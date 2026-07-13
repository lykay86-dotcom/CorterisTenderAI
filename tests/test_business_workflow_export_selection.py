"""Tests for exporting currently visible workflow rows."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.repositories.business_metrics import (
    BusinessMetricsRepository,
    BusinessRecordKind,
    BusinessStatus,
)
from app.ui.pages.business_workflow_page import BusinessWorkflowPage


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_visible_records_respect_kind_filter(tmp_path) -> None:
    _app()
    repository = BusinessMetricsRepository(tmp_path / "workflow.json")
    repository.save_record(
        kind=BusinessRecordKind.PROPOSAL,
        tender_id="T-1",
        title="КП",
        status=BusinessStatus.READY,
    )
    repository.save_record(
        kind=BusinessRecordKind.PROJECT,
        tender_id="T-2",
        title="Проект",
        status=BusinessStatus.ACTIVE,
    )

    page = BusinessWorkflowPage(repository=repository)
    proposal_index = page.kind_filter.findData(BusinessRecordKind.PROPOSAL.value)
    page.kind_filter.setCurrentIndex(proposal_index)

    visible = page._visible_records()

    assert len(visible) == 1
    assert visible[0].kind == BusinessRecordKind.PROPOSAL.value


def test_export_filter_description_contains_active_filters(
    tmp_path,
) -> None:
    _app()
    page = BusinessWorkflowPage(repository=BusinessMetricsRepository(tmp_path / "workflow.json"))
    page.search_edit.setText("видеонаблюдение")

    description = page._export_filter_description()

    assert "Тип:" in description
    assert "Статус:" in description
    assert "Архив:" in description
    assert "Поиск: видеонаблюдение" in description
