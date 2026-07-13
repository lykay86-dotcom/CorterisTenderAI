"""Safe-mode launch guard for repeated application crashes."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import json
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class LaunchRecord:
    launch_id: str
    started_at: str
    finished_at: str = ""
    outcome: str = "running"
    crash_report: str = ""
    details: str = ""

    @property
    def started_timestamp(self) -> datetime | None:
        try:
            return datetime.fromisoformat(self.started_at)
        except (TypeError, ValueError):
            return None


@dataclass(frozen=True, slots=True)
class SafeModeDecision:
    enabled: bool
    reason: str
    recent_crashes: int
    threshold: int
    window_minutes: int
    records: tuple[LaunchRecord, ...]


class LaunchGuardService:
    """Persist launch outcomes and enable safe mode after crash loops."""

    SCHEMA_VERSION = 1
    DEFAULT_CRASH_THRESHOLD = 3
    DEFAULT_WINDOW_MINUTES = 30
    MAX_RECORDS = 50

    def __init__(
        self,
        path: str | Path,
        *,
        crash_threshold: int = DEFAULT_CRASH_THRESHOLD,
        window_minutes: int = DEFAULT_WINDOW_MINUTES,
        max_records: int = MAX_RECORDS,
    ) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.crash_threshold = max(2, int(crash_threshold))
        self.window_minutes = max(1, int(window_minutes))
        self.max_records = max(self.crash_threshold, int(max_records))
        self._lock = RLock()
        self._current_launch_id = ""

    @property
    def current_launch_id(self) -> str:
        return self._current_launch_id

    def evaluate(
        self,
        *,
        now: datetime | None = None,
        force_safe_mode: bool = False,
    ) -> SafeModeDecision:
        moment = now or datetime.now()
        records = self.list_records()

        cutoff = moment - timedelta(minutes=self.window_minutes)
        recent_crashes = [
            record
            for record in records
            if record.outcome in {"crashed", "interrupted"}
            and record.started_timestamp is not None
            and record.started_timestamp >= cutoff
        ]

        enabled = force_safe_mode or (len(recent_crashes) >= self.crash_threshold)
        if force_safe_mode:
            reason = "Безопасный режим запрошен вручную."
        elif enabled:
            reason = (
                f"За последние {self.window_minutes} мин. обнаружено "
                f"{len(recent_crashes)} аварийных запусков."
            )
        else:
            reason = ""

        return SafeModeDecision(
            enabled=enabled,
            reason=reason,
            recent_crashes=len(recent_crashes),
            threshold=self.crash_threshold,
            window_minutes=self.window_minutes,
            records=tuple(records),
        )

    def begin_launch(
        self,
        *,
        started_at: datetime | None = None,
    ) -> LaunchRecord:
        moment = started_at or datetime.now()
        launch_id = uuid4().hex

        with self._lock:
            records = self._load_unlocked()
            records = [
                self._mark_interrupted(record, moment) if record.outcome == "running" else record
                for record in records
            ]

            record = LaunchRecord(
                launch_id=launch_id,
                started_at=moment.isoformat(timespec="seconds"),
            )
            records.append(record)
            self._current_launch_id = launch_id
            self._write_unlocked(records[-self.max_records :])
            return record

    def mark_clean_exit(
        self,
        *,
        finished_at: datetime | None = None,
        details: str = "",
    ) -> None:
        self._finish_current(
            outcome="clean",
            finished_at=finished_at,
            details=details,
        )

    def mark_crash(
        self,
        *,
        crash_report: str | Path | None = None,
        finished_at: datetime | None = None,
        details: str = "",
    ) -> None:
        self._finish_current(
            outcome="crashed",
            finished_at=finished_at,
            crash_report=str(crash_report or ""),
            details=details,
        )

    def mark_safe_mode_exit(
        self,
        *,
        finished_at: datetime | None = None,
        details: str = "",
    ) -> None:
        self._finish_current(
            outcome="safe_mode",
            finished_at=finished_at,
            details=details,
        )

    def reset_history(self) -> None:
        with self._lock:
            self._current_launch_id = ""
            self._write_unlocked([])

    def list_records(self) -> list[LaunchRecord]:
        with self._lock:
            records = self._load_unlocked()
        records.sort(
            key=lambda item: (
                item.started_timestamp or datetime.min,
                item.launch_id,
            ),
            reverse=True,
        )
        return records

    def _finish_current(
        self,
        *,
        outcome: str,
        finished_at: datetime | None,
        crash_report: str = "",
        details: str = "",
    ) -> None:
        launch_id = self._current_launch_id
        if not launch_id:
            return

        moment = finished_at or datetime.now()
        with self._lock:
            records = self._load_unlocked()
            updated: list[LaunchRecord] = []
            for record in records:
                if record.launch_id != launch_id:
                    updated.append(record)
                    continue
                updated.append(
                    LaunchRecord(
                        launch_id=record.launch_id,
                        started_at=record.started_at,
                        finished_at=moment.isoformat(timespec="seconds"),
                        outcome=outcome,
                        crash_report=crash_report,
                        details=details,
                    )
                )
            self._write_unlocked(updated[-self.max_records :])

    @staticmethod
    def _mark_interrupted(
        record: LaunchRecord,
        moment: datetime,
    ) -> LaunchRecord:
        return LaunchRecord(
            launch_id=record.launch_id,
            started_at=record.started_at,
            finished_at=moment.isoformat(timespec="seconds"),
            outcome="interrupted",
            crash_report=record.crash_report,
            details=(
                record.details or "Предыдущий запуск завершился без отметки о штатном закрытии."
            ),
        )

    def _load_unlocked(self) -> list[LaunchRecord]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return []

        if not isinstance(payload, dict):
            return []
        raw_records = payload.get("records", [])
        if not isinstance(raw_records, list):
            return []

        records: list[LaunchRecord] = []
        for item in raw_records:
            if not isinstance(item, dict):
                continue
            try:
                record = LaunchRecord(
                    launch_id=str(item.get("launch_id", "")).strip(),
                    started_at=str(item.get("started_at", "")).strip(),
                    finished_at=str(item.get("finished_at", "")).strip(),
                    outcome=str(item.get("outcome", "running")).strip(),
                    crash_report=str(item.get("crash_report", "")).strip(),
                    details=str(item.get("details", "")).strip(),
                )
            except (TypeError, ValueError):
                continue
            if record.launch_id and record.started_at:
                records.append(record)
        return records[-self.max_records :]

    def _write_unlocked(
        self,
        records: list[LaunchRecord],
    ) -> None:
        payload: dict[str, Any] = {
            "schema_version": self.SCHEMA_VERSION,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "records": [asdict(record) for record in records],
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
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


__all__ = [
    "LaunchGuardService",
    "LaunchRecord",
    "SafeModeDecision",
]
