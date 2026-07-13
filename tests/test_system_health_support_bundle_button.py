"""Tests for support bundle integration in System Health Center."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.core.diagnostic_support_bundle import (
    DiagnosticSupportBundleService,
)
from app.core.system_health import (
    SystemHealthJournal,
    SystemHealthService,
)
from app.core.workflow_auto_backup import WorkflowAutoBackupService
from app.core.workflow_backup import WorkflowBackupService
from app.core.workflow_backup_catalog import (
    WorkflowBackupCatalogService,
)
from app.core.workflow_database_health import (
    WorkflowDatabaseHealthService,
)
from app.repositories.business_metrics import BusinessMetricsRepository
from app.ui.business_workflow.system_health_dialog import (
    SystemHealthCenterDialog,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_health_center_exposes_support_bundle_button(
    tmp_path,
) -> None:
    _app()
    repository = BusinessMetricsRepository(tmp_path / "workflow.json")
    backup = WorkflowBackupService()
    catalog = WorkflowBackupCatalogService(backup)
    support = DiagnosticSupportBundleService()

    dialog = SystemHealthCenterDialog(
        repository=repository,
        health_service=SystemHealthService(),
        journal=SystemHealthJournal(tmp_path / "journal.json"),
        database_health_service=WorkflowDatabaseHealthService(
            backup_service=backup,
            catalog_service=catalog,
        ),
        auto_backup_service=WorkflowAutoBackupService(
            tmp_path / "auto_settings.json",
            backup_service=backup,
        ),
        backup_catalog_service=catalog,
        backup_directories=[tmp_path / "backups"],
        support_bundle_service=support,
    )

    assert dialog.support_bundle_service is support
    assert dialog.support_bundle_button.text() == "Пакет диагностики…"
    assert dialog.support_bundle_button.isEnabled()
