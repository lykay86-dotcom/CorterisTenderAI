"""Privacy-aware diagnostic support bundle for CORTERIS Tender AI."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import re
import sys
from typing import Any, Iterable, Sequence
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile

from app.core.system_health import (
    SystemHealthJournal,
    SystemHealthSnapshot,
)
from app.core.workflow_auto_backup import WorkflowAutoBackupService
from app.core.workflow_backup_catalog import (
    WorkflowBackupCatalogService,
)
from app.repositories.business_metrics import BusinessMetricsRepository


@dataclass(frozen=True, slots=True)
class DiagnosticSupportBundleResult:
    path: Path
    size_bytes: int
    file_count: int
    created_at: str


@dataclass(frozen=True, slots=True)
class DiagnosticSupportBundleInspection:
    path: Path
    valid: bool
    created_at: str = ""
    file_count: int = 0
    errors: tuple[str, ...] = ()


class _Redactor:
    """Remove common secrets and user-specific filesystem paths."""

    EMAIL = re.compile(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        re.IGNORECASE,
    )
    BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{6,}")
    SECRET_VALUE = re.compile(
        r"""(?ix)
        \b(
            api[_\-\s]?key
            |access[_\-\s]?token
            |refresh[_\-\s]?token
            |token
            |password
            |passwd
            |secret
            |authorization
        )
        (\s*[:=]\s*)
        (["']?)[^,\s;"']+\3
        """
    )

    def __init__(self, roots: Iterable[str | Path]) -> None:
        values: list[str] = []

        for root in roots:
            text = str(root).strip()
            if text:
                values.append(text)

        for env_name in ("USERPROFILE", "HOME", "HOMEPATH"):
            value = os.environ.get(env_name, "").strip()
            if value:
                values.append(value)

        try:
            values.append(str(Path.home()))
        except RuntimeError:
            pass

        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            for variant in {
                value,
                value.replace("\\", "/"),
                value.replace("/", "\\"),
            }:
                key = variant.casefold()
                if variant and key not in seen:
                    seen.add(key)
                    normalized.append(variant)

        normalized.sort(key=len, reverse=True)
        self._roots = tuple(normalized)

    def text(self, value: Any) -> str:
        result = str(value)
        for root in self._roots:
            result = re.sub(
                re.escape(root),
                "<PRIVATE_PATH>",
                result,
                flags=re.IGNORECASE,
            )

        result = self.EMAIL.sub("<EMAIL>", result)
        result = self.BEARER.sub(
            "Bearer <REDACTED>",
            result,
        )
        result = self.SECRET_VALUE.sub(
            lambda match: f"{match.group(1)}{match.group(2)}<REDACTED>",
            result,
        )
        return result

    def value(self, value: Any) -> Any:
        if value is None or isinstance(value, (bool, int, float)):
            return value
        if isinstance(value, datetime):
            return value.isoformat(timespec="seconds")
        if isinstance(value, Path):
            return self.text(value)
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return {self.text(key): self.value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self.value(item) for item in value]
        return self.text(value)


class DiagnosticSupportBundleService:
    """Create and verify a support ZIP without business document contents."""

    FORMAT_NAME = "corteris.diagnostic_support_bundle"
    FORMAT_VERSION = 1
    DEFAULT_EXTENSION = ".ctsupport"
    MANIFEST_NAME = "manifest.json"

    REQUIRED_FILES = {
        "README.txt",
        "environment.json",
        "health_snapshot.json",
        "database_summary.json",
        "auto_backup.json",
        "backup_inventory.json",
        "system_health_journal.txt",
        "privacy_report.json",
    }

    MAX_BACKUP_FILES = 200
    MAX_LOG_FILES = 5
    MAX_LOG_FILE_BYTES = 1024 * 1024
    MAX_TOTAL_LOG_BYTES = 5 * 1024 * 1024

    def create_bundle(
        self,
        target: str | Path,
        *,
        repository: BusinessMetricsRepository,
        snapshot: SystemHealthSnapshot,
        journal: SystemHealthJournal,
        auto_backup_service: WorkflowAutoBackupService,
        backup_catalog_service: WorkflowBackupCatalogService,
        backup_directories: Sequence[str | Path],
        log_directories: Sequence[str | Path] = (),
        created_at: datetime | None = None,
    ) -> DiagnosticSupportBundleResult:
        timestamp = created_at or datetime.now()
        destination = self._normalize_target(target)
        destination.parent.mkdir(parents=True, exist_ok=True)

        app_data_root = repository.path.parent
        redactor = _Redactor(
            (
                app_data_root,
                repository.path,
                auto_backup_service.settings_path,
                *backup_directories,
                *log_directories,
            )
        )

        files: dict[str, bytes] = {}
        files["README.txt"] = self._text_bytes(self._readme_text(timestamp))
        files["environment.json"] = self._json_bytes(redactor.value(self._environment_payload()))
        files["health_snapshot.json"] = self._json_bytes(
            redactor.value(self._snapshot_payload(snapshot))
        )
        files["database_summary.json"] = self._json_bytes(
            redactor.value(self._database_payload(repository, snapshot))
        )
        files["auto_backup.json"] = self._json_bytes(
            redactor.value(asdict(auto_backup_service.load_settings()))
        )
        files["backup_inventory.json"] = self._json_bytes(
            redactor.value(
                self._backup_inventory(
                    backup_catalog_service,
                    backup_directories,
                )
            )
        )
        files["system_health_journal.txt"] = self._text_bytes(self._journal_text(journal, redactor))

        log_files = self._collect_logs(
            repository=repository,
            explicit_directories=log_directories,
            redactor=redactor,
        )
        files.update(log_files)

        files["privacy_report.json"] = self._json_bytes(
            {
                "business_database_included": False,
                "business_records_included": False,
                "attached_documents_included": False,
                "backup_payloads_included": False,
                "credentials_intentionally_included": False,
                "filesystem_paths_redacted": True,
                "emails_redacted": True,
                "common_secret_values_redacted": True,
                "included_log_files": sorted(log_files),
                "note": (
                    "Пакет содержит технические метаданные, сводные "
                    "счётчики и очищенные журналы. Перед отправкой "
                    "пакет можно открыть как ZIP и проверить вручную."
                ),
            }
        )

        manifest_files = [
            {
                "name": name,
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
            for name, content in sorted(files.items())
        ]
        manifest = {
            "format": self.FORMAT_NAME,
            "format_version": self.FORMAT_VERSION,
            "created_at": timestamp.isoformat(timespec="seconds"),
            "application": "CORTERIS Tender AI",
            "files": manifest_files,
        }
        manifest_bytes = self._json_bytes(manifest)

        temporary = destination.with_suffix(destination.suffix + ".tmp")
        try:
            with ZipFile(
                temporary,
                "w",
                compression=ZIP_DEFLATED,
                compresslevel=9,
            ) as archive:
                archive.writestr(
                    self.MANIFEST_NAME,
                    manifest_bytes,
                )
                for name, content in sorted(files.items()):
                    archive.writestr(name, content)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)

        inspection = self.inspect_bundle(destination)
        if not inspection.valid:
            destination.unlink(missing_ok=True)
            raise RuntimeError(
                "Пакет диагностики не прошёл проверку:\n"
                + "\n".join(f"• {error}" for error in inspection.errors)
            )

        return DiagnosticSupportBundleResult(
            path=destination,
            size_bytes=destination.stat().st_size,
            file_count=inspection.file_count,
            created_at=inspection.created_at,
        )

    def inspect_bundle(
        self,
        source: str | Path,
    ) -> DiagnosticSupportBundleInspection:
        path = Path(source).expanduser()
        errors: list[str] = []

        if not path.is_file():
            return DiagnosticSupportBundleInspection(
                path=path,
                valid=False,
                errors=(f"Файл не найден: {path}",),
            )

        try:
            with ZipFile(path, "r") as archive:
                names = set(archive.namelist())
                if self.MANIFEST_NAME not in names:
                    return DiagnosticSupportBundleInspection(
                        path=path,
                        valid=False,
                        errors=("В пакете отсутствует manifest.json.",),
                    )

                try:
                    manifest = json.loads(archive.read(self.MANIFEST_NAME).decode("utf-8"))
                except (
                    UnicodeDecodeError,
                    json.JSONDecodeError,
                    KeyError,
                ) as exc:
                    return DiagnosticSupportBundleInspection(
                        path=path,
                        valid=False,
                        errors=(f"Повреждён manifest.json: {exc}",),
                    )

                if not isinstance(manifest, dict):
                    errors.append("manifest.json должен быть объектом.")
                    manifest = {}

                if manifest.get("format") != self.FORMAT_NAME:
                    errors.append("Файл не является пакетом диагностики CORTERIS.")
                if self._integer(manifest.get("format_version", 0)) != self.FORMAT_VERSION:
                    errors.append("Неподдерживаемая версия пакета диагностики.")

                listed = manifest.get("files", [])
                if not isinstance(listed, list):
                    errors.append("Поле files в manifest.json должно быть списком.")
                    listed = []

                listed_names: set[str] = set()
                for item in listed:
                    if not isinstance(item, dict):
                        errors.append("Некорректная запись файла в manifest.json.")
                        continue

                    name = str(item.get("name", "")).strip()
                    if not name:
                        errors.append("В manifest.json найден файл без имени.")
                        continue
                    listed_names.add(name)

                    if name not in names:
                        errors.append(f"В архиве отсутствует {name}.")
                        continue

                    content = archive.read(name)
                    expected_size = self._integer(item.get("size_bytes", -1))
                    if expected_size != len(content):
                        errors.append(f"Размер {name} не совпадает с manifest.json.")

                    expected_hash = str(item.get("sha256", "")).strip()
                    actual_hash = hashlib.sha256(content).hexdigest()
                    if expected_hash != actual_hash:
                        errors.append(f"Контрольная сумма {name} не совпадает.")

                missing_required = self.REQUIRED_FILES - listed_names
                for name in sorted(missing_required):
                    errors.append(f"В пакете отсутствует обязательный файл {name}.")

                unexpected = names - listed_names - {self.MANIFEST_NAME}
                for name in sorted(unexpected):
                    errors.append(f"Файл {name} не описан в manifest.json.")

                created_at = str(manifest.get("created_at", "")).strip()
                return DiagnosticSupportBundleInspection(
                    path=path,
                    valid=not errors,
                    created_at=created_at,
                    file_count=len(listed_names),
                    errors=tuple(errors),
                )
        except (BadZipFile, OSError) as exc:
            return DiagnosticSupportBundleInspection(
                path=path,
                valid=False,
                errors=(f"Не удалось прочитать пакет: {exc}",),
            )

    def _backup_inventory(
        self,
        catalog: WorkflowBackupCatalogService,
        directories: Sequence[str | Path],
    ) -> dict[str, Any]:
        roots = self._unique_paths(directories)
        candidates: dict[str, Path] = {}

        for root in roots:
            if not root.is_dir():
                continue
            try:
                children = root.iterdir()
            except OSError:
                continue

            for path in children:
                try:
                    supported = path.is_file() and path.suffix.lower() in catalog.SUPPORTED_SUFFIXES
                except OSError:
                    continue
                if not supported:
                    continue
                candidates[str(path.resolve(strict=False)).casefold()] = path

        ordered = sorted(
            candidates.values(),
            key=self._safe_mtime,
            reverse=True,
        )[: self.MAX_BACKUP_FILES]

        entries: list[dict[str, Any]] = []
        for path in ordered:
            try:
                entry = catalog.refresh_entry(
                    path,
                    managed_directories=roots,
                )
            except Exception as exc:
                entries.append(
                    {
                        "name": path.name,
                        "path": path,
                        "valid": False,
                        "errors": [str(exc)],
                    }
                )
                continue

            entries.append(
                {
                    "name": entry.path.name,
                    "path": entry.path,
                    "kind": entry.kind,
                    "valid": entry.valid,
                    "size_bytes": entry.size_bytes,
                    "modified_at": entry.modified_at,
                    "created_at": entry.created_timestamp,
                    "schema_version": (entry.inspection.schema_version),
                    "record_count": (entry.inspection.record_count),
                    "event_count": entry.inspection.event_count,
                    "archived_count": (entry.inspection.archived_count),
                    "errors": entry.inspection.errors,
                }
            )

        return {
            "directories": list(roots),
            "candidate_limit": self.MAX_BACKUP_FILES,
            "total": len(entries),
            "valid": sum(1 for item in entries if item.get("valid")),
            "invalid": sum(1 for item in entries if not item.get("valid")),
            "entries": entries,
        }

    def _collect_logs(
        self,
        *,
        repository: BusinessMetricsRepository,
        explicit_directories: Sequence[str | Path],
        redactor: _Redactor,
    ) -> dict[str, bytes]:
        roots = self._unique_paths(
            (
                repository.path.parent / "logs",
                repository.path.parent,
                *explicit_directories,
            )
        )
        candidates: dict[str, Path] = {}

        for root in roots:
            if not root.is_dir():
                continue
            try:
                children = root.iterdir()
            except OSError:
                continue

            for path in children:
                try:
                    supported = path.is_file() and path.suffix.lower() in {".log", ".txt"}
                except OSError:
                    continue
                if not supported:
                    continue
                candidates[str(path.resolve(strict=False)).casefold()] = path

        ordered = sorted(
            candidates.values(),
            key=self._safe_mtime,
            reverse=True,
        )[: self.MAX_LOG_FILES]

        total = 0
        result: dict[str, bytes] = {}
        for index, path in enumerate(ordered, start=1):
            remaining = self.MAX_TOTAL_LOG_BYTES - total
            if remaining <= 0:
                break
            limit = min(self.MAX_LOG_FILE_BYTES, remaining)

            try:
                with path.open("rb") as handle:
                    handle.seek(0, 2)
                    size = handle.tell()
                    handle.seek(max(0, size - limit))
                    raw = handle.read(limit)
            except OSError:
                continue

            text = raw.decode("utf-8", errors="replace")
            text = redactor.text(text)
            safe_name = self._safe_filename(path.name)
            archive_name = f"logs/{index:02d}_{safe_name}"
            encoded = self._text_bytes(text)
            result[archive_name] = encoded
            total += len(encoded)

        return result

    @staticmethod
    def _snapshot_payload(
        snapshot: SystemHealthSnapshot,
    ) -> dict[str, Any]:
        database = snapshot.database
        return {
            "checked_at": snapshot.checked_at,
            "severity": snapshot.severity,
            "status_label": snapshot.status_label,
            "issues": snapshot.issues,
            "database": {
                "path": database.path,
                "status": database.status,
                "status_label": database.status_label,
                "schema_version": database.schema_version,
                "record_count": database.record_count,
                "event_count": database.event_count,
                "archived_count": database.archived_count,
                "file_size": database.file_size,
                "issues": [
                    {
                        "code": issue.code,
                        "message": issue.message,
                        "fatal": issue.fatal,
                    }
                    for issue in database.issues
                ],
            },
            "auto_backup": {
                "enabled": snapshot.auto_backup_enabled,
                "interval_hours": (snapshot.auto_backup_interval_hours),
                "retention_count": (snapshot.auto_backup_retention_count),
                "last_success_at": (snapshot.auto_backup_last_success_at),
                "last_error": snapshot.auto_backup_last_error,
            },
            "backups": {
                "total": snapshot.backup_total,
                "valid": snapshot.backup_valid,
                "invalid": snapshot.backup_invalid,
                "latest_backup_at": snapshot.latest_backup_at,
            },
            "journal_count": snapshot.journal_count,
        }

    @staticmethod
    def _database_payload(
        repository: BusinessMetricsRepository,
        snapshot: SystemHealthSnapshot,
    ) -> dict[str, Any]:
        path = repository.path
        exists = path.is_file()
        checksum = ""
        size_bytes = 0

        if exists:
            try:
                size_bytes = path.stat().st_size
                digest = hashlib.sha256()
                with path.open("rb") as handle:
                    for chunk in iter(
                        lambda: handle.read(1024 * 1024),
                        b"",
                    ):
                        digest.update(chunk)
                checksum = digest.hexdigest()
            except OSError:
                checksum = ""

        return {
            "path": path,
            "filename": path.name,
            "exists": exists,
            "size_bytes": size_bytes,
            "sha256": checksum,
            "schema_version": (snapshot.database.schema_version),
            "record_count": snapshot.database.record_count,
            "event_count": snapshot.database.event_count,
            "archived_count": (snapshot.database.archived_count),
            "raw_database_included": False,
        }

    @staticmethod
    def _environment_payload() -> dict[str, Any]:
        return {
            "generated_on": datetime.now(),
            "python": {
                "version": sys.version,
                "implementation": platform.python_implementation(),
                "executable": sys.executable,
                "frozen": bool(getattr(sys, "frozen", False)),
            },
            "operating_system": {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "platform": platform.platform(),
            },
            "packages": {
                name: DiagnosticSupportBundleService._package_version(name)
                for name in (
                    "PySide6",
                    "openpyxl",
                    "pytest",
                )
            },
        }

    @staticmethod
    def _journal_text(
        journal: SystemHealthJournal,
        redactor: _Redactor,
    ) -> str:
        lines = [
            "CORTERIS Tender AI — системный журнал",
            "=" * 48,
            "",
        ]
        for event in journal.list_events(limit=None):
            timestamp = event.timestamp
            date_text = (
                timestamp.strftime("%d.%m.%Y %H:%M:%S")
                if timestamp is not None
                else event.occurred_at
            )
            lines.append(
                f"[{date_text}] [{event.severity.value.upper()}] [{event.component}] {event.title}"
            )
            if event.details:
                lines.append("  " + redactor.text(event.details))
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _readme_text(timestamp: datetime) -> str:
        return (
            "CORTERIS Tender AI — пакет технической диагностики\n"
            f"Создан: {timestamp:%d.%m.%Y %H:%M:%S}\n\n"
            "Пакет предназначен для поиска технических ошибок.\n"
            "Он НЕ содержит:\n"
            "- business_workflow.json и содержимое бизнес-записей;\n"
            "- файлы КП, смет, проектов и тендерной документации;\n"
            "- содержимое резервных копий;\n"
            "- намеренно добавленные пароли, токены или API-ключи.\n\n"
            "В пакет входят технические версии, сводные счётчики,\n"
            "инвентаризация копий и очищенные журналы. Абсолютные\n"
            "пользовательские пути, email и распространённые секреты\n"
            "заменяются служебными маркерами.\n\n"
            "Файл .ctsupport является обычным ZIP-архивом. Его можно\n"
            "открыть и проверить перед передачей техническому специалисту.\n"
        )

    def _normalize_target(self, target: str | Path) -> Path:
        path = Path(target).expanduser()
        if path.suffix.lower() not in {
            self.DEFAULT_EXTENSION,
            ".zip",
        }:
            path = path.with_suffix(self.DEFAULT_EXTENSION)
        return path

    @staticmethod
    def _json_bytes(payload: Any) -> bytes:
        return json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")

    @staticmethod
    def _text_bytes(text: str) -> bytes:
        return text.encode("utf-8-sig")

    @staticmethod
    def _package_version(name: str) -> str:
        try:
            return metadata.version(name)
        except metadata.PackageNotFoundError:
            return "not-installed"

    @staticmethod
    def _safe_filename(name: str) -> str:
        cleaned = re.sub(r"[^A-Za-zА-Яа-я0-9._-]+", "_", name)
        return cleaned[:120] or "log.txt"

    @staticmethod
    def _unique_paths(
        paths: Iterable[str | Path],
    ) -> tuple[Path, ...]:
        result: list[Path] = []
        seen: set[str] = set()
        for item in paths:
            path = Path(item).expanduser()
            identity = str(path.resolve(strict=False)).casefold()
            if identity in seen:
                continue
            seen.add(identity)
            result.append(path)
        return tuple(result)

    @staticmethod
    def _safe_mtime(path: Path) -> int:
        try:
            return path.stat().st_mtime_ns
        except OSError:
            return 0

    @staticmethod
    def _integer(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0


__all__ = [
    "DiagnosticSupportBundleInspection",
    "DiagnosticSupportBundleResult",
    "DiagnosticSupportBundleService",
]
