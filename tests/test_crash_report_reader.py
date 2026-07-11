"""Tests for verified crash-report reading."""

from __future__ import annotations

from datetime import datetime
import sys

from app.core.crash_reporting import CrashReportService


def test_read_report_returns_crash_details(tmp_path) -> None:
    service = CrashReportService(tmp_path / "crashes")

    try:
        raise ValueError("test failure")
    except ValueError:
        exc_type, exc_value, tb = sys.exc_info()

    created = service.create_report(
        exc_type,
        exc_value,
        tb,
        origin="unit-test",
        thread_name="TestThread",
        created_at=datetime(2026, 7, 12, 14, 0),
    )

    details = service.read_report(created.path)

    assert details.crash_id == created.crash_id
    assert details.origin == "unit-test"
    assert details.thread_name == "TestThread"
    assert details.exception_type.endswith("ValueError")
    assert details.exception_message == "test failure"
    assert "ValueError: test failure" in details.traceback_text
    assert details.created_timestamp == datetime(
        2026,
        7,
        12,
        14,
        0,
    )
