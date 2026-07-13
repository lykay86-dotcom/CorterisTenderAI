"""Tests for the unified system health center dialog."""

from __future__ import annotations

import os
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.core.system_health import (
    SystemHealthJournal,
    SystemHealthService,
    SystemHealthSeverity,
)
from app.core.workflow_auto_backup import WorkflowAutoBackupService
from app.core.workflow_backup import WorkflowBackupService
from app.core.workflow_backup_catalog import (
    WorkflowBackupCatalogService,
)
from app.core.workflow_database_health import (
    WorkflowDatabaseHealthService,
)
from app.repositories.business_metrics import (
    BusinessMetricsRepository,
    BusinessRecordKind,
    BusinessStatus,
)
from app.ui.business_workflow.system_health_dialog import (
    SystemHealthCenterDialog,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_system_health_center_displays_cards_and_journal(
    tmp_path,
) -> None:
    _app()
    repository = BusinessMetricsRepository(tmp_path / "workflow.json")
    repository.save_record(
        kind=BusinessRecordKind.ESTIMATE,
        tender_id="T-87",
        title="Смета",
        status=BusinessStatus.DRAFT,
    )

    backup = WorkflowBackupService()
    catalog = WorkflowBackupCatalogService(backup)
    database_health = WorkflowDatabaseHealthService(
        backup_service=backup,
        catalog_service=catalog,
    )
    auto = WorkflowAutoBackupService(
        tmp_path / "auto_settings.json",
        backup_service=backup,
    )
    journal = SystemHealthJournal(tmp_path / "journal.json")
    journal.record(
        severity=SystemHealthSeverity.SUCCESS,
        component="database",
        title="Проверка завершена",
        occurred_at=datetime(2026, 7, 11, 23, 10),
    )

    dialog = SystemHealthCenterDialog(
        repository=repository,
        health_service=SystemHealthService(),
        journal=journal,
        database_health_service=database_health,
        auto_backup_service=auto,
        backup_catalog_service=catalog,
        backup_directories=[tmp_path / "backups"],
    )

    assert dialog.snapshot is not None
    assert dialog.database_value.text() == "Исправна"
    assert dialog.table.rowCount() == 1
    assert dialog.table.item(0, 3).text() == "Проверка завершена"


def test_system_health_center_navigation_signals(tmp_path) -> None:
    _app()
    repository = BusinessMetricsRepository(tmp_path / "workflow.json")
    backup = WorkflowBackupService()
    catalog = WorkflowBackupCatalogService(backup)
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
    )

    requested: list[str] = []
    dialog.database_diagnostics_requested.connect(lambda: requested.append("database"))
    dialog._request_database_diagnostics()

    assert requested == ["database"]
