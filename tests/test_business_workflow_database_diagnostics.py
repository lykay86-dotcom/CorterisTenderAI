"""Tests for automatic database diagnostics integration."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

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


def _page(tmp_path) -> BusinessWorkflowPage:
    backup_service = WorkflowBackupService()
    catalog = WorkflowBackupCatalogService(backup_service)
    repository = BusinessMetricsRepository(tmp_path / "business_workflow.json")
    return BusinessWorkflowPage(
        repository=repository,
        backup_service=backup_service,
        backup_catalog_service=catalog,
        database_health_service=WorkflowDatabaseHealthService(
            backup_service=backup_service,
            catalog_service=catalog,
        ),
        auto_backup_service=WorkflowAutoBackupService(
            tmp_path / "auto_backup_settings.json",
            backup_service=backup_service,
        ),
    )


def test_data_menu_contains_database_diagnostics(tmp_path) -> None:
    _app()
    page = _page(tmp_path)

    actions = [action.text() for action in page.data_menu.actions()]

    assert actions[:6] == [
        "Состояние системы…",
        "",
        "Центр резервных копий…",
        "Диагностика базы…",
        "",
        "Создать резервную копию…",
    ]


def test_corrupted_database_is_not_auto_backed_up(tmp_path) -> None:
    _app()
    page = _page(tmp_path)
    page.repository.path.write_text(
        "{damaged",
        encoding="utf-8",
    )

    page._check_automatic_backup(force=True)

    automatic_dir = page.auto_backup_service.backup_directory(
        page.repository,
        page.auto_backup_service.load_settings(),
    )
    assert not list(automatic_dir.glob("*.ctbackup"))
