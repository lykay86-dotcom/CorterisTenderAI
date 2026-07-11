"""Tests for registry navigation in TenderSearchUiController."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMainWindow

from app.tenders.search_profile_repository import (
    TenderSearchProfileRepository,
)
from app.tenders.search_runtime import TenderSearchRuntime
from app.tenders.tender_registry import TenderRegistryRepository
from app.ui.tender_search_ui_controller import TenderSearchUiController
from tests.test_tender_registry import _evaluated_tender, _run


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


class FakeRunner:
    def run(self, profile_id: str):
        return _run(_evaluated_tender())


def _runtime(tmp_path) -> TenderSearchRuntime:
    profiles = TenderSearchProfileRepository(
        tmp_path / "search_profiles.json"
    )
    profiles.initialize()
    registry = TenderRegistryRepository(
        tmp_path / "tender_registry.sqlite3"
    )
    registry.record_profile_run(
        _run(_evaluated_tender()),
        run_id="run-1",
    )
    return TenderSearchRuntime(
        data_directory=Path(tmp_path),
        repository=profiles,
        registry=object(),
        engine=object(),
        search_service=object(),
        runner=FakeRunner(),
        tender_registry=registry,
    )


def test_controller_installs_registry_menu_action(tmp_path) -> None:
    app = _app()
    window = QMainWindow()
    controller = TenderSearchUiController(
        tmp_path,
        runtime=_runtime(tmp_path),
        parent=window,
    )

    controller.install_on_main_window(window)
    menu = controller._tender_menu

    assert menu is not None
    assert controller.registry_action in menu.actions()
    assert controller.registry_action.objectName() == (
        "actionTenderRegistry"
    )
    assert controller.registry_action.isEnabled()
    app.processEvents()


def test_controller_opens_registry_dialog(tmp_path) -> None:
    app = _app()
    window = QMainWindow()
    controller = TenderSearchUiController(
        tmp_path,
        runtime=_runtime(tmp_path),
        parent=window,
    )
    controller.install_on_main_window(window)

    controller.open_registry_dialog()
    app.processEvents()

    assert controller.registry_dialog is not None
    assert controller.registry_dialog.table.rowCount() == 1
    assert controller.registry_dialog.isVisible()
