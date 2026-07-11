"""Tests for workflow backup center dialog."""

from __future__ import annotations

import os
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.core.workflow_backup import WorkflowBackupService
from app.core.workflow_backup_catalog import (
    WorkflowBackupCatalogService,
)
from app.repositories.business_metrics import (
    BusinessMetricsRepository,
    BusinessRecordKind,
    BusinessStatus,
)
from app.ui.business_workflow.backup_center_dialog import (
    WorkflowBackupCenterDialog,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_backup_center_lists_valid_and_invalid_files(
    tmp_path,
) -> None:
    _app()
    repository = BusinessMetricsRepository(
        tmp_path / "workflow.json"
    )
    repository.save_record(
        kind=BusinessRecordKind.PROPOSAL,
        tender_id="T-85",
        title="КП",
        status=BusinessStatus.READY,
    )

    directory = tmp_path / "backups"
    backup_service = WorkflowBackupService()
    backup_service.create_backup(
        repository,
        directory / "valid.ctbackup",
        created_at=datetime(2026, 7, 11, 21, 0),
    )
    directory.mkdir(exist_ok=True)
    (directory / "invalid.ctbackup").write_text(
        "damaged",
        encoding="utf-8",
    )

    dialog = WorkflowBackupCenterDialog(
        repository=repository,
        backup_service=backup_service,
        catalog_service=WorkflowBackupCatalogService(
            backup_service
        ),
        directories=[directory],
    )

    assert dialog.table.rowCount() == 2
    assert "Найдено: 2" in dialog.summary_label.text()
    assert any(entry.valid for entry in dialog.entries)
    assert any(not entry.valid for entry in dialog.entries)


def test_invalid_selected_backup_cannot_be_restored(
    tmp_path,
) -> None:
    _app()
    repository = BusinessMetricsRepository(
        tmp_path / "workflow.json"
    )
    directory = tmp_path / "backups"
    directory.mkdir()
    (directory / "invalid.ctbackup").write_text(
        "damaged",
        encoding="utf-8",
    )

    dialog = WorkflowBackupCenterDialog(
        repository=repository,
        backup_service=WorkflowBackupService(),
        catalog_service=WorkflowBackupCatalogService(),
        directories=[directory],
    )
    dialog.table.selectRow(0)
    dialog.table.setCurrentCell(0, 0)
    dialog._selection_changed()

    assert dialog.selected_entry is not None
    assert not dialog.selected_entry.valid
    assert not dialog.restore_button.isEnabled()
    assert dialog.verify_button.isEnabled()
    assert dialog.delete_button.isEnabled()
