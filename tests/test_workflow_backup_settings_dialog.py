"""Tests for automatic backup settings dialog."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.core.workflow_auto_backup import (
    WorkflowAutoBackupService,
    WorkflowAutoBackupSettings,
)
from app.ui.business_workflow.backup_settings_dialog import (
    WorkflowBackupSettingsDialog,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_dialog_prefills_and_returns_preferences(tmp_path) -> None:
    _app()
    service = WorkflowAutoBackupService(tmp_path / "settings.json")
    dialog = WorkflowBackupSettingsDialog(
        WorkflowAutoBackupSettings(
            enabled=True,
            interval_hours=12,
            retention_count=20,
            directory=str(tmp_path / "copies"),
        ),
        default_directory=tmp_path / "default",
        auto_backup_service=service,
    )

    assert dialog.enabled_check.isChecked()
    assert dialog.interval_combo.currentData() == 12
    assert dialog.retention_spin.value() == 20

    values = dialog.settings()
    assert values.interval_hours == 12
    assert values.retention_count == 20
    assert values.directory == str(tmp_path / "copies")


def test_disabling_schedule_disables_controls(tmp_path) -> None:
    _app()
    service = WorkflowAutoBackupService(tmp_path / "settings.json")
    dialog = WorkflowBackupSettingsDialog(
        WorkflowAutoBackupSettings(enabled=True),
        default_directory=tmp_path / "default",
        auto_backup_service=service,
    )

    dialog.enabled_check.setChecked(False)

    assert not dialog.interval_combo.isEnabled()
    assert not dialog.retention_spin.isEnabled()
    assert not dialog.directory_edit.isEnabled()
    assert dialog.settings().enabled is False
