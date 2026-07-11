"""Tests for non-blocking profile-search busy state."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.tenders.search_profile_repository import (
    TenderSearchProfileRepository,
)
from app.ui.tender_search_profiles_dialog import (
    TenderSearchProfilesPanel,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_profile_panel_disables_editing_during_search(tmp_path) -> None:
    _app()
    repository = TenderSearchProfileRepository(
        tmp_path / "search_profiles.json"
    )
    panel = TenderSearchProfilesPanel(repository)

    panel.set_search_busy(True, profile_id="all-corteris")

    assert not panel.profile_list.isEnabled()
    assert not panel.save_button.isEnabled()
    assert not panel.run_button.isEnabled()
    assert panel.run_button.text() == "Идёт поиск…"
    assert "Выполняется поиск" in panel.status_label.text()

    panel.set_search_busy(False)

    assert panel.profile_list.isEnabled()
    assert panel.run_button.isEnabled()
    assert panel.run_button.text() == "Запустить поиск"
