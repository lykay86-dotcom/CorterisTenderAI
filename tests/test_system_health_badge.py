"""Tests for the compact system health badge."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.core.system_health import (
    SystemHealthSeverity,
    SystemHealthSnapshot,
)
from app.core.workflow_database_health import (
    WorkflowDatabaseHealthReport,
    WorkflowDatabaseHealthStatus,
)
from app.ui.business_workflow.system_health_badge import (
    SystemHealthBadge,
)
from app.ui.theme.colors import ThemeName, get_palette


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _snapshot(
    severity: SystemHealthSeverity,
) -> SystemHealthSnapshot:
    return SystemHealthSnapshot(
        checked_at=datetime(2026, 7, 11, 23, 30),
        database=WorkflowDatabaseHealthReport(
            path=Path("workflow.json"),
            status=WorkflowDatabaseHealthStatus.HEALTHY,
            checked_at=datetime(2026, 7, 11, 23, 30),
            schema_version=2,
            record_count=3,
            event_count=6,
        ),
        auto_backup_enabled=True,
        auto_backup_interval_hours=24,
        auto_backup_retention_count=10,
        auto_backup_last_success_at="2026-07-11T23:00:00",
        auto_backup_last_error="",
        backup_total=2,
        backup_valid=2,
        backup_invalid=0,
        latest_backup_at=datetime(2026, 7, 11, 23, 0),
        journal_count=5,
        severity=severity,
        issues=("Тестовое предупреждение.",) if severity == SystemHealthSeverity.WARNING else (),
    )


def test_badge_displays_snapshot_and_tooltip() -> None:
    _app()
    badge = SystemHealthBadge()
    badge.set_snapshot(_snapshot(SystemHealthSeverity.WARNING))

    assert badge.severity == SystemHealthSeverity.WARNING
    assert "Требуется внимание" in badge.text()
    assert "Копии: 2 исправных" in badge.toolTip()
    assert "Тестовое предупреждение" in badge.toolTip()


def test_badge_uses_valid_palette_tokens_in_both_themes() -> None:
    _app()
    badge = SystemHealthBadge()

    for theme in (ThemeName.DARK, ThemeName.LIGHT):
        palette = get_palette(theme)
        badge.apply_theme(theme)
        badge.set_snapshot(_snapshot(SystemHealthSeverity.SUCCESS))

        assert palette.success in badge.styleSheet()
        assert palette.success_background in badge.styleSheet()
