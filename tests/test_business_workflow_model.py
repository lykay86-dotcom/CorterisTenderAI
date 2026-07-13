"""Tests for business workflow transitions and filters."""

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
    WorkflowFilterProxyModel,
    WorkflowTableModel,
    allowed_transitions,
    preferred_next_status,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _record(
    *,
    record_id: str,
    kind: BusinessRecordKind,
    status: BusinessStatus,
    title: str,
) -> BusinessWorkflowRecord:
    return BusinessWorkflowRecord(
        id=record_id,
        kind=kind.value,
        tender_id="10",
        title=title,
        status=status.value,
        updated_at="2026-07-11T12:00:00",
    )


def test_proposal_normal_status_flow() -> None:
    assert (
        preferred_next_status(
            BusinessRecordKind.PROPOSAL,
            BusinessStatus.DRAFT,
        )
        == BusinessStatus.REVIEW
    )
    assert (
        preferred_next_status(
            BusinessRecordKind.PROPOSAL,
            BusinessStatus.REVIEW,
        )
        == BusinessStatus.READY
    )
    assert (
        preferred_next_status(
            BusinessRecordKind.PROPOSAL,
            BusinessStatus.READY,
        )
        == BusinessStatus.SENT
    )


def test_project_can_be_blocked_during_installation() -> None:
    transitions = allowed_transitions(
        BusinessRecordKind.PROJECT,
        BusinessStatus.INSTALLATION,
    )

    assert BusinessStatus.COMMISSIONING in transitions
    assert BusinessStatus.BLOCKED in transitions


def test_filter_proxy_combines_kind_and_search() -> None:
    _app()
    model = WorkflowTableModel(
        [
            _record(
                record_id="proposal",
                kind=BusinessRecordKind.PROPOSAL,
                status=BusinessStatus.READY,
                title="КП на видеонаблюдение",
            ),
            _record(
                record_id="project",
                kind=BusinessRecordKind.PROJECT,
                status=BusinessStatus.ACTIVE,
                title="Монтаж СКУД",
            ),
        ]
    )
    proxy = WorkflowFilterProxyModel()
    proxy.setSourceModel(model)

    proxy.set_kind(BusinessRecordKind.PROPOSAL)
    assert proxy.rowCount() == 1

    proxy.set_search("скуд")
    assert proxy.rowCount() == 0

    proxy.set_kind(None)
    assert proxy.rowCount() == 1
