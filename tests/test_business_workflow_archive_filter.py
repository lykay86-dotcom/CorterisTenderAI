"""Tests for workflow archive filtering."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.repositories.business_metrics import (
    BusinessRecordKind,
    BusinessStatus,
    BusinessWorkflowRecord,
)
from app.ui.business_workflow.model import (
    WorkflowArchiveMode,
    WorkflowFilterProxyModel,
    WorkflowTableModel,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _record(
    record_id: str,
    *,
    archived: bool,
) -> BusinessWorkflowRecord:
    return BusinessWorkflowRecord(
        id=record_id,
        kind=BusinessRecordKind.PROPOSAL.value,
        tender_id="T-1",
        title=f"КП {record_id}",
        status=BusinessStatus.READY.value,
        updated_at="2026-07-11T12:00:00",
        archived_at=(
            "2026-07-11T13:00:00" if archived else ""
        ),
    )


def test_proxy_defaults_to_active_records() -> None:
    _app()
    model = WorkflowTableModel(
        [
            _record("active", archived=False),
            _record("archived", archived=True),
        ]
    )
    proxy = WorkflowFilterProxyModel()
    proxy.setSourceModel(model)

    assert proxy.rowCount() == 1


def test_proxy_can_show_archive_or_all_records() -> None:
    _app()
    model = WorkflowTableModel(
        [
            _record("active", archived=False),
            _record("archived", archived=True),
        ]
    )
    proxy = WorkflowFilterProxyModel()
    proxy.setSourceModel(model)

    proxy.set_archive_mode(WorkflowArchiveMode.ARCHIVED)
    assert proxy.rowCount() == 1

    proxy.set_archive_mode(WorkflowArchiveMode.ALL)
    assert proxy.rowCount() == 2
