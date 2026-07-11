"""Tests for readable and responsive workflow detail card."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
)

from app.repositories.business_metrics import BusinessMetricsRepository
from app.ui.pages.business_workflow_page import BusinessWorkflowPage


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _page(tmp_path) -> BusinessWorkflowPage:
    return BusinessWorkflowPage(
        repository=BusinessMetricsRepository(
            tmp_path / "workflow.json"
        )
    )


def test_detail_card_uses_stacked_readable_rows(tmp_path) -> None:
    _app()
    page = _page(tmp_path)

    assert (
        page.detail_form.rowWrapPolicy()
        == QFormLayout.RowWrapPolicy.WrapAllRows
    )
    assert page.detail_form.verticalSpacing() >= 14
    assert page.detail_title.wordWrap()
    assert page.detail_file.wordWrap()
    assert page.detail_title.minimumHeight() >= 38


def test_wide_layout_reserves_space_for_detail_card(tmp_path) -> None:
    _app()
    page = _page(tmp_path)

    page._apply_content_orientation(1600, force=True)

    assert (
        page.splitter.orientation()
        == Qt.Orientation.Horizontal
    )
    assert page.detail_panel.minimumWidth() >= 460


def test_compact_layout_places_detail_card_below_table(tmp_path) -> None:
    _app()
    page = _page(tmp_path)

    page._apply_content_orientation(1100, force=True)

    assert (
        page.splitter.orientation()
        == Qt.Orientation.Vertical
    )
    assert page.detail_panel.minimumWidth() == 0
    assert page.detail_scroll.widgetResizable()
