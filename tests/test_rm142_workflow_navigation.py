"""Expected RM-142 workflow intent/filter/selection navigation contract."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.repositories.business_metrics import (
    BusinessMetricsRepository,
    BusinessRecordKind,
    BusinessStatus,
)
from app.ui.pages.business_workflow_page import (
    BusinessWorkflowPage,
    WorkflowNavigationState,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_workflow_navigation_round_trip_uses_stable_record_identity(tmp_path, monkeypatch) -> None:
    _app()
    monkeypatch.setattr(
        "app.ui.pages.business_workflow_page.SystemHealthMonitor.request_refresh",
        lambda _self: False,
    )
    repository = BusinessMetricsRepository(tmp_path / "workflow.json")
    proposal = repository.save_record(
        kind=BusinessRecordKind.PROPOSAL,
        tender_id="T-1",
        title="КП видеонаблюдение",
        status=BusinessStatus.READY,
    )
    estimate = repository.save_record(
        kind=BusinessRecordKind.ESTIMATE,
        tender_id="T-2",
        title="Смета видеонаблюдение",
        status=BusinessStatus.DRAFT,
    )
    page = BusinessWorkflowPage(repository=repository)
    page.search_edit.setText("видеонаблюдение")
    page.apply_navigation_state(
        WorkflowNavigationState(
            search_text="видеонаблюдение",
            kind=BusinessRecordKind.PROPOSAL.value,
            status="",
            archive_mode="active",
            record_id=proposal.id,
        )
    )

    saved = page.capture_navigation_state()
    assert saved.record_id == proposal.id
    assert saved.kind == BusinessRecordKind.PROPOSAL.value

    page.apply_navigation_state(
        WorkflowNavigationState(
            search_text="видеонаблюдение",
            kind=BusinessRecordKind.ESTIMATE.value,
            status="",
            archive_mode="active",
            record_id=proposal.id,
        )
    )
    assert page.selected_record is None

    page.apply_navigation_state(
        WorkflowNavigationState(
            search_text="видеонаблюдение",
            kind=BusinessRecordKind.ESTIMATE.value,
            status="",
            archive_mode="active",
            record_id=estimate.id,
        )
    )
    assert page.selected_record is not None
    assert page.selected_record.id == estimate.id

    page.apply_navigation_state(saved)
    assert page.selected_record is not None
    assert page.selected_record.id == proposal.id


def test_workflow_navigation_state_is_presentation_only() -> None:
    state = WorkflowNavigationState(
        search_text="",
        kind="project",
        status="active",
        archive_mode="active",
        record_id=None,
    )

    assert not hasattr(state, "repository")
    assert not hasattr(state, "record")
    assert state.record_id is None
