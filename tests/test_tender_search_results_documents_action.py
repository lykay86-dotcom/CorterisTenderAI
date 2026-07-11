"""Tests for the search-results documentation action."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.ui.tender_search_results_dialog import (
    TenderSearchResultsDialog,
)
from tests.tender_search_ui_helpers import make_profile_run


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_results_dialog_requests_selected_documents() -> None:
    app = _app()
    dialog = TenderSearchResultsDialog(make_profile_run())
    requested: list[object] = []
    dialog.documents_requested.connect(requested.append)

    dialog.documents_button.click()

    assert len(requested) == 1
    assert requested[0] is dialog.selected_evaluated().tender
    assert dialog.documents_button.isEnabled()
    app.processEvents()


def test_empty_results_disable_documents_button() -> None:
    app = _app()
    dialog = TenderSearchResultsDialog(
        make_profile_run(include_tender=False)
    )

    assert not dialog.documents_button.isEnabled()
    app.processEvents()
