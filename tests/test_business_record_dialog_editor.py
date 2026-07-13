"""Tests for business record edit dialog."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.repositories.business_metrics import (
    BusinessRecordKind,
    BusinessStatus,
    BusinessWorkflowRecord,
)
from app.ui.business_workflow.dialogs import BusinessRecordDialog


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _record() -> BusinessWorkflowRecord:
    return BusinessWorkflowRecord(
        id="record-1",
        kind=BusinessRecordKind.PROPOSAL.value,
        tender_id="T-100",
        title="КП на видеонаблюдение",
        status=BusinessStatus.READY.value,
        total=1000000,
        profit=200000,
        margin_percent=20,
        file_path="proposal.docx",
        due_date="2026-07-20",
        created_at="2026-07-11T10:00:00",
        updated_at="2026-07-11T10:00:00",
    )


def test_edit_dialog_prefills_and_locks_identity_fields() -> None:
    _app()
    dialog = BusinessRecordDialog(record=_record())

    assert dialog.edit_mode is True
    assert dialog.title_edit.text() == "КП на видеонаблюдение"
    assert dialog.tender_edit.text() == "T-100"
    assert not dialog.kind_combo.isEnabled()
    assert not dialog.tender_edit.isEnabled()
    assert not dialog.status_combo.isEnabled()
    assert dialog.total_spin.value() == 1000000
    assert dialog.profit_spin.value() == 200000


def test_dialog_recalculates_margin_from_total_and_profit() -> None:
    _app()
    dialog = BusinessRecordDialog(initial_kind=BusinessRecordKind.ESTIMATE)

    dialog.total_spin.setValue(800000)
    dialog.profit_spin.setValue(160000)

    assert round(dialog.margin_spin.value(), 2) == 20.00
