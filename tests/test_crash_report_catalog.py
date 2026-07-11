"""Tests for crash-report catalog discovery and operations."""

from __future__ import annotations

from datetime import datetime
import sys

from app.core.crash_report_catalog import (
    CrashReportCatalogService,
)
from app.core.crash_reporting import CrashReportService


def _report(
    service: CrashReportService,
    *,
    message: str,
    created_at: datetime,
):
    try:
        raise RuntimeError(message)
    except RuntimeError:
        exc_type, exc_value, tb = sys.exc_info()
    return service.create_report(
        exc_type,
        exc_value,
        tb,
        origin="test",
        created_at=created_at,
    )


def test_catalog_lists_valid_and_invalid_reports(tmp_path) -> None:
    directory = tmp_path / "crashes"
    service = CrashReportService(directory)
    older = _report(
        service,
        message="older",
        created_at=datetime(2026, 7, 12, 12, 0),
    )
    newer = _report(
        service,
        message="newer",
        created_at=datetime(2026, 7, 12, 13, 0),
    )
    damaged = directory / "damaged.ctcrash"
    damaged.write_text("broken", encoding="utf-8")

    entries = CrashReportCatalogService(
        service
    ).list_reports([directory])

    assert entries[0].path == newer.path
    assert entries[1].path == older.path
    assert any(entry.path == damaged for entry in entries)
    assert sum(entry.valid for entry in entries) == 2
    assert sum(not entry.valid for entry in entries) == 1


def test_catalog_copies_and_deletes_managed_report(tmp_path) -> None:
    directory = tmp_path / "crashes"
    service = CrashReportService(directory)
    report = _report(
        service,
        message="copy",
        created_at=datetime(2026, 7, 12, 13, 30),
    )
    catalog = CrashReportCatalogService(service)

    copied = catalog.copy_report(
        report.path,
        tmp_path / "exported",
    )

    assert copied.suffix == ".ctcrash"
    assert copied.exists()
    assert service.inspect_report(copied).valid

    deleted = catalog.delete_report(
        report.path,
        managed_directories=[directory],
    )
    assert deleted == report.path
    assert not report.path.exists()


def test_external_report_requires_delete_permission(tmp_path) -> None:
    managed = tmp_path / "managed"
    external = tmp_path / "external"
    service = CrashReportService(external)
    report = _report(
        service,
        message="external",
        created_at=datetime(2026, 7, 12, 14, 0),
    )
    catalog = CrashReportCatalogService(service)

    try:
        catalog.delete_report(
            report.path,
            managed_directories=[managed],
        )
    except PermissionError:
        pass
    else:
        raise AssertionError("Expected PermissionError")

    catalog.delete_report(
        report.path,
        managed_directories=[managed],
        allow_external=True,
    )
    assert not report.path.exists()
