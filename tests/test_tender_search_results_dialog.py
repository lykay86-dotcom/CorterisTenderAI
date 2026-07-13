"""Tests for ranked tender search results dialog."""

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


def test_results_dialog_displays_ranked_tender() -> None:
    _app()
    dialog = TenderSearchResultsDialog(make_profile_run())

    assert dialog.table.rowCount() == 1
    assert dialog.table.item(0, 0).text() == "88"
    assert dialog.table.item(0, 3).text() == ("Монтаж системы видеонаблюдения")
    assert dialog.selected_evaluated() is not None
    assert "ГБУ города Москвы" in dialog.details.toPlainText()
    assert "ЕИС Закупки" in dialog.provider_status.text()
    assert dialog.open_source_button.isEnabled()


def test_empty_results_dialog_shows_empty_state() -> None:
    _app()
    dialog = TenderSearchResultsDialog(make_profile_run(include_tender=False))

    assert dialog.table.rowCount() == 0
    assert not dialog.open_source_button.isEnabled()
    assert "не найдено" in dialog.details.toPlainText().casefold()


def test_results_dialog_emits_navigation_signals() -> None:
    _app()
    dialog = TenderSearchResultsDialog(make_profile_run())
    reruns: list[str] = []
    profiles: list[bool] = []
    dialog.rerun_requested.connect(reruns.append)
    dialog.profiles_requested.connect(lambda: profiles.append(True))

    dialog.rerun_button.click()
    dialog.profiles_button.click()

    assert reruns == ["video-surveillance"]
    assert profiles == [True]
