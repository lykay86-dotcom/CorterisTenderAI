"""Keyboard and accessible-text guards for the RM-147 page."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication

from app.ui.pages.tender_analytics_page import TenderAnalyticsPage
from tests.rm147_analytics_helpers import aggregate, make_record


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_keyboard_selection_uses_exact_rm146_point_identity_and_contributor() -> None:
    app = _app()
    page = TenderAnalyticsPage()
    page.set_snapshot(aggregate((make_record("exact", status="published"),)))
    chart = page._charts["tenders_by_status"]
    spy = QSignalSpy(page.contributor_activated)

    chart.canvas.setFocus()
    QTest.keyClick(chart.canvas, Qt.Key.Key_Right)
    assert chart.selection is not None
    QTest.keyClick(chart.canvas, Qt.Key.Key_Return)

    assert spy.count() == 1
    assert spy.at(0) == ["exact"]
    assert page.selection_label.text().startswith("published: 1")
    app.processEvents()


def test_page_has_explicit_filter_refresh_chart_and_export_tab_chain() -> None:
    _app()
    page = TenderAnalyticsPage()

    assert page.preset_combo.nextInFocusChain() is page.grain_combo
    assert page.grain_combo.nextInFocusChain() is page.include_archived
    assert page.include_archived.nextInFocusChain() is page.apply_button
    assert page.apply_button.nextInFocusChain() is page.reset_button
    assert page.reset_button.nextInFocusChain() is page.refresh_button
    candidate = page.refresh_button.nextInFocusChain()
    while candidate.focusPolicy() is Qt.FocusPolicy.NoFocus:
        candidate = candidate.nextInFocusChain()
    assert candidate is page._charts["tenders_discovered"].canvas
    assert page.export_json_button.text() == "Экспорт JSON"
    assert page.export_csv_button.text() == "Экспорт CSV"
