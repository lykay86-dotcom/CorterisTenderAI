"""Diagnostics and recovery for business_workflow.json."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import json
from pathlib import Path
import shutil
from typing import Any, Sequence

from app.core.workflow_backup import (
    WorkflowBackupRestoreResult,
    WorkflowBackupService,
)
from app.core.workflow_backup_catalog import (
    WorkflowBackupCatalogService,
    WorkflowBackupEntry,
)
from app.repositories.business_metrics import (
    BusinessAuditAction,
    BusinessMetricsRepository,
    BusinessRecordKind,
    BusinessStatus,
)


class WorkflowDatabaseHealthStatus(StrEnum):
    HEALTHY = "healthy"
    EMPTY = "empty"
    MISSING = "missing"
    CORRUPTED = "corrupted"
    INVALID = "invalid"
    INCOMPATIBLE = "incompatible"


@dataclass(frozen=True, slots=True)
class WorkflowDatabaseIssue:
    code: str
    message: str
    fatal: bool = True


@dataclass(frozen=True, slots=True)
class WorkflowDatabaseHealthReport:
    path: Path
    status: WorkflowDatabaseHealthStatus
    checked_at: datetime
    schema_version: int = 0
    record_count: int = 0
    event_count: int = 0
    archived_count: int = 0
    file_size: int = 0
    issues: tuple[WorkflowDatabaseIssue, ...] = ()
    latest_valid_backup: WorkflowBackupEntry | None = None

    @property
    def requires_recovery(self) -> bool:
        return self.status in {
            WorkflowDatabaseHealthStatus.CORRUPTED,
            WorkflowDatabaseHealthStatus.INVALID,
            WorkflowDatabaseHealthStatus.INCOMPATIBLE,
        }

    @property
    def safe_for_backup(self) -> bool:
        return self.status in {
            WorkflowDatabaseHealthStatus.HEALTHY,
            WorkflowDatabaseHealthStatus.EMPTY,
        }

    @property
    def status_label(self) -> str:
        return {
            WorkflowDatabaseHealthStatus.HEALTHY: "Исправна",
            WorkflowDatabaseHealthStatus.EMPTY: "Исправна, записей нет",
            WorkflowDatabaseHealthStatus.MISSING: "Файл ещё не создан",
            WorkflowDatabaseHealthStatus.CORRUPTED: "Повреждён JSON",
            WorkflowDatabaseHealthStatus.INVALID: "Нарушена структура",
            WorkflowDatabaseHealthStatus.INCOMPATIBLE: ("Создана более новой версией"),
        }[self.status]


@dataclass(frozen=True, slots=True)
class WorkflowDatabaseRecoveryResult:
    restored_from: Path | None
    quarantine_path: Path | None
    safety_backup: Path | None
    report: WorkflowDatabaseHealthReport
    initialized_empty: bool = False


class WorkflowDatabaseHealthService:
    """Inspect the live JSON file and recover it from verified backups."""

    MAX_DATABASE_BYTES = 100 * 1024 * 1024
    MAX_BACKUP_CANDIDATES = 100

    def __init__(
        self,
        *,
        backup_service: WorkflowBackupService | None = None,
        catalog_service: WorkflowBackupCatalogService | None = None,
    ) -> None:
        self.backup_service = backup_service or WorkflowBackupService()
        self.catalog_service = catalog_service or WorkflowBackupCatalogService(self.backup_service)

    def inspect(
        self,
        repository: BusinessMetricsRepository,
        *,
        backup_directories: Sequence[str | Path] = (),
    ) -> WorkflowDatabaseHealthReport:
        path = repository.path
        checked_at = datetime.now()
        latest_backup = self._latest_valid_backup(backup_directories)

        if not path.exists():
            return WorkflowDatabaseHealthReport(
                path=path,
                status=WorkflowDatabaseHealthStatus.MISSING,
                checked_at=checked_at,
                latest_valid_backup=latest_backup,
            )

        try:
            file_size = path.stat().st_size
        except OSError as exc:
            return self._failure_report(
                path,
                checked_at,
                WorkflowDatabaseHealthStatus.CORRUPTED,
                "database_stat_error",
                f"Не удалось прочитать параметры файла: {exc}",
                latest_backup,
            )

        if file_size > self.MAX_DATABASE_BYTES:
            return WorkflowDatabaseHealthReport(
                path=path,
                status=WorkflowDatabaseHealthStatus.INVALID,
                checked_at=checked_at,
                file_size=file_size,
                issues=(
                    WorkflowDatabaseIssue(
                        "database_too_large",
                        (
                            "Размер базы превышает допустимые "
                            f"{self.MAX_DATABASE_BYTES // 1024 // 1024} МБ."
                        ),
                    ),
                ),
                latest_valid_backup=latest_backup,
            )

        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return self._failure_report(
                path,
                checked_at,
                WorkflowDatabaseHealthStatus.CORRUPTED,
                "database_read_error",
                f"Не удалось прочитать JSON в UTF-8: {exc}",
                latest_backup,
                file_size=file_size,
            )

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            return self._failure_report(
                path,
                checked_at,
                WorkflowDatabaseHealthStatus.CORRUPTED,
                "json_decode_error",
                (f"Ошибка JSON: строка {exc.lineno}, столбец {exc.colno}: {exc.msg}."),
                latest_backup,
                file_size=file_size,
            )

        if not isinstance(payload, dict):
            return self._failure_report(
                path,
                checked_at,
                WorkflowDatabaseHealthStatus.INVALID,
                "payload_not_object",
                "Корневой элемент JSON должен быть объектом.",
                latest_backup,
                file_size=file_size,
            )

        schema_version = self._integer(payload.get("schema_version", 0))
        issues: list[WorkflowDatabaseIssue] = []

        if schema_version < 1:
            issues.append(
                WorkflowDatabaseIssue(
                    "schema_invalid",
                    "Не указана корректная версия схемы данных.",
                )
            )
        elif schema_version > repository.SCHEMA_VERSION:
            issues.append(
                WorkflowDatabaseIssue(
                    "schema_newer",
                    (
                        f"Схема {schema_version} новее поддерживаемой "
                        f"схемы {repository.SCHEMA_VERSION}."
                    ),
                )
            )

        records = payload.get("records")
        events = payload.get("events", [])

        if not isinstance(records, list):
            issues.append(
                WorkflowDatabaseIssue(
                    "records_not_list",
                    "Поле records должно быть списком.",
                )
            )
            records = []
        if not isinstance(events, list):
            issues.append(
                WorkflowDatabaseIssue(
                    "events_not_list",
                    "Поле events должно быть списком.",
                )
            )
            events = []

        record_ids: set[str] = set()
        archived_count = 0

        for index, record in enumerate(records, start=1):
            prefix = f"Запись {index}"
            if not isinstance(record, dict):
                issues.append(
                    WorkflowDatabaseIssue(
                        "record_not_object",
                        f"{prefix}: ожидается объект.",
                    )
                )
                continue

            record_id = str(record.get("id", "")).strip()
            if not record_id:
                issues.append(
                    WorkflowDatabaseIssue(
                        "record_id_missing",
                        f"{prefix}: отсутствует ID.",
                    )
                )
            elif record_id in record_ids:
                issues.append(
                    WorkflowDatabaseIssue(
                        "record_id_duplicate",
                        f"{prefix}: повторяется ID «{record_id}».",
                    )
                )
            else:
                record_ids.add(record_id)

            self._validate_enum(
                issues,
                prefix,
                "kind",
                record.get("kind"),
                BusinessRecordKind,
            )
            self._validate_enum(
                issues,
                prefix,
                "status",
                record.get("status"),
                BusinessStatus,
            )

            for field in ("tender_id", "title"):
                if not str(record.get(field, "")).strip():
                    issues.append(
                        WorkflowDatabaseIssue(
                            f"record_{field}_missing",
                            f"{prefix}: поле {field} не заполнено.",
                        )
                    )

            for field in ("total", "profit", "margin_percent"):
                try:
                    float(record.get(field, 0))
                except (TypeError, ValueError):
                    issues.append(
                        WorkflowDatabaseIssue(
                            f"record_{field}_invalid",
                            f"{prefix}: поле {field} должно быть числом.",
                        )
                    )

            if str(record.get("archived_at", "")).strip():
                archived_count += 1

        event_ids: set[str] = set()
        for index, event in enumerate(events, start=1):
            prefix = f"Событие {index}"
            if not isinstance(event, dict):
                issues.append(
                    WorkflowDatabaseIssue(
                        "event_not_object",
                        f"{prefix}: ожидается объект.",
                    )
                )
                continue

            event_id = str(event.get("id", "")).strip()
            if not event_id:
                issues.append(
                    WorkflowDatabaseIssue(
                        "event_id_missing",
                        f"{prefix}: отсутствует ID.",
                    )
                )
            elif event_id in event_ids:
                issues.append(
                    WorkflowDatabaseIssue(
                        "event_id_duplicate",
                        f"{prefix}: повторяется ID «{event_id}».",
                    )
                )
            else:
                event_ids.add(event_id)

            related_id = str(event.get("record_id", "")).strip()
            if related_id not in record_ids:
                issues.append(
                    WorkflowDatabaseIssue(
                        "event_orphan",
                        (f"{prefix}: связанная запись «{related_id}» не найдена."),
                    )
                )

            self._validate_enum(
                issues,
                prefix,
                "action",
                event.get("action"),
                BusinessAuditAction,
            )

            occurred_at = str(event.get("occurred_at", "")).strip()
            if not occurred_at:
                issues.append(
                    WorkflowDatabaseIssue(
                        "event_date_missing",
                        f"{prefix}: отсутствует дата.",
                    )
                )
            else:
                try:
                    datetime.fromisoformat(occurred_at)
                except ValueError:
                    issues.append(
                        WorkflowDatabaseIssue(
                            "event_date_invalid",
                            (f"{prefix}: неверная дата «{occurred_at}»."),
                        )
                    )

        if any(issue.code == "schema_newer" for issue in issues):
            status = WorkflowDatabaseHealthStatus.INCOMPATIBLE
        elif issues:
            status = WorkflowDatabaseHealthStatus.INVALID
        elif records or events:
            status = WorkflowDatabaseHealthStatus.HEALTHY
        else:
            status = WorkflowDatabaseHealthStatus.EMPTY

        return WorkflowDatabaseHealthReport(
            path=path,
            status=status,
            checked_at=checked_at,
            schema_version=schema_version,
            record_count=len(records),
            event_count=len(events),
            archived_count=archived_count,
            file_size=file_size,
            issues=tuple(issues),
            latest_valid_backup=latest_backup,
        )

    def recover_latest(
        self,
        repository: BusinessMetricsRepository,
        *,
        backup_directories: Sequence[str | Path],
        quarantine_directory: str | Path | None = None,
        recovered_at: datetime | None = None,
    ) -> WorkflowDatabaseRecoveryResult:
        report = self.inspect(
            repository,
            backup_directories=backup_directories,
        )
        latest = report.latest_valid_backup
        if latest is None:
            raise FileNotFoundError("Не найдена исправная резервная копия.")
        return self.recover_from_backup(
            repository,
            latest.path,
            backup_directories=backup_directories,
            quarantine_directory=quarantine_directory,
            recovered_at=recovered_at,
        )

    def recover_from_backup(
        self,
        repository: BusinessMetricsRepository,
        source: str | Path,
        *,
        backup_directories: Sequence[str | Path] = (),
        quarantine_directory: str | Path | None = None,
        recovered_at: datetime | None = None,
    ) -> WorkflowDatabaseRecoveryResult:
        timestamp = recovered_at or datetime.now()
        inspection = self.backup_service.inspect_backup(source)
        if not inspection.valid:
            raise ValueError(
                "Выбранная резервная копия повреждена:\n"
                + "\n".join(f"• {error}" for error in inspection.errors)
            )

        quarantine = self.quarantine_current(
            repository,
            directory=quarantine_directory,
            timestamp=timestamp,
        )
        restored: WorkflowBackupRestoreResult = self.backup_service.restore_backup(
            source,
            repository,
            restored_at=timestamp,
        )
        final_report = self.inspect(
            repository,
            backup_directories=backup_directories,
        )
        if final_report.requires_recovery:
            raise RuntimeError("После восстановления база не прошла диагностику.")

        return WorkflowDatabaseRecoveryResult(
            restored_from=Path(source),
            quarantine_path=quarantine,
            safety_backup=restored.safety_backup,
            report=final_report,
        )

    def initialize_empty(
        self,
        repository: BusinessMetricsRepository,
        *,
        backup_directories: Sequence[str | Path] = (),
        quarantine_directory: str | Path | None = None,
        initialized_at: datetime | None = None,
    ) -> WorkflowDatabaseRecoveryResult:
        timestamp = initialized_at or datetime.now()
        quarantine = self.quarantine_current(
            repository,
            directory=quarantine_directory,
            timestamp=timestamp,
        )
        repository.replace_payload(
            {
                "schema_version": repository.SCHEMA_VERSION,
                "updated_at": timestamp.isoformat(timespec="seconds"),
                "records": [],
                "events": [],
            }
        )
        final_report = self.inspect(
            repository,
            backup_directories=backup_directories,
        )
        return WorkflowDatabaseRecoveryResult(
            restored_from=None,
            quarantine_path=quarantine,
            safety_backup=None,
            report=final_report,
            initialized_empty=True,
        )

    def quarantine_current(
        self,
        repository: BusinessMetricsRepository,
        *,
        directory: str | Path | None = None,
        timestamp: datetime | None = None,
    ) -> Path | None:
        source = repository.path
        if not source.is_file():
            return None

        moment = timestamp or datetime.now()
        target_dir = (
            Path(directory).expanduser()
            if directory is not None
            else source.parent / "recovery" / "quarantine"
        )
        target_dir.mkdir(parents=True, exist_ok=True)

        base_name = f"{source.stem}_corrupted_{moment:%Y%m%d_%H%M%S}"
        destination = target_dir / f"{base_name}{source.suffix}"
        counter = 1
        while destination.exists():
            destination = target_dir / f"{base_name}_{counter}{source.suffix}"
            counter += 1

        shutil.copy2(source, destination)
        return destination

    def _latest_valid_backup(
        self,
        directories: Sequence[str | Path],
    ) -> WorkflowBackupEntry | None:
        """Find the newest valid backup without recursive disk scans.

        The page already passes both the regular backup directory and the
        automatic-backup directory. Scanning those exact folders is enough.
        Recursive ``rglob`` over a user-selected directory such as Documents
        or a drive root can make diagnostics appear frozen.
        """
        roots = self._unique_directories(directories)
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
                    is_candidate = (
                        path.is_file()
                        and path.suffix.lower() in self.catalog_service.SUPPORTED_SUFFIXES
                    )
                except OSError:
                    continue
                if not is_candidate:
                    continue
                candidates[str(path.resolve(strict=False)).casefold()] = path

        ordered = sorted(
            candidates.values(),
            key=self._safe_modified_time,
            reverse=True,
        )[: self.MAX_BACKUP_CANDIDATES]

        valid_entries: list[WorkflowBackupEntry] = []
        for path in ordered:
            try:
                entry = self.catalog_service.refresh_entry(
                    path,
                    managed_directories=roots,
                )
            except Exception:
                continue
            if entry.valid:
                valid_entries.append(entry)

        if not valid_entries:
            return None

        return max(
            valid_entries,
            key=lambda entry: (
                entry.created_timestamp,
                entry.modified_at,
                entry.path.name.lower(),
            ),
        )

    @staticmethod
    def _unique_directories(
        directories: Sequence[str | Path],
    ) -> tuple[Path, ...]:
        result: list[Path] = []
        seen: set[str] = set()

        for item in directories:
            path = Path(item).expanduser()
            identity = str(path.resolve(strict=False)).casefold()
            if identity in seen:
                continue
            seen.add(identity)
            result.append(path)

        return tuple(result)

    @staticmethod
    def _safe_modified_time(path: Path) -> int:
        try:
            return path.stat().st_mtime_ns
        except OSError:
            return 0

    @staticmethod
    def _validate_enum(
        issues: list[WorkflowDatabaseIssue],
        prefix: str,
        field: str,
        value: Any,
        enum_type,
    ) -> None:
        try:
            enum_type(value)
        except (TypeError, ValueError):
            issues.append(
                WorkflowDatabaseIssue(
                    f"{field}_invalid",
                    (f"{prefix}: неизвестное значение {field} «{value}»."),
                )
            )

    @staticmethod
    def _integer(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _failure_report(
        path: Path,
        checked_at: datetime,
        status: WorkflowDatabaseHealthStatus,
        code: str,
        message: str,
        latest_backup: WorkflowBackupEntry | None,
        *,
        file_size: int = 0,
    ) -> WorkflowDatabaseHealthReport:
        return WorkflowDatabaseHealthReport(
            path=path,
            status=status,
            checked_at=checked_at,
            file_size=file_size,
            issues=(WorkflowDatabaseIssue(code, message),),
            latest_valid_backup=latest_backup,
        )


__all__ = [
    "WorkflowDatabaseHealthReport",
    "WorkflowDatabaseHealthService",
    "WorkflowDatabaseHealthStatus",
    "WorkflowDatabaseIssue",
    "WorkflowDatabaseRecoveryResult",
]
