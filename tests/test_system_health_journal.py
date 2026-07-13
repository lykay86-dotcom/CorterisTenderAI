"""Tests for the persistent system health journal."""

from __future__ import annotations

from datetime import datetime

from app.core.system_health import (
    SystemHealthJournal,
    SystemHealthSeverity,
)


def test_journal_records_orders_limits_and_clears(tmp_path) -> None:
    journal = SystemHealthJournal(
        tmp_path / "system_health.json",
        max_events=10,
    )
    journal.record(
        severity=SystemHealthSeverity.INFO,
        component="database",
        title="First",
        occurred_at=datetime(2026, 7, 11, 10, 0),
    )
    journal.record(
        severity=SystemHealthSeverity.ERROR,
        component="backup",
        title="Second",
        details="Failure",
        occurred_at=datetime(2026, 7, 11, 11, 0),
    )

    events = journal.list_events(limit=1)

    assert len(events) == 1
    assert events[0].title == "Second"
    assert events[0].severity == SystemHealthSeverity.ERROR
    assert journal.count() == 2

    journal.clear()

    assert journal.list_events(limit=None) == ()


def test_journal_exports_utf8_text(tmp_path) -> None:
    journal = SystemHealthJournal(tmp_path / "system_health.json")
    journal.record(
        severity=SystemHealthSeverity.SUCCESS,
        component="database",
        title="Диагностика завершена",
        details="База исправна",
        occurred_at=datetime(2026, 7, 11, 12, 30),
    )

    target = journal.export_text(tmp_path / "journal")

    assert target.suffix == ".txt"
    text = target.read_text(encoding="utf-8-sig")
    assert "Диагностика завершена" in text
    assert "База исправна" in text


def test_corrupted_journal_does_not_break_application(tmp_path) -> None:
    path = tmp_path / "system_health.json"
    path.write_text("{broken", encoding="utf-8")
    journal = SystemHealthJournal(path)

    assert journal.list_events() == ()

    event = journal.record(
        severity=SystemHealthSeverity.WARNING,
        component="system",
        title="Recovered",
    )
    assert event.title == "Recovered"
    assert journal.count() == 1
