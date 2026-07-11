"""Tests for main-window tender search integration and background runs."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMainWindow

from app.tenders.search_profile_repository import (
    TenderSearchProfileRepository,
)
from app.tenders.search_runtime import TenderSearchRuntime
from app.ui.tender_search_ui_controller import (
    TenderSearchUiController,
)
from tests.tender_search_ui_helpers import make_profile_run


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


class ImmediateThreadPool:
    def start(self, runnable) -> None:
        runnable.run()


class FakeRunner:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[str] = []

    def run(self, profile_id: str):
        self.calls.append(profile_id)
        if self.error is not None:
            raise self.error
        return make_profile_run()


def _runtime(tmp_path, runner) -> TenderSearchRuntime:
    repository = TenderSearchProfileRepository(
        tmp_path / "search_profiles.json"
    )
    repository.initialize()
    return TenderSearchRuntime(
        data_directory=Path(tmp_path),
        repository=repository,
        registry=object(),
        engine=object(),
        search_service=object(),
        runner=runner,
    )


def test_controller_installs_tender_menu_action(tmp_path) -> None:
    app = _app()
    window = QMainWindow()
    controller = TenderSearchUiController(
        tmp_path,
        runtime=_runtime(tmp_path, FakeRunner()),
        thread_pool=ImmediateThreadPool(),
        parent=window,
    )

    action = controller.install_on_main_window(window)

    # Do not obtain the menu through repeated QAction.menu() calls.
    # On PySide6/Windows/offscreen those temporary wrappers may be
    # invalidated even though the real QMenu is still owned by QMenuBar.
    menu = controller._tender_menu

    assert menu is not None
    assert menu.objectName() == "tendersMenu"
    assert menu.menuAction() in window.menuBar().actions()
    assert action in menu.actions()
    assert action.objectName() == "actionTenderSearchProfiles"
    assert window._tender_search_ui_controller is controller
    assert window._tender_search_menu is menu

    app.processEvents()


def test_controller_runs_profile_and_opens_results(tmp_path) -> None:
    app = _app()
    window = QMainWindow()
    runner = FakeRunner()
    controller = TenderSearchUiController(
        tmp_path,
        runtime=_runtime(tmp_path, runner),
        thread_pool=ImmediateThreadPool(),
        parent=window,
    )
    controller.install_on_main_window(window)
    controller.open_profiles_dialog()

    controller.run_profile("video-surveillance")
    app.processEvents()

    assert runner.calls == ["video-surveillance"]
    assert len(controller.result_dialogs) == 1
    assert controller.result_dialogs[0].table.rowCount() == 1
    assert controller.profiles_dialog is not None
    assert not controller.profiles_dialog.isVisible()


def test_controller_reports_search_error_in_profiles_dialog(
    tmp_path,
) -> None:
    app = _app()
    window = QMainWindow()
    runner = FakeRunner(error=RuntimeError("ЕИС недоступна"))
    controller = TenderSearchUiController(
        tmp_path,
        runtime=_runtime(tmp_path, runner),
        thread_pool=ImmediateThreadPool(),
        parent=window,
    )
    controller.open_profiles_dialog()

    controller.run_profile("video-surveillance")
    app.processEvents()

    assert controller.result_dialogs == ()
    assert controller.profiles_dialog is not None
    assert "ЕИС недоступна" in (
        controller.profiles_dialog.panel.status_label.text()
    )
    assert controller.profiles_dialog.panel.run_button.isEnabled()
