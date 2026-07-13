"""Backup and restore for the business workflow JSON store."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile

from app.repositories.business_metrics import (
    BusinessAuditAction,
    BusinessMetricsRepository,
    BusinessRecordKind,
    BusinessStatus,
)


class WorkflowBackupError(RuntimeError):
    """Base backup error."""


class WorkflowBackupValidationError(WorkflowBackupError):
    """Raised when a backup cannot be safely restored."""


@dataclass(frozen=True, slots=True)
class WorkflowBackupInspection:
    path: Path
    valid: bool
    created_at: str = ""
    schema_version: int = 0
    record_count: int = 0
    event_count: int = 0
    archived_count: int = 0
    checksum_sha256: str = ""
    errors: tuple[str, ...] = ()

    @property
    def created_timestamp(self) -> datetime | None:
        try:
            return datetime.fromisoformat(self.created_at)
        except (TypeError, ValueError):
            return None


@dataclass(frozen=True, slots=True)
class WorkflowBackupCreateResult:
    path: Path
    inspection: WorkflowBackupInspection
    size_bytes: int


@dataclass(frozen=True, slots=True)
class WorkflowBackupRestoreResult:
    source: Path
    safety_backup: Path
    record_count: int
    event_count: int
    archived_count: int


class WorkflowBackupService:
    """Create, validate and restore portable CORTERIS backups."""

    FORMAT_NAME = "corteris.business_workflow.backup"
    FORMAT_VERSION = 1
    MANIFEST_NAME = "manifest.json"
    PAYLOAD_NAME = "business_workflow.json"
    DEFAULT_EXTENSION = ".ctbackup"
    MAX_PAYLOAD_BYTES = 100 * 1024 * 1024

    def create_backup(
        self,
        repository: BusinessMetricsRepository,
        target: str | Path,
        *,
        created_at: datetime | None = None,
    ) -> WorkflowBackupCreateResult:
        timestamp = created_at or datetime.now()
        destination = self._normalize_target(target)
        destination.parent.mkdir(parents=True, exist_ok=True)

        payload = repository.snapshot_payload()
        payload_bytes = self._serialize_payload(payload)
        checksum = hashlib.sha256(payload_bytes).hexdigest()
        records = payload.get("records", [])
        events = payload.get("events", [])
        archived_count = self._archived_count(records)

        manifest = {
            "format": self.FORMAT_NAME,
            "format_version": self.FORMAT_VERSION,
            "created_at": timestamp.isoformat(timespec="seconds"),
            "schema_version": int(
                payload.get(
                    "schema_version",
                    repository.SCHEMA_VERSION,
                )
            ),
            "record_count": len(records),
            "event_count": len(events),
            "archived_count": archived_count,
            "checksum_sha256": checksum,
            "payload_name": self.PAYLOAD_NAME,
        }

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
                    json.dumps(
                        manifest,
                        ensure_ascii=False,
                        indent=2,
                    ).encode("utf-8"),
                )
                archive.writestr(
                    self.PAYLOAD_NAME,
                    payload_bytes,
                )
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)

        inspection = self.inspect_backup(destination)
        if not inspection.valid:
            destination.unlink(missing_ok=True)
            raise WorkflowBackupError(
                "Созданная копия не прошла проверку:\n" + "\n".join(inspection.errors)
            )

        return WorkflowBackupCreateResult(
            path=destination,
            inspection=inspection,
            size_bytes=destination.stat().st_size,
        )

    def inspect_backup(
        self,
        source: str | Path,
    ) -> WorkflowBackupInspection:
        path = Path(source).expanduser()
        if not path.is_file():
            return WorkflowBackupInspection(
                path=path,
                valid=False,
                errors=(f"Файл не найден: {path}",),
            )

        errors: list[str] = []
        manifest: dict[str, Any] = {}
        payload: dict[str, Any] | None = None
        payload_bytes = b""

        try:
            with ZipFile(path, "r") as archive:
                names = set(archive.namelist())
                missing = [
                    name
                    for name in (
                        self.MANIFEST_NAME,
                        self.PAYLOAD_NAME,
                    )
                    if name not in names
                ]
                if missing:
                    return WorkflowBackupInspection(
                        path=path,
                        valid=False,
                        errors=tuple(f"В архиве отсутствует {name}." for name in missing),
                    )

                payload_info = archive.getinfo(self.PAYLOAD_NAME)
                if payload_info.file_size > self.MAX_PAYLOAD_BYTES:
                    errors.append("Файл данных превышает допустимые 100 МБ.")
                else:
                    payload_bytes = archive.read(self.PAYLOAD_NAME)
                manifest_bytes = archive.read(self.MANIFEST_NAME)
        except (BadZipFile, OSError, KeyError) as exc:
            return WorkflowBackupInspection(
                path=path,
                valid=False,
                errors=(f"Не удалось прочитать резервную копию: {exc}",),
            )

        try:
            value = json.loads(manifest_bytes.decode("utf-8"))
            if isinstance(value, dict):
                manifest = value
            else:
                errors.append("manifest.json должен быть объектом.")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"Повреждён manifest.json: {exc}")

        try:
            value = json.loads(payload_bytes.decode("utf-8"))
            if isinstance(value, dict):
                payload = value
            else:
                errors.append("business_workflow.json должен быть объектом.")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"Повреждён business_workflow.json: {exc}")

        if manifest:
            if manifest.get("format") != self.FORMAT_NAME:
                errors.append("Файл не является резервной копией CORTERIS.")
            version = self._integer(
                manifest.get("format_version"),
                default=0,
            )
            if version != self.FORMAT_VERSION:
                errors.append(f"Неподдерживаемая версия формата: {version}.")
            expected = str(manifest.get("checksum_sha256", ""))
            actual = hashlib.sha256(payload_bytes).hexdigest()
            if not expected:
                errors.append("В manifest.json нет контрольной суммы.")
            elif expected != actual:
                errors.append("Контрольная сумма не совпадает: данные изменены или повреждены.")

        if payload is not None:
            errors.extend(self._validate_payload(payload))

        records = payload.get("records", []) if payload is not None else []
        events = payload.get("events", []) if payload is not None else []
        archived_count = self._archived_count(records)

        if manifest and payload is not None:
            self._check_count(
                errors,
                manifest,
                "record_count",
                len(records),
                "записей",
            )
            self._check_count(
                errors,
                manifest,
                "event_count",
                len(events),
                "событий",
            )
            self._check_count(
                errors,
                manifest,
                "archived_count",
                archived_count,
                "архивных записей",
            )

        schema_version = self._integer(
            (
                payload.get("schema_version")
                if payload is not None
                else manifest.get("schema_version")
            ),
            default=0,
        )
        return WorkflowBackupInspection(
            path=path,
            valid=not errors,
            created_at=str(manifest.get("created_at", "")),
            schema_version=schema_version,
            record_count=len(records),
            event_count=len(events),
            archived_count=archived_count,
            checksum_sha256=str(manifest.get("checksum_sha256", "")),
            errors=tuple(errors),
        )

    def restore_backup(
        self,
        source: str | Path,
        repository: BusinessMetricsRepository,
        *,
        safety_directory: str | Path | None = None,
        restored_at: datetime | None = None,
    ) -> WorkflowBackupRestoreResult:
        path = Path(source).expanduser()
        inspection, payload = self._load_valid_backup(path)
        timestamp = restored_at or datetime.now()

        safety_dir = (
            Path(safety_directory).expanduser()
            if safety_directory is not None
            else repository.path.parent / "backups"
        )
        safety_dir.mkdir(parents=True, exist_ok=True)
        safety_path = safety_dir / (
            f"CORTERIS_auto_before_restore_{timestamp:%Y%m%d_%H%M%S}{self.DEFAULT_EXTENSION}"
        )
        safety = self.create_backup(
            repository,
            safety_path,
            created_at=timestamp,
        )

        try:
            repository.replace_payload(payload)
        except Exception:
            _, old_payload = self._load_valid_backup(safety.path)
            repository.replace_payload(old_payload)
            raise

        return WorkflowBackupRestoreResult(
            source=path,
            safety_backup=safety.path,
            record_count=inspection.record_count,
            event_count=inspection.event_count,
            archived_count=inspection.archived_count,
        )

    def _load_valid_backup(
        self,
        path: Path,
    ) -> tuple[WorkflowBackupInspection, dict[str, Any]]:
        inspection = self.inspect_backup(path)
        if not inspection.valid:
            raise WorkflowBackupValidationError(
                "Резервная копия не прошла проверку:\n"
                + "\n".join(f"• {error}" for error in inspection.errors)
            )
        with ZipFile(path, "r") as archive:
            payload = json.loads(archive.read(self.PAYLOAD_NAME).decode("utf-8"))
        return inspection, payload

    def _validate_payload(
        self,
        payload: dict[str, Any],
    ) -> list[str]:
        errors: list[str] = []
        schema = self._integer(
            payload.get("schema_version"),
            default=0,
        )
        if schema < 1:
            errors.append("Некорректная версия схемы данных.")
        elif schema > BusinessMetricsRepository.SCHEMA_VERSION:
            errors.append(
                "Копия создана более новой версией приложения: "
                f"схема {schema}, поддерживается "
                f"{BusinessMetricsRepository.SCHEMA_VERSION}."
            )

        records = payload.get("records")
        events = payload.get("events", [])
        if not isinstance(records, list):
            errors.append("Поле records должно быть списком.")
            records = []
        if not isinstance(events, list):
            errors.append("Поле events должно быть списком.")
            events = []

        record_ids: set[str] = set()
        for index, record in enumerate(records, start=1):
            prefix = f"Запись {index}"
            if not isinstance(record, dict):
                errors.append(f"{prefix}: ожидается объект.")
                continue

            record_id = str(record.get("id", "")).strip()
            if not record_id:
                errors.append(f"{prefix}: отсутствует ID.")
            elif record_id in record_ids:
                errors.append(f"{prefix}: повторяется ID «{record_id}».")
            else:
                record_ids.add(record_id)

            self._check_enum(
                errors,
                prefix,
                "kind",
                record.get("kind"),
                BusinessRecordKind,
            )
            self._check_enum(
                errors,
                prefix,
                "status",
                record.get("status"),
                BusinessStatus,
            )
            for field in ("tender_id", "title"):
                if not str(record.get(field, "")).strip():
                    errors.append(f"{prefix}: поле {field} не заполнено.")
            for field in (
                "total",
                "profit",
                "margin_percent",
            ):
                try:
                    float(record.get(field, 0))
                except (TypeError, ValueError):
                    errors.append(f"{prefix}: поле {field} должно быть числом.")

        event_ids: set[str] = set()
        for index, event in enumerate(events, start=1):
            prefix = f"Событие {index}"
            if not isinstance(event, dict):
                errors.append(f"{prefix}: ожидается объект.")
                continue

            event_id = str(event.get("id", "")).strip()
            if not event_id:
                errors.append(f"{prefix}: отсутствует ID.")
            elif event_id in event_ids:
                errors.append(f"{prefix}: повторяется ID «{event_id}».")
            else:
                event_ids.add(event_id)

            record_id = str(event.get("record_id", "")).strip()
            if record_id not in record_ids:
                errors.append(f"{prefix}: неизвестная запись «{record_id}».")
            self._check_enum(
                errors,
                prefix,
                "action",
                event.get("action"),
                BusinessAuditAction,
            )
            occurred_at = str(event.get("occurred_at", "")).strip()
            if not occurred_at:
                errors.append(f"{prefix}: отсутствует дата события.")
            else:
                try:
                    datetime.fromisoformat(occurred_at)
                except ValueError:
                    errors.append(f"{prefix}: неверная дата «{occurred_at}».")
        return errors

    @staticmethod
    def _check_enum(
        errors: list[str],
        prefix: str,
        field: str,
        value: Any,
        enum_type,
    ) -> None:
        try:
            enum_type(value)
        except (TypeError, ValueError):
            errors.append(f"{prefix}: неизвестное значение {field} «{value}».")

    @staticmethod
    def _check_count(
        errors: list[str],
        manifest: dict[str, Any],
        field: str,
        actual: int,
        label: str,
    ) -> None:
        expected = WorkflowBackupService._integer(
            manifest.get(field),
            default=-1,
        )
        if expected != actual:
            errors.append(f"Manifest содержит {expected} {label}, фактически найдено {actual}.")

    @staticmethod
    def _archived_count(records: Any) -> int:
        if not isinstance(records, list):
            return 0
        return sum(
            1
            for record in records
            if isinstance(record, dict) and bool(str(record.get("archived_at", "")).strip())
        )

    @staticmethod
    def _serialize_payload(
        payload: dict[str, Any],
    ) -> bytes:
        return json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")

    def _normalize_target(self, target: str | Path) -> Path:
        path = Path(target).expanduser()
        if path.suffix.lower() not in {
            self.DEFAULT_EXTENSION,
            ".zip",
        }:
            path = path.with_suffix(self.DEFAULT_EXTENSION)
        return path

    @staticmethod
    def _integer(value: Any, *, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default


__all__ = [
    "WorkflowBackupCreateResult",
    "WorkflowBackupError",
    "WorkflowBackupInspection",
    "WorkflowBackupRestoreResult",
    "WorkflowBackupService",
    "WorkflowBackupValidationError",
]
