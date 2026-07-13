"""Tests for Crash Report Center page integration."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.core.crash_report_catalog import (
    CrashReportCatalogService,
)
from app.core.crash_reporting import CrashReportService
from app.repositories.business_metrics import BusinessMetricsRepository
from app.ui.pages.business_workflow_page import BusinessWorkflowPage


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_workflow_page_uses_local_crash_report_directory(
    tmp_path,
) -> None:
    _app()
    repository = BusinessMetricsRepository(tmp_path / "workflow.json")
    crash_service = CrashReportService(tmp_path / "custom_crashes")
    catalog = CrashReportCatalogService(crash_service)

    page = BusinessWorkflowPage(
        repository=repository,
        crash_report_service=crash_service,
        crash_report_catalog_service=catalog,
    )

    assert page.crash_report_service is crash_service
    assert page.crash_report_catalog_service is catalog
    assert page.crash_report_service.directory == (tmp_path / "custom_crashes")
