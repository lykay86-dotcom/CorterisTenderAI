"""Tests for repeated-crash launch guard and safe-mode decision."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.core.launch_guard import LaunchGuardService


NOW = datetime(2026, 7, 12, 18, 0, 0)


def test_three_recent_crashes_enable_safe_mode(tmp_path) -> None:
    guard = LaunchGuardService(
        tmp_path / "launch_history.json",
        crash_threshold=3,
        window_minutes=30,
    )

    for minutes in (20, 10, 1):
        guard.begin_launch(
            started_at=NOW - timedelta(minutes=minutes)
        )
        guard.mark_crash(
            finished_at=NOW - timedelta(minutes=minutes - 1),
            details="test crash",
        )

    decision = guard.evaluate(now=NOW)

    assert decision.enabled
    assert decision.recent_crashes == 3
    assert "аварийных запусков" in decision.reason


def test_old_crashes_do_not_enable_safe_mode(tmp_path) -> None:
    guard = LaunchGuardService(
        tmp_path / "launch_history.json",
        crash_threshold=3,
        window_minutes=30,
    )

    for hours in (4, 3, 2):
        guard.begin_launch(
            started_at=NOW - timedelta(hours=hours)
        )
        guard.mark_crash(
            finished_at=NOW - timedelta(hours=hours),
        )

    decision = guard.evaluate(now=NOW)

    assert not decision.enabled
    assert decision.recent_crashes == 0


def test_running_launch_becomes_interrupted_on_next_start(
    tmp_path,
) -> None:
    path = tmp_path / "launch_history.json"
    first = LaunchGuardService(path)
    first.begin_launch(started_at=NOW - timedelta(minutes=5))

    second = LaunchGuardService(path)
    second.begin_launch(started_at=NOW)

    outcomes = {
        record.outcome
        for record in second.list_records()
    }

    assert "interrupted" in outcomes
    assert "running" in outcomes


def test_clean_exit_and_reset_history(tmp_path) -> None:
    guard = LaunchGuardService(tmp_path / "launch_history.json")
    guard.begin_launch(started_at=NOW)
    guard.mark_clean_exit(
        finished_at=NOW + timedelta(minutes=1)
    )

    records = guard.list_records()
    assert records[0].outcome == "clean"

    guard.reset_history()
    assert guard.list_records() == []


def test_force_safe_mode_works_without_crashes(tmp_path) -> None:
    guard = LaunchGuardService(tmp_path / "launch_history.json")

    decision = guard.evaluate(
        now=NOW,
        force_safe_mode=True,
    )

    assert decision.enabled
    assert decision.recent_crashes == 0
    assert "вручную" in decision.reason
