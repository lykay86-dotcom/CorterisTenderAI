"""Offscreen smoke for the one RM-147 physical page."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.ui.pages.tender_analytics_page import TenderAnalyticsPage
from tests.rm147_analytics_helpers import aggregate, make_record


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_page_publishes_four_rm146_charts_text_and_exports() -> None:
    app = _app()
    page = TenderAnalyticsPage()
    snapshot = aggregate((make_record("a"), make_record("b", status="completed")))

    page.set_snapshot(snapshot)

    assert page.snapshot is snapshot
    assert tuple(page._charts) == tuple(metric.metric_id for metric in snapshot.metrics)
    assert page.text_table.rowCount() == sum(len(metric.points) for metric in snapshot.metrics)
    assert page.export_json_button.isEnabled()
    assert page.export_csv_button.isEnabled()
    assert snapshot.fingerprint[:12] in page.coverage_label.text()
    app.processEvents()
