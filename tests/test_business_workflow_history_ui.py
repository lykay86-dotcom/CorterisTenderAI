"""Tests for workflow audit history presentation."""

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


def test_selected_record_loads_readable_history(tmp_path) -> None:
    _app()
    repository = BusinessMetricsRepository(tmp_path / "workflow.json")
    record = repository.save_record(
        kind=BusinessRecordKind.PROPOSAL,
        tender_id="T-79",
        title="КП на видеонаблюдение",
        status=BusinessStatus.DRAFT,
        total=500000,
    )
    repository.update_status(
        record.id,
        BusinessStatus.REVIEW,
    )

    page = BusinessWorkflowPage(repository=repository)
    selected = repository.get_record(record.id)
    page._set_selected_record(selected)

    assert page.history_list.count() == 2
    combined = "\n".join(
        page.history_list.item(index).text() for index in range(page.history_list.count())
    )
    assert "Статус:" in combined
    assert "На проверке" in combined
    assert "Создана запись" in combined
