"""Tests for workflow backup menu integration."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.core.workflow_auto_backup import WorkflowAutoBackupService
from app.core.workflow_backup import WorkflowBackupService
from app.core.workflow_backup_catalog import (
    WorkflowBackupCatalogService,
)
from app.repositories.business_metrics import BusinessMetricsRepository
from app.ui.pages.business_workflow_page import BusinessWorkflowPage


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_workflow_page_exposes_backup_center_and_actions(
    tmp_path,
) -> None:
    _app()
    backup_service = WorkflowBackupService()
    page = BusinessWorkflowPage(
        repository=BusinessMetricsRepository(tmp_path / "workflow.json"),
        backup_service=backup_service,
        backup_catalog_service=WorkflowBackupCatalogService(backup_service),
        auto_backup_service=WorkflowAutoBackupService(
            tmp_path / "auto_backup_settings.json",
            backup_service=backup_service,
        ),
    )

    assert page.data_button.text().endswith("Данные")
    assert [action.text() for action in page.data_menu.actions()] == [
        "Состояние системы…",
        "",
        "Центр резервных копий…",
        "Диагностика базы…",
        "",
        "Создать резервную копию…",
        "Восстановить из копии…",
        "",
        "Настроить автокопирование…",
        "Создать автокопию сейчас",
    ]
    assert page._auto_backup_timer.isActive()
    assert page._auto_backup_timer.interval() == 15 * 60 * 1000
