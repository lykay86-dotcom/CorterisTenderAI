"""System health journal and aggregated application status."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
import json
from pathlib import Path
from threading import RLock
from typing import Any, Iterable, Sequence
from uuid import uuid4

from app.core.workflow_auto_backup import WorkflowAutoBackupService
from app.core.workflow_backup_catalog import WorkflowBackupCatalogService
from app.core.workflow_database_health import (
    WorkflowDatabaseHealthReport,
    WorkflowDatabaseHealthService,
    WorkflowDatabaseHealthStatus,
)
from app.repositories.business_metrics import BusinessMetricsRepository


class SystemHealthSeverity(StrEnum):
    SUCCESS = "success"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class SystemHealthEvent:
    id: str
    occurred_at: str
    severity: SystemHealthSeverity
    component: str
    title: str
    details: str = ""

    @property
    def timestamp(self) -> datetime | None:
        try:
            return datetime.fromisoformat(self.occurred_at)
        except (TypeError, ValueError):
            return None


@dataclass(frozen=True, slots=True)
class SystemHealthSnapshot:
    checked_at: datetime
    database: WorkflowDatabaseHealthReport
    auto_backup_enabled: bool
    auto_backup_interval_hours: int
    auto_backup_retention_count: int
    auto_backup_last_success_at: str
    auto_backup_last_error: str
    backup_total: int
    backup_valid: int
    backup_invalid: int
    latest_backup_at: datetime | None
    journal_count: int
    severity: SystemHealthSeverity
    issues: tuple[str, ...]

    @property
    def status_label(self) -> str:
        return {
            SystemHealthSeverity.SUCCESS: "Система исправна",
            SystemHealthSeverity.INFO: "Система работает",
            SystemHealthSeverity.WARNING: "Требуется внимание",
            SystemHealthSeverity.ERROR: "Обнаружены ошибки",
        }[self.severity]


class SystemHealthJournal:
    """Small atomic JSON journal for diagnostics and service events."""

    SCHEMA_VERSION = 1
    MAX_EVENTS = 500

    def __init__(
        self,
        path: str | Path,
        *,
        max_events: int = MAX_EVENTS,
    ) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_events = max(10, int(max_events))
        self._lock = RLock()

    @classmethod
    def for_repository(
        cls,
        repository: BusinessMetricsRepository,
    ) -> "SystemHealthJournal":
        return cls(
            repository.path.parent / "system_health_journal.json"
        )

    def record(
        self,
        *,
        severity: SystemHealthSeverity | str,
        component: str,
        title: str,
        details: str = "",
        occurred_at: datetime | None = None,
    ) -> SystemHealthEvent:
        event = SystemHealthEvent(
            id=uuid4().hex,
            occurred_at=(occurred_at or datetime.now()).isoformat(
                timespec="seconds"
            ),
            severity=SystemHealthSeverity(severity),
            component=str(component).strip() or "system",
            title=str(title).strip() or "Системное событие",
            details=str(details).strip(),
        )

        with self._lock:
            events = self._load_events_unlocked()
            events.append(event)
            events = events[-self.max_events :]
            self._write_events_unlocked(events)
        return event

    def list_events(
        self,
        *,
        limit: int | None = 100,
    ) -> tuple[SystemHealthEvent, ...]:
        with self._lock:
            events = self._load_events_unlocked()

        events.sort(
            key=lambda event: (
                event.timestamp or datetime.min,
                event.id,
            ),
            reverse=True,
        )
        if limit is None:
            return tuple(events)
        return tuple(events[: max(0, int(limit))])

    def count(self) -> int:
        with self._lock:
            return len(self._load_events_unlocked())

    def clear(self) -> None:
        with self._lock:
            self._write_events_unlocked([])

    def export_text(
        self,
        target: str | Path,
    ) -> Path:
        destination = Path(target).expanduser()
        if destination.suffix.lower() != ".txt":
            destination = destination.with_suffix(".txt")
        destination.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            "CORTERIS Tender AI — журнал состояния системы",
            "=" * 58,
            "",
        ]
        for event in self.list_events(limit=None):
            timestamp = event.timestamp
            time_text = (
                timestamp.strftime("%d.%m.%Y %H:%M:%S")
                if timestamp is not None
                else event.occurred_at
            )
            lines.append(
                f"[{time_text}] [{event.severity.value.upper()}] "
                f"[{event.component}] {event.title}"
            )
            if event.details:
                lines.append(f"  {event.details}")
            lines.append("")

        destination.write_text(
            "\n".join(lines),
            encoding="utf-8-sig",
        )
        return destination

    def _load_events_unlocked(self) -> list[SystemHealthEvent]:
        if not self.path.exists():
            return []

        try:
            payload = json.loads(
                self.path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return []

        if not isinstance(payload, dict):
            return []
        raw_events = payload.get("events", [])
        if not isinstance(raw_events, list):
            return []

        events: list[SystemHealthEvent] = []
        for item in raw_events:
            if not isinstance(item, dict):
                continue
            try:
                event = SystemHealthEvent(
                    id=str(item.get("id", "")).strip()
                    or uuid4().hex,
                    occurred_at=str(
                        item.get("occurred_at", "")
                    ).strip(),
                    severity=SystemHealthSeverity(
                        item.get("severity", "info")
                    ),
                    component=str(
                        item.get("component", "system")
                    ).strip()
                    or "system",
                    title=str(
                        item.get("title", "Системное событие")
                    ).strip()
                    or "Системное событие",
                    details=str(item.get("details", "")).strip(),
                )
            except (TypeError, ValueError):
                continue
            events.append(event)
        return events[-self.max_events :]

    def _write_events_unlocked(
        self,
        events: Sequence[SystemHealthEvent],
    ) -> None:
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "updated_at": datetime.now().isoformat(
                timespec="seconds"
            ),
            "events": [
                {
                    **asdict(event),
                    "severity": event.severity.value,
                }
                for event in events
            ],
        }
        temporary = self.path.with_suffix(
            self.path.suffix + ".tmp"
        )
        try:
            temporary.write_text(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)


class SystemHealthService:
    """Aggregate database, backup and journal health into one snapshot."""

    MAX_BACKUP_FILES = 200

    def collect(
        self,
        *,
        repository: BusinessMetricsRepository,
        database_health_service: WorkflowDatabaseHealthService,
        auto_backup_service: WorkflowAutoBackupService,
        backup_catalog_service: WorkflowBackupCatalogService,
        journal: SystemHealthJournal,
        backup_directories: Sequence[str | Path],
    ) -> SystemHealthSnapshot:
        checked_at = datetime.now()
        database = database_health_service.inspect(
            repository,
            backup_directories=backup_directories,
        )
        settings = auto_backup_service.load_settings()
        backup_entries = self._backup_entries(
            backup_catalog_service,
            backup_directories,
        )

        valid_entries = [
            entry for entry in backup_entries if entry.valid
        ]
        invalid_entries = [
            entry for entry in backup_entries if not entry.valid
        ]
        latest_backup_at = (
            max(
                (
                    entry.created_timestamp
                    for entry in valid_entries
                ),
                default=None,
            )
        )

        issues: list[str] = []
        severity = SystemHealthSeverity.SUCCESS

        if database.requires_recovery:
            severity = SystemHealthSeverity.ERROR
            issues.append(
                f"База бизнес-процессов: {database.status_label}."
            )
        elif database.status == WorkflowDatabaseHealthStatus.MISSING:
            severity = SystemHealthSeverity.INFO
            issues.append(
                "Файл базы появится после создания первой записи."
            )

        if settings.last_error:
            severity = self._maximum(
                severity,
                SystemHealthSeverity.WARNING,
            )
            issues.append(
                "Последняя ошибка автокопирования: "
                f"{settings.last_error}"
            )

        if invalid_entries:
            severity = self._maximum(
                severity,
                SystemHealthSeverity.WARNING,
            )
            issues.append(
                f"Повреждённых резервных копий: "
                f"{len(invalid_entries)}."
            )

        if (
            database.record_count > 0
            and not valid_entries
        ):
            severity = self._maximum(
                severity,
                SystemHealthSeverity.WARNING,
            )
            issues.append(
                "Для рабочей базы не найдена исправная резервная копия."
            )

        if not settings.enabled:
            severity = self._maximum(
                severity,
                SystemHealthSeverity.INFO,
            )
            issues.append(
                "Автоматическое резервное копирование отключено."
            )

        return SystemHealthSnapshot(
            checked_at=checked_at,
            database=database,
            auto_backup_enabled=settings.enabled,
            auto_backup_interval_hours=settings.interval_hours,
            auto_backup_retention_count=settings.retention_count,
            auto_backup_last_success_at=settings.last_success_at,
            auto_backup_last_error=settings.last_error,
            backup_total=len(backup_entries),
            backup_valid=len(valid_entries),
            backup_invalid=len(invalid_entries),
            latest_backup_at=latest_backup_at,
            journal_count=journal.count(),
            severity=severity,
            issues=tuple(issues),
        )

    def _backup_entries(
        self,
        catalog: WorkflowBackupCatalogService,
        directories: Sequence[str | Path],
    ) -> list:
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
                    supported = (
                        path.is_file()
                        and path.suffix.lower()
                        in catalog.SUPPORTED_SUFFIXES
                    )
                except OSError:
                    continue
                if not supported:
                    continue
                candidates[
                    str(path.resolve(strict=False)).casefold()
                ] = path

        ordered = sorted(
            candidates.values(),
            key=self._safe_modified_time,
            reverse=True,
        )[: self.MAX_BACKUP_FILES]

        entries = []
        for path in ordered:
            try:
                entries.append(
                    catalog.refresh_entry(
                        path,
                        managed_directories=roots,
                    )
                )
            except Exception:
                continue
        return entries

    @staticmethod
    def _unique_directories(
        directories: Iterable[str | Path],
    ) -> tuple[Path, ...]:
        result: list[Path] = []
        seen: set[str] = set()
        for item in directories:
            path = Path(item).expanduser()
            identity = str(
                path.resolve(strict=False)
            ).casefold()
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
    def _maximum(
        left: SystemHealthSeverity,
        right: SystemHealthSeverity,
    ) -> SystemHealthSeverity:
        order = {
            SystemHealthSeverity.SUCCESS: 0,
            SystemHealthSeverity.INFO: 1,
            SystemHealthSeverity.WARNING: 2,
            SystemHealthSeverity.ERROR: 3,
        }
        return left if order[left] >= order[right] else right


__all__ = [
    "SystemHealthEvent",
    "SystemHealthJournal",
    "SystemHealthService",
    "SystemHealthSeverity",
    "SystemHealthSnapshot",
]
