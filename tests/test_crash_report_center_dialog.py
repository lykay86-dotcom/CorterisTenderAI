"""Tests for the Crash Report Center dialog."""

from __future__ import annotations

import os
from datetime import datetime
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.core.crash_report_catalog import (
    CrashReportCatalogService,
)
from app.core.crash_reporting import CrashReportService
from app.ui.crash_report_center_dialog import (
    CrashReportCenterDialog,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _create_report(service: CrashReportService) -> None:
    try:
        raise RuntimeError("dialog failure")
    except RuntimeError:
        exc_type, exc_value, tb = sys.exc_info()
    service.create_report(
        exc_type,
        exc_value,
        tb,
        origin="dialog-test",
        created_at=datetime(2026, 7, 12, 15, 0),
    )


def test_center_lists_report_and_displays_traceback(tmp_path) -> None:
    _app()
    directory = tmp_path / "crashes"
    service = CrashReportService(directory)
    _create_report(service)

    dialog = CrashReportCenterDialog(
        catalog_service=CrashReportCatalogService(service),
        directories=[directory],
        support_bundle_provider=lambda target: target,
    )

    assert dialog.table.rowCount() == 1
    assert dialog.selected_entry is not None
    assert dialog.selected_entry.valid
    assert "RuntimeError" in dialog.details_label.text()
    assert "dialog failure" in dialog.traceback_edit.toPlainText()
    assert dialog.copy_button.isEnabled()
    assert dialog.support_button.isEnabled()


def test_invalid_report_stays_visible_but_cannot_be_copied(
    tmp_path,
) -> None:
    _app()
    directory = tmp_path / "crashes"
    directory.mkdir()
    (directory / "invalid.ctcrash").write_text(
        "damaged",
        encoding="utf-8",
    )
    service = CrashReportService(directory)

    dialog = CrashReportCenterDialog(
        catalog_service=CrashReportCatalogService(service),
        directories=[directory],
    )

    assert dialog.table.rowCount() == 1
    assert dialog.selected_entry is not None
    assert not dialog.selected_entry.valid
    assert not dialog.copy_button.isEnabled()
    assert dialog.delete_button.isEnabled()
    assert "повреждён" in dialog.details_label.text().lower()
