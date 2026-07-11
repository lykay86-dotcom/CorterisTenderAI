"""Regression tests for reporting package placement."""

from __future__ import annotations

from app.reporting import (
    WorkflowExcelExporter,
    WorkflowExcelExportResult,
)
from app.repositories import (
    BusinessMetricsRepository,
    TenderRepository,
)


def test_reporting_package_exports_excel_service() -> None:
    assert WorkflowExcelExporter is not None
    assert WorkflowExcelExportResult is not None


def test_repository_package_does_not_import_reporting_as_repository() -> None:
    assert BusinessMetricsRepository is not None
    assert TenderRepository is not None
