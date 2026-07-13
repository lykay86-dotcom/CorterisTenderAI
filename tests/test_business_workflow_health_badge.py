"""Tests for background health badge integration."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.core.system_health import SystemHealthSeverity
from app.core.workflow_auto_backup import WorkflowAutoBackupService
from app.core.workflow_backup import WorkflowBackupService
from app.core.workflow_backup_catalog import (
    WorkflowBackupCatalogService,
)
from app.core.workflow_database_health import (
    WorkflowDatabaseHealthService,
)
from app.repositories.business_metrics import BusinessMetricsRepository
from app.ui.pages.business_workflow_page import BusinessWorkflowPage


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_workflow_page_exposes_periodic_health_badge(tmp_path) -> None:
    _app()
    backup = WorkflowBackupService()
    catalog = WorkflowBackupCatalogService(backup)
    repository = BusinessMetricsRepository(tmp_path / "workflow.json")

    page = BusinessWorkflowPage(
        repository=repository,
        backup_service=backup,
        backup_catalog_service=catalog,
        database_health_service=WorkflowDatabaseHealthService(
            backup_service=backup,
            catalog_service=catalog,
        ),
        auto_backup_service=WorkflowAutoBackupService(
            tmp_path / "auto_settings.json",
            backup_service=backup,
        ),
    )

    assert "Проверка системы" in page.system_health_badge.text()
    assert page._system_health_timer.isActive()
    assert page._system_health_timer.interval() == 2 * 60 * 1000
    assert page.system_health_badge.severity == SystemHealthSeverity.INFO
