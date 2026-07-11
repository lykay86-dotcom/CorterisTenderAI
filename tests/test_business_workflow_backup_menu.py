"""Tests for workflow backup menu integration."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.core.workflow_backup import WorkflowBackupService
from app.repositories.business_metrics import BusinessMetricsRepository
from app.ui.pages.business_workflow_page import BusinessWorkflowPage


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_workflow_page_exposes_backup_and_restore_actions(
    tmp_path,
) -> None:
    _app()
    page = BusinessWorkflowPage(
        repository=BusinessMetricsRepository(
            tmp_path / "workflow.json"
        ),
        backup_service=WorkflowBackupService(),
    )

    assert page.data_button.text().endswith("Данные")
    assert [
        action.text()
        for action in page.data_menu.actions()
    ] == [
        "Создать резервную копию…",
        "Восстановить из копии…",
    ]
