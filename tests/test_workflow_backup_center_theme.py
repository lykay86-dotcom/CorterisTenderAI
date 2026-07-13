"""Regression test for Backup Center palette compatibility."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.core.workflow_backup import WorkflowBackupService
from app.core.workflow_backup_catalog import (
    WorkflowBackupCatalogService,
)
from app.repositories.business_metrics import BusinessMetricsRepository
from app.ui.business_workflow.backup_center_dialog import (
    WorkflowBackupCenterDialog,
)
from app.ui.theme.colors import ThemeName, get_palette


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_backup_center_uses_existing_palette_tokens_for_both_themes(
    tmp_path,
) -> None:
    _app()
    repository = BusinessMetricsRepository(tmp_path / "workflow.json")
    backup_service = WorkflowBackupService()

    for theme in (ThemeName.DARK, ThemeName.LIGHT):
        palette = get_palette(theme)

        assert palette.brand_primary
        assert palette.text_on_brand

        dialog = WorkflowBackupCenterDialog(
            repository=repository,
            backup_service=backup_service,
            catalog_service=WorkflowBackupCatalogService(backup_service),
            directories=[tmp_path / "backups"],
            theme=theme,
        )

        stylesheet = dialog.styleSheet()
        assert palette.brand_primary in stylesheet
        assert palette.text_on_brand in stylesheet
        dialog.close()
