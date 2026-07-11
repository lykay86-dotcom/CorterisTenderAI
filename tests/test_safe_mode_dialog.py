"""Tests for the minimal Safe Mode dialog."""

from __future__ import annotations

import os
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.core.launch_guard import LaunchGuardService
from app.ui.safe_mode_dialog import SafeModeDialog


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_safe_mode_dialog_shows_checks_and_actions(tmp_path) -> None:
    _app()
    guard = LaunchGuardService(
        tmp_path / "launch_history.json",
        crash_threshold=2,
    )

    for index in range(2):
        guard.begin_launch(
            started_at=datetime(2026, 7, 12, 10 + index, 0)
        )
        guard.mark_crash(
            finished_at=datetime(2026, 7, 12, 10 + index, 1)
        )

    decision = guard.evaluate(
        now=datetime(2026, 7, 12, 12, 0)
    )
    data_dir = tmp_path / "data"
    backups = data_dir / "backups"
    crashes = data_dir / "crash_reports"
    data_dir.mkdir()
    backups.mkdir()
    crashes.mkdir()
    (backups / "copy.ctbackup").write_text(
        "test",
        encoding="utf-8",
    )
    (crashes / "error.ctcrash").write_text(
        "test",
        encoding="utf-8",
    )

    dialog = SafeModeDialog(
        decision=decision,
        launch_guard=guard,
        data_directory=data_dir,
        database_file=data_dir / "database.sqlite3",
        backups_directory=backups,
        crash_reports_directory=crashes,
    )

    assert dialog.normal_button.text() == (
        "Продолжить обычный запуск"
    )
    assert dialog.reset_button.isEnabled()
    assert "Последние аварийные запуски: 2" in (
        dialog._history_text()
    )


def test_reset_button_clears_launch_history(tmp_path) -> None:
    _app()
    guard = LaunchGuardService(
        tmp_path / "launch_history.json",
        crash_threshold=2,
    )
    guard.begin_launch()
    guard.mark_crash()
    decision = guard.evaluate(force_safe_mode=True)

    dialog = SafeModeDialog(
        decision=decision,
        launch_guard=guard,
        data_directory=tmp_path,
        database_file=tmp_path / "database.sqlite3",
        backups_directory=tmp_path / "backups",
        crash_reports_directory=tmp_path / "crashes",
    )
    dialog._reset_history()

    assert guard.list_records() == []
    assert not dialog.reset_button.isEnabled()
    assert dialog.reset_button.text() == "История сброшена"
