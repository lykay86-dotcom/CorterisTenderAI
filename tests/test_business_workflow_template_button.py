"""Tests for workflow Excel template UI integration."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.reporting.workflow_excel_template import (
    WorkflowExcelTemplateService,
)
from app.repositories.business_metrics import BusinessMetricsRepository
from app.ui.pages.business_workflow_page import BusinessWorkflowPage


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_workflow_page_exposes_template_button(tmp_path) -> None:
    _app()
    page = BusinessWorkflowPage(
        repository=BusinessMetricsRepository(
            tmp_path / "workflow.json"
        ),
        excel_template_service=WorkflowExcelTemplateService(
            tmp_path / "template.xlsx"
        ),
    )

    assert page.template_button.text().endswith("Шаблон Excel")
    assert "▤" in page.template_button.text()
    assert page.template_button.isEnabled()
