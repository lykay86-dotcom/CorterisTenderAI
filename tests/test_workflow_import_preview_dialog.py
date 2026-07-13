"""Tests for workflow import preview dialog."""

from __future__ import annotations

import os
import warnings
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.reporting.workflow_excel_import import (
    WorkflowImportIssue,
    WorkflowImportLevel,
    WorkflowImportPreview,
    WorkflowImportRow,
)
from app.repositories.business_metrics import (
    BusinessRecordKind,
    BusinessStatus,
)
from app.ui.business_workflow.import_dialog import (
    WorkflowImportPreviewDialog,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_preview_dialog_enables_import_for_valid_rows() -> None:
    _app()
    preview = WorkflowImportPreview(
        path=Path("registry.xlsx"),
        sheet_name="Реестр",
        rows=(
            WorkflowImportRow(
                source_row=2,
                kind=BusinessRecordKind.PROPOSAL,
                tender_id="T-1",
                title="КП",
                status=BusinessStatus.DRAFT,
            ),
        ),
    )

    dialog = WorkflowImportPreviewDialog(preview)

    assert dialog.table.rowCount() == 1
    assert dialog.import_button.isEnabled()
    assert "Импортировать 1" == dialog.import_button.text()


def test_preview_dialog_disables_import_for_invalid_rows() -> None:
    _app()
    row = WorkflowImportRow(
        source_row=2,
        tender_id="",
        title="",
    )
    row.issues.append(
        WorkflowImportIssue(
            WorkflowImportLevel.ERROR,
            "Не указан тендер.",
        )
    )
    preview = WorkflowImportPreview(
        path=Path("invalid.xlsx"),
        sheet_name="Реестр",
        rows=(row,),
    )

    dialog = WorkflowImportPreviewDialog(preview)

    assert not dialog.import_button.isEnabled()
    assert dialog.table.item(0, 1).text() == "Ошибка"


def test_preview_dialog_uses_non_deprecated_alignment_api() -> None:
    _app()
    preview = WorkflowImportPreview(
        path=Path("registry.xlsx"),
        sheet_name="Реестр",
        rows=(
            WorkflowImportRow(
                source_row=2,
                kind=BusinessRecordKind.PROPOSAL,
                tender_id="T-1",
                title="КП",
                status=BusinessStatus.DRAFT,
            ),
        ),
    )

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        WorkflowImportPreviewDialog(preview)

    deprecated = [
        warning
        for warning in captured
        if issubclass(warning.category, DeprecationWarning)
        and "setTextAlignment" in str(warning.message)
    ]
    assert deprecated == []
