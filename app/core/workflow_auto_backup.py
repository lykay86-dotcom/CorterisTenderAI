"""Scheduled automatic backups for the business workflow store."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import json
from pathlib import Path
from threading import RLock
from typing import Any

from app.core.workflow_backup import (
    WorkflowBackupCreateResult,
    WorkflowBackupService,
)
from app.repositories.business_metrics import BusinessMetricsRepository


@dataclass(frozen=True, slots=True)
class WorkflowAutoBackupSettings:
    """Persistent schedule and retention preferences."""

    enabled: bool = True
    interval_hours: int = 24
    retention_count: int = 10
    directory: str = ""
    last_success_at: str = ""
    last_attempt_at: str = ""
    last_error: str = ""

    @property
    def last_success_timestamp(self) -> datetime | None:
        return _parse_datetime(self.last_success_at)


@dataclass(frozen=True, slots=True)
class WorkflowAutoBackupRunResult:
    """Outcome of one schedule check or forced backup."""

    executed: bool
    settings: WorkflowAutoBackupSettings
    backup: WorkflowBackupCreateResult | None = None
    removed_paths: tuple[Path, ...] = ()
    skipped_reason: str = ""
    next_run_at: datetime | None = None


class WorkflowAutoBackupService:
    """Persist schedule, create due backups and enforce retention."""

    SETTINGS_SCHEMA_VERSION = 1
    AUTOMATIC_PREFIX = "CORTERIS_auto_"
    SETTINGS_FILENAME = "workflow_auto_backup_settings.json"
    MIN_INTERVAL_HOURS = 1
    MAX_INTERVAL_HOURS = 24 * 30
    MIN_RETENTION = 1
    MAX_RETENTION = 100

    def __init__(
        self,
        settings_path: str | Path,
        *,
        backup_service: WorkflowBackupService | None = None,
    ) -> None:
        self.settings_path = Path(settings_path).expanduser()
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.backup_service = backup_service or WorkflowBackupService()
        self._lock = RLock()

    @classmethod
    def for_repository(
        cls,
        repository: BusinessMetricsRepository,
        *,
        backup_service: WorkflowBackupService | None = None,
    ) -> "WorkflowAutoBackupService":
        return cls(
            repository.path.parent / cls.SETTINGS_FILENAME,
            backup_service=backup_service,
        )

    def load_settings(self) -> WorkflowAutoBackupSettings:
        with self._lock:
            if not self.settings_path.exists():
                return WorkflowAutoBackupSettings()

            try:
                payload = json.loads(
                    self.settings_path.read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                return WorkflowAutoBackupSettings(
                    last_error=(
                        "Не удалось прочитать настройки автоматического "
                        "резервного копирования. Использованы значения "
                        "по умолчанию."
                    )
                )

            if not isinstance(payload, dict):
                return WorkflowAutoBackupSettings(
                    last_error="Файл настроек имеет неверный формат."
                )

            return self._validated_settings(payload)

    def save_settings(
        self,
        settings: WorkflowAutoBackupSettings,
    ) -> WorkflowAutoBackupSettings:
        normalized = self._validated_settings(asdict(settings))
        with self._lock:
            self._write_settings_unlocked(normalized)
        return normalized

    def update_preferences(
        self,
        *,
        enabled: bool,
        interval_hours: int,
        retention_count: int,
        directory: str | Path = "",
    ) -> WorkflowAutoBackupSettings:
        current = self.load_settings()
        updated = WorkflowAutoBackupSettings(
            enabled=bool(enabled),
            interval_hours=int(interval_hours),
            retention_count=int(retention_count),
            directory=str(directory).strip(),
            last_success_at=current.last_success_at,
            last_attempt_at=current.last_attempt_at,
            last_error=current.last_error,
        )
        return self.save_settings(updated)

    def backup_directory(
        self,
        repository: BusinessMetricsRepository,
        settings: WorkflowAutoBackupSettings | None = None,
    ) -> Path:
        current = settings or self.load_settings()
        if current.directory.strip():
            return Path(current.directory).expanduser()
        return repository.path.parent / "backups" / "automatic"

    def next_run_at(
        self,
        settings: WorkflowAutoBackupSettings | None = None,
        *,
        now: datetime | None = None,
    ) -> datetime | None:
        current = settings or self.load_settings()
        if not current.enabled:
            return None

        last_success = current.last_success_timestamp
        if last_success is None:
            return now or datetime.now()
        return last_success + timedelta(hours=current.interval_hours)

    def is_due(
        self,
        settings: WorkflowAutoBackupSettings | None = None,
        *,
        now: datetime | None = None,
    ) -> bool:
        current = settings or self.load_settings()
        if not current.enabled:
            return False
        current_time = now or datetime.now()
        due_at = self.next_run_at(current, now=current_time)
        return due_at is not None and current_time >= due_at

    def run_if_due(
        self,
        repository: BusinessMetricsRepository,
        *,
        now: datetime | None = None,
        force: bool = False,
    ) -> WorkflowAutoBackupRunResult:
        timestamp = now or datetime.now()
        with self._lock:
            settings = self.load_settings()
            if not force and not settings.enabled:
                return WorkflowAutoBackupRunResult(
                    executed=False,
                    settings=settings,
                    skipped_reason="Автоматическое копирование отключено.",
                    next_run_at=None,
                )

            if not force and not self.is_due(settings, now=timestamp):
                return WorkflowAutoBackupRunResult(
                    executed=False,
                    settings=settings,
                    skipped_reason="Срок следующей копии ещё не наступил.",
                    next_run_at=self.next_run_at(settings, now=timestamp),
                )

            directory = self.backup_directory(repository, settings)
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / (
                f"{self.AUTOMATIC_PREFIX}"
                f"{timestamp:%Y%m%d_%H%M%S}"
                f"{self.backup_service.DEFAULT_EXTENSION}"
            )

            attempted = WorkflowAutoBackupSettings(
                **{
                    **asdict(settings),
                    "last_attempt_at": timestamp.isoformat(
                        timespec="seconds"
                    ),
                }
            )
            self._write_settings_unlocked(attempted)

            try:
                backup = self.backup_service.create_backup(
                    repository,
                    target,
                    created_at=timestamp,
                )
                removed = self.prune_backups(
                    directory,
                    retention_count=settings.retention_count,
                )
                successful = WorkflowAutoBackupSettings(
                    enabled=settings.enabled,
                    interval_hours=settings.interval_hours,
                    retention_count=settings.retention_count,
                    directory=settings.directory,
                    last_success_at=timestamp.isoformat(
                        timespec="seconds"
                    ),
                    last_attempt_at=timestamp.isoformat(
                        timespec="seconds"
                    ),
                    last_error="",
                )
                self._write_settings_unlocked(successful)
                return WorkflowAutoBackupRunResult(
                    executed=True,
                    settings=successful,
                    backup=backup,
                    removed_paths=removed,
                    next_run_at=self.next_run_at(
                        successful,
                        now=timestamp,
                    ),
                )
            except Exception as exc:
                failed = WorkflowAutoBackupSettings(
                    enabled=settings.enabled,
                    interval_hours=settings.interval_hours,
                    retention_count=settings.retention_count,
                    directory=settings.directory,
                    last_success_at=settings.last_success_at,
                    last_attempt_at=timestamp.isoformat(
                        timespec="seconds"
                    ),
                    last_error=str(exc),
                )
                self._write_settings_unlocked(failed)
                raise

    def prune_backups(
        self,
        directory: str | Path,
        *,
        retention_count: int,
    ) -> tuple[Path, ...]:
        keep = self._validated_retention(retention_count)
        folder = Path(directory).expanduser()
        if not folder.exists():
            return ()

        candidates = sorted(
            (
                path
                for path in folder.glob(
                    f"{self.AUTOMATIC_PREFIX}*"
                    f"{self.backup_service.DEFAULT_EXTENSION}"
                )
                if path.is_file()
            ),
            key=lambda path: (
                path.stat().st_mtime_ns,
                path.name,
            ),
            reverse=True,
        )

        removed: list[Path] = []
        for path in candidates[keep:]:
            path.unlink(missing_ok=True)
            removed.append(path)
        return tuple(removed)

    def _validated_settings(
        self,
        payload: dict[str, Any],
    ) -> WorkflowAutoBackupSettings:
        interval = self._validated_interval(
            payload.get("interval_hours", 24)
        )
        retention = self._validated_retention(
            payload.get("retention_count", 10)
        )
        return WorkflowAutoBackupSettings(
            enabled=bool(payload.get("enabled", True)),
            interval_hours=interval,
            retention_count=retention,
            directory=str(payload.get("directory", "")).strip(),
            last_success_at=self._valid_datetime_text(
                payload.get("last_success_at", "")
            ),
            last_attempt_at=self._valid_datetime_text(
                payload.get("last_attempt_at", "")
            ),
            last_error=str(payload.get("last_error", "")).strip(),
        )

    def _write_settings_unlocked(
        self,
        settings: WorkflowAutoBackupSettings,
    ) -> None:
        payload = {
            "schema_version": self.SETTINGS_SCHEMA_VERSION,
            **asdict(settings),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        temporary = self.settings_path.with_suffix(
            self.settings_path.suffix + ".tmp"
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
            temporary.replace(self.settings_path)
        finally:
            temporary.unlink(missing_ok=True)

    def _validated_interval(self, value: Any) -> int:
        try:
            interval = int(value)
        except (TypeError, ValueError):
            interval = 24
        return max(
            self.MIN_INTERVAL_HOURS,
            min(self.MAX_INTERVAL_HOURS, interval),
        )

    def _validated_retention(self, value: Any) -> int:
        try:
            retention = int(value)
        except (TypeError, ValueError):
            retention = 10
        return max(
            self.MIN_RETENTION,
            min(self.MAX_RETENTION, retention),
        )

    @staticmethod
    def _valid_datetime_text(value: Any) -> str:
        text = str(value or "").strip()
        return text if not text or _parse_datetime(text) else ""


def _parse_datetime(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


__all__ = [
    "WorkflowAutoBackupRunResult",
    "WorkflowAutoBackupService",
    "WorkflowAutoBackupSettings",
]
