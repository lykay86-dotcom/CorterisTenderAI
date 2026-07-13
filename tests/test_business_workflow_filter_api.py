"""Regression tests for non-deprecated workflow filtering."""

from __future__ import annotations

import os
import warnings

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.repositories.business_metrics import (
    BusinessRecordKind,
    BusinessStatus,
    BusinessWorkflowRecord,
)
from app.ui.business_workflow.model import (
    WorkflowFilterProxyModel,
    WorkflowTableModel,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_filter_changes_do_not_emit_deprecation_warning() -> None:
    _app()
    model = WorkflowTableModel(
        [
            BusinessWorkflowRecord(
                id="1",
                kind=BusinessRecordKind.PROPOSAL.value,
                tender_id="10",
                title="КП",
                status=BusinessStatus.READY.value,
                updated_at="2026-07-11T12:00:00",
            )
        ]
    )
    proxy = WorkflowFilterProxyModel()
    proxy.setSourceModel(model)

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        proxy.set_search("КП")
        proxy.set_kind(BusinessRecordKind.PROPOSAL)
        proxy.set_status(BusinessStatus.READY)

    deprecated = [
        warning for warning in captured if issubclass(warning.category, DeprecationWarning)
    ]
    assert deprecated == []
    assert proxy.rowCount() == 1
