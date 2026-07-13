"""Tests for the workflow database recovery dialog."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.core.workflow_backup import WorkflowBackupInspection
from app.core.workflow_backup_catalog import (
    WorkflowBackupEntry,
    WorkflowBackupKind,
)
from app.core.workflow_database_health import (
    WorkflowDatabaseHealthReport,
    WorkflowDatabaseHealthStatus,
    WorkflowDatabaseIssue,
)
from app.ui.business_workflow.database_recovery_dialog import (
    WorkflowDatabaseRecoveryAction,
    WorkflowDatabaseRecoveryDialog,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _report(*, with_backup: bool):
    backup = None
    if with_backup:
        inspection = WorkflowBackupInspection(
            path=Path("valid.ctbackup"),
            valid=True,
            created_at="2026-07-11T21:00:00",
            schema_version=2,
            record_count=4,
            event_count=9,
        )
        backup = WorkflowBackupEntry(
            path=Path("valid.ctbackup"),
            inspection=inspection,
            kind=WorkflowBackupKind.MANUAL,
            size_bytes=1024,
            modified_at=datetime(2026, 7, 11, 21, 0),
            managed=True,
        )
    return WorkflowDatabaseHealthReport(
        path=Path("business_workflow.json"),
        status=WorkflowDatabaseHealthStatus.CORRUPTED,
        checked_at=datetime(2026, 7, 11, 22, 0),
        issues=(
            WorkflowDatabaseIssue(
                "json_decode_error",
                "Ошибка JSON.",
            ),
        ),
        latest_valid_backup=backup,
    )


def test_restore_button_enabled_when_valid_backup_exists() -> None:
    _app()
    dialog = WorkflowDatabaseRecoveryDialog(_report(with_backup=True))

    assert dialog.restore_button.isEnabled()
    dialog._restore_latest()
    assert dialog.selected_action == WorkflowDatabaseRecoveryAction.RESTORE_LATEST


def test_restore_button_disabled_without_backup() -> None:
    _app()
    dialog = WorkflowDatabaseRecoveryDialog(_report(with_backup=False))

    assert not dialog.restore_button.isEnabled()
    assert "не найдена" in dialog.backup_label.text()
