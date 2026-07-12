"""Tests for persistent collector scheduling."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.tenders.collector.scheduler import (
    CollectorScheduleFrequency,
    CollectorScheduleRepository,
    CollectorScheduleSettings,
    CollectorScheduler,
)


def _now(hour=10, minute=0):
    return datetime(
        2026,
        7,
        12,
        hour,
        minute,
        tzinfo=timezone.utc,
    )


def _settings(**changes):
    values = {
        "enabled": True,
        "profile_id": "all-corteris",
        "provider_ids": ("eis",),
        "frequency": CollectorScheduleFrequency.HOURLY,
        "daily_time": "09:00",
    }
    values.update(changes)
    return CollectorScheduleSettings(**values)


def test_repository_roundtrip(tmp_path) -> None:
    repository = CollectorScheduleRepository(
        tmp_path / "schedule.json"
    )
    scheduler = CollectorScheduler(repository)
    scheduler.update_settings(
        _settings(),
        now=_now(),
    )

    settings, state = scheduler.snapshot()

    assert settings.profile_id == "all-corteris"
    assert settings.provider_ids == ("eis",)
    expected = _now().astimezone() + timedelta(hours=1)
    actual = datetime.fromisoformat(state.next_run_at)

    assert actual == expected


def test_poll_returns_due_request(tmp_path) -> None:
    scheduler = CollectorScheduler(
        CollectorScheduleRepository(
            tmp_path / "schedule.json"
        )
    )
    scheduler.update_settings(
        _settings(),
        now=_now(),
    )

    assert scheduler.poll(
        now=_now(10, 59)
    ) is None
    request = scheduler.poll(now=_now(11, 0))

    assert request is not None
    assert request.profile_id == "all-corteris"
    assert request.reason == "scheduled"


def test_busy_run_is_deferred_without_overlap(tmp_path) -> None:
    scheduler = CollectorScheduler(
        CollectorScheduleRepository(
            tmp_path / "schedule.json"
        )
    )
    scheduler.update_settings(
        _settings(),
        now=_now(),
    )

    assert scheduler.poll(
        now=_now(11, 0),
        busy=True,
    ) is None
    _, state = scheduler.snapshot()

    assert state.last_status == "deferred_busy"
    assert state.busy_skip_count == 1


def test_mark_started_moves_next_interval(tmp_path) -> None:
    scheduler = CollectorScheduler(
        CollectorScheduleRepository(
            tmp_path / "schedule.json"
        )
    )
    scheduler.update_settings(
        _settings(),
        now=_now(),
    )
    request = scheduler.poll(now=_now(11, 0))
    assert request is not None

    state = scheduler.mark_started(
        request,
        now=_now(11, 0),
    )

    assert state.last_status == "running:scheduled"
    expected = _now(11, 0).astimezone() + timedelta(hours=1)
    actual = datetime.fromisoformat(state.next_run_at)

    assert actual == expected


def test_daily_schedule_uses_selected_time(tmp_path) -> None:
    scheduler = CollectorScheduler(
        CollectorScheduleRepository(
            tmp_path / "schedule.json"
        )
    )

    state = scheduler.update_settings(
        _settings(
            frequency=CollectorScheduleFrequency.DAILY,
            daily_time="09:30",
        ),
        now=_now(10, 0),
    )

    assert state.next_run_at.startswith(
        "2026-07-13T09:30:00"
    )


def test_startup_request_is_emitted_once(tmp_path) -> None:
    scheduler = CollectorScheduler(
        CollectorScheduleRepository(
            tmp_path / "schedule.json"
        )
    )
    scheduler.update_settings(
        _settings(run_on_startup=True),
        now=_now(),
    )

    first = scheduler.startup_request(now=_now())
    second = scheduler.startup_request(now=_now())

    assert first is not None
    assert first.reason == "startup"
    assert second is None


def test_freshness_due_preempts_regular_schedule(tmp_path) -> None:
    scheduler = CollectorScheduler(
        CollectorScheduleRepository(
            tmp_path / "schedule.json"
        )
    )
    scheduler.update_settings(
        _settings(
            frequency=CollectorScheduleFrequency.EVERY_3_HOURS
        ),
        now=_now(),
    )

    request = scheduler.poll(
        now=_now(10, 30),
        freshness_due_at=_now(10, 15).isoformat(),
    )

    assert request is not None
    assert request.reason == "freshness_due"
    assert datetime.fromisoformat(request.due_at) == _now(10, 15).astimezone()
