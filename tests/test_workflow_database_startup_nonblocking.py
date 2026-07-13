"""Regression tests for non-blocking startup diagnostics."""

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
from app.ui.business_workflow.database_recovery_dialog import (
    WorkflowDatabaseRecoveryDialog,
)
from app.ui.pages.business_workflow_page import BusinessWorkflowPage


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_corrupted_database_startup_never_opens_modal_dialog(
    tmp_path,
    monkeypatch,
) -> None:
    app = _app()
    repository = BusinessMetricsRepository(tmp_path / "business_workflow.json")
    repository.path.write_text("{broken", encoding="utf-8")

    backup_service = WorkflowBackupService()
    catalog = WorkflowBackupCatalogService(backup_service)
    health = WorkflowDatabaseHealthService(
        backup_service=backup_service,
        catalog_service=catalog,
    )
    auto_backup = WorkflowAutoBackupService(
        tmp_path / "auto_backup_settings.json",
        backup_service=backup_service,
    )

    modal_calls: list[bool] = []

    def forbidden_exec(self) -> int:
        modal_calls.append(True)
        raise AssertionError("Startup diagnostics must not open a modal dialog")

    monkeypatch.setattr(
        WorkflowDatabaseRecoveryDialog,
        "exec",
        forbidden_exec,
    )

    page = BusinessWorkflowPage(
        repository=repository,
        backup_service=backup_service,
        backup_catalog_service=catalog,
        database_health_service=health,
        auto_backup_service=auto_backup,
    )

    # Executes the zero-delay startup timer.
    app.processEvents()

    assert modal_calls == []
    assert not list((tmp_path / "backups").rglob("*.ctbackup"))
    assert page._auto_backup_timer.isActive()
