"""Persistent in-process scheduling rules for Corteris Tender Collector."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, time, timedelta
from enum import StrEnum
import json
from pathlib import Path
from threading import RLock
from typing import Any, Mapping


class CollectorScheduleFrequency(StrEnum):
    EVERY_30_MINUTES = "every_30_minutes"
    HOURLY = "hourly"
    EVERY_3_HOURS = "every_3_hours"
    DAILY = "daily"


@dataclass(frozen=True, slots=True)
class CollectorScheduleSettings:
    """User-controlled recurring collector schedule."""

    enabled: bool = False
    profile_id: str = ""
    provider_ids: tuple[str, ...] = ()
    frequency: CollectorScheduleFrequency = (
        CollectorScheduleFrequency.HOURLY
    )
    daily_time: str = "09:00"
    run_on_startup: bool = False
    notify_new: bool = True
    notify_changed: bool = True
    notify_failures: bool = True

    def __post_init__(self) -> None:
        normalized_profile = self.profile_id.strip().casefold()
        normalized_providers = tuple(
            dict.fromkeys(
                item.strip().casefold()
                for item in self.provider_ids
                if item.strip()
            )
        )
        object.__setattr__(self, "profile_id", normalized_profile)
        object.__setattr__(
            self,
            "provider_ids",
            normalized_providers,
        )
        if not isinstance(
            self.frequency,
            CollectorScheduleFrequency,
        ):
            object.__setattr__(
                self,
                "frequency",
                CollectorScheduleFrequency(
                    str(self.frequency)
                ),
            )
        _parse_daily_time(self.daily_time)
        if self.enabled and not self.profile_id:
            raise ValueError(
                "Для включённого планировщика нужен профиль."
            )
        if self.enabled and not self.provider_ids:
            raise ValueError(
                "Для включённого планировщика нужен источник."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "profile_id": self.profile_id,
            "provider_ids": list(self.provider_ids),
            "frequency": self.frequency.value,
            "daily_time": self.daily_time,
            "run_on_startup": self.run_on_startup,
            "notify_new": self.notify_new,
            "notify_changed": self.notify_changed,
            "notify_failures": self.notify_failures,
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
    ) -> "CollectorScheduleSettings":
        raw_providers = payload.get("provider_ids", ())
        if not isinstance(raw_providers, (list, tuple)):
            raw_providers = ()
        try:
            frequency = CollectorScheduleFrequency(
                str(
                    payload.get(
                        "frequency",
                        CollectorScheduleFrequency.HOURLY.value,
                    )
                )
            )
        except ValueError:
            frequency = CollectorScheduleFrequency.HOURLY
        return cls(
            enabled=bool(payload.get("enabled", False)),
            profile_id=str(payload.get("profile_id", "")),
            provider_ids=tuple(
                str(item) for item in raw_providers
            ),
            frequency=frequency,
            daily_time=str(
                payload.get("daily_time", "09:00")
            ),
            run_on_startup=bool(
                payload.get("run_on_startup", False)
            ),
            notify_new=bool(
                payload.get("notify_new", True)
            ),
            notify_changed=bool(
                payload.get("notify_changed", True)
            ),
            notify_failures=bool(
                payload.get("notify_failures", True)
            ),
        )


@dataclass(frozen=True, slots=True)
class CollectorScheduleState:
    """Durable operational state of the scheduler."""

    last_started_at: str = ""
    last_completed_at: str = ""
    next_run_at: str = ""
    last_status: str = "idle"
    last_error: str = ""
    busy_skip_count: int = 0

    def __post_init__(self) -> None:
        if self.busy_skip_count < 0:
            raise ValueError(
                "busy_skip_count must be non-negative"
            )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
    ) -> "CollectorScheduleState":
        return cls(
            last_started_at=str(
                payload.get("last_started_at", "")
            ),
            last_completed_at=str(
                payload.get("last_completed_at", "")
            ),
            next_run_at=str(
                payload.get("next_run_at", "")
            ),
            last_status=str(
                payload.get("last_status", "idle")
            ),
            last_error=str(
                payload.get("last_error", "")
            ),
            busy_skip_count=max(
                0,
                int(payload.get("busy_skip_count", 0)),
            ),
        )


@dataclass(frozen=True, slots=True)
class ScheduledCollectorRequest:
    profile_id: str
    provider_ids: tuple[str, ...]
    reason: str
    due_at: str

    def __post_init__(self) -> None:
        if not self.profile_id.strip():
            raise ValueError("profile_id must not be empty")
        if not self.provider_ids:
            raise ValueError("provider_ids must not be empty")


class CollectorScheduleRepository:
    """Atomically persist schedule and state without secrets."""

    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self._lock = RLock()

    def load(
        self,
    ) -> tuple[
        CollectorScheduleSettings,
        CollectorScheduleState,
    ]:
        with self._lock:
            if not self.path.is_file():
                return (
                    CollectorScheduleSettings(),
                    CollectorScheduleState(),
                )
            try:
                payload = json.loads(
                    self.path.read_text(encoding="utf-8")
                )
            except (
                OSError,
                TypeError,
                json.JSONDecodeError,
                ValueError,
            ):
                return (
                    CollectorScheduleSettings(),
                    CollectorScheduleState(),
                )
            if not isinstance(payload, dict):
                return (
                    CollectorScheduleSettings(),
                    CollectorScheduleState(),
                )
            raw_settings = payload.get("settings", {})
            raw_state = payload.get("state", {})
            if not isinstance(raw_settings, dict):
                raw_settings = {}
            if not isinstance(raw_state, dict):
                raw_state = {}
            try:
                settings = (
                    CollectorScheduleSettings.from_dict(
                        raw_settings
                    )
                )
            except ValueError:
                settings = CollectorScheduleSettings()
            try:
                state = CollectorScheduleState.from_dict(
                    raw_state
                )
            except (ValueError, TypeError):
                state = CollectorScheduleState()
            return settings, state

    def save(
        self,
        settings: CollectorScheduleSettings,
        state: CollectorScheduleState,
    ) -> None:
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "settings": settings.to_dict(),
            "state": state.to_dict(),
        }
        with self._lock:
            self.path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            temporary = self.path.with_suffix(
                self.path.suffix + ".tmp"
            )
            temporary.write_text(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            temporary.replace(self.path)


class CollectorScheduler:
    """Compute due runs and prevent overlapping scheduled starts."""

    def __init__(
        self,
        repository: CollectorScheduleRepository,
    ) -> None:
        self.repository = repository
        self._startup_consumed = False

    def snapshot(
        self,
    ) -> tuple[
        CollectorScheduleSettings,
        CollectorScheduleState,
    ]:
        return self.repository.load()

    def update_settings(
        self,
        settings: CollectorScheduleSettings,
        *,
        now: datetime | None = None,
    ) -> CollectorScheduleState:
        current = _local_now(now)
        _, old_state = self.repository.load()
        next_value = (
            _next_run(settings, current).isoformat(
                timespec="seconds"
            )
            if settings.enabled
            else ""
        )
        state = replace(
            old_state,
            next_run_at=next_value,
            last_status=(
                old_state.last_status
                if settings.enabled
                else "disabled"
            ),
            last_error="",
        )
        self.repository.save(settings, state)
        return state

    def startup_request(
        self,
        *,
        now: datetime | None = None,
    ) -> ScheduledCollectorRequest | None:
        if self._startup_consumed:
            return None
        self._startup_consumed = True
        settings, _ = self.repository.load()
        if not settings.enabled or not settings.run_on_startup:
            return None
        current = _local_now(now)
        return ScheduledCollectorRequest(
            profile_id=settings.profile_id,
            provider_ids=settings.provider_ids,
            reason="startup",
            due_at=current.isoformat(timespec="seconds"),
        )

    def poll(
        self,
        *,
        now: datetime | None = None,
        busy: bool = False,
        freshness_due_at: str = "",
    ) -> ScheduledCollectorRequest | None:
        current = _local_now(now)
        settings, state = self.repository.load()
        if not settings.enabled:
            return None

        due = _parse_datetime(state.next_run_at)
        if due is None:
            due = _next_run(settings, current)
            state = replace(
                state,
                next_run_at=due.isoformat(
                    timespec="seconds"
                ),
            )
            self.repository.save(settings, state)

        freshness_due = _parse_datetime(freshness_due_at)
        reason = "scheduled"
        effective_due = due
        if freshness_due is not None and freshness_due < effective_due:
            effective_due = freshness_due
            reason = "freshness_due"

        if current < effective_due:
            return None

        if busy:
            if state.last_status != "deferred_busy":
                self.repository.save(
                    settings,
                    replace(
                        state,
                        last_status="deferred_busy",
                        busy_skip_count=(
                            state.busy_skip_count + 1
                        ),
                    ),
                )
            return None

        return ScheduledCollectorRequest(
            profile_id=settings.profile_id,
            provider_ids=settings.provider_ids,
            reason=reason,
            due_at=effective_due.isoformat(timespec="seconds"),
        )

    def mark_started(
        self,
        request: ScheduledCollectorRequest,
        *,
        now: datetime | None = None,
    ) -> CollectorScheduleState:
        current = _local_now(now)
        settings, state = self.repository.load()
        next_value = (
            _next_run(settings, current).isoformat(
                timespec="seconds"
            )
            if settings.enabled
            else ""
        )
        state = replace(
            state,
            last_started_at=current.isoformat(
                timespec="seconds"
            ),
            next_run_at=next_value,
            last_status=f"running:{request.reason}",
            last_error="",
        )
        self.repository.save(settings, state)
        return state

    def mark_finished(
        self,
        status: str,
        *,
        error: str = "",
        now: datetime | None = None,
    ) -> CollectorScheduleState:
        current = _local_now(now)
        settings, state = self.repository.load()
        state = replace(
            state,
            last_completed_at=current.isoformat(
                timespec="seconds"
            ),
            last_status=status.strip() or "completed",
            last_error=error.strip(),
        )
        self.repository.save(settings, state)
        return state


def _next_run(
    settings: CollectorScheduleSettings,
    now: datetime,
) -> datetime:
    if (
        settings.frequency
        == CollectorScheduleFrequency.EVERY_30_MINUTES
    ):
        return now + timedelta(minutes=30)
    if settings.frequency == CollectorScheduleFrequency.HOURLY:
        return now + timedelta(hours=1)
    if (
        settings.frequency
        == CollectorScheduleFrequency.EVERY_3_HOURS
    ):
        return now + timedelta(hours=3)

    daily = _parse_daily_time(settings.daily_time)
    candidate = now.replace(
        hour=daily.hour,
        minute=daily.minute,
        second=0,
        microsecond=0,
    )
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def _parse_daily_time(value: str) -> time:
    try:
        hour_text, minute_text = value.strip().split(":", 1)
        parsed = time(
            hour=int(hour_text),
            minute=int(minute_text),
        )
    except (ValueError, TypeError) as exc:
        raise ValueError(
            "daily_time must use HH:MM format"
        ) from exc
    return parsed


def _parse_datetime(value: str) -> datetime | None:
    if not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except ValueError:
        return None
    return _local_now(parsed)


def _local_now(value: datetime | None = None) -> datetime:
    if value is None:
        return datetime.now().astimezone()
    if value.tzinfo is None:
        return value.astimezone()
    return value.astimezone()


__all__ = [
    "CollectorScheduleFrequency",
    "CollectorScheduleRepository",
    "CollectorScheduleSettings",
    "CollectorScheduleState",
    "CollectorScheduler",
    "ScheduledCollectorRequest",
]
