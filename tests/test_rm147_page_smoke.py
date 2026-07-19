"""Offscreen smoke for the one RM-147 physical page."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication

from app.tenders.collector.store import CollectorStateRepository
from app.tenders.tender_registry import TenderRegistryRepository
from app.ui.controllers.tender_analytics_controller import TenderAnalyticsController
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


def test_closed_filter_controls_build_the_same_immutable_query(tmp_path) -> None:
    _app()
    page = TenderAnalyticsPage()
    records = (
        replace(make_record("a", source_id="eis"), law="44-ФЗ"),
        replace(make_record("b", source_id="rts"), law="223-ФЗ"),
    )
    page.set_filter_options(records)
    page.source_combo.setCurrentIndex(page.source_combo.findData("eis"))
    page.status_combo.setCurrentIndex(page.status_combo.findData("published"))
    page.law_combo.setCurrentIndex(page.law_combo.findData("44-ФЗ"))
    page.preset_combo.setCurrentIndex(page.preset_combo.findData("custom"))
    page.start_date.setDate(QDate(2026, 7, 1))
    page.end_date.setDate(QDate(2026, 7, 10))
    path = tmp_path / "tender_registry.sqlite3"
    controller = TenderAnalyticsController(
        page,
        TenderRegistryRepository(path),
        CollectorStateRepository(path),
    )

    query = controller._query(
        datetime(2026, 7, 19, 9, tzinfo=timezone.utc),
        records,
    )

    assert query.interval.start_inclusive.isoformat() == "2026-07-01T00:00:00+03:00"
    assert query.interval.end_exclusive.isoformat() == "2026-07-10T00:00:00+03:00"
    assert query.source_ids == ("eis",)
    assert query.statuses == ("published",)
    assert query.laws == ("44-фз",)
