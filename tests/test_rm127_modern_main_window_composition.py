"""RM-127 modern-shell composition, navigation and action parity."""

from __future__ import annotations

import os
import socket

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMainWindow

from app.ui.modern_main_window import ModernMainWindow
from app.ui.pages.tender_workspace_page import TenderWorkspacePage
from app.ui.tender_search_ui_controller import TenderSearchUiController
from tests.test_rm127_tender_workspace_contract import _isolate_page_dependencies


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _window(monkeypatch) -> ModernMainWindow:
    _isolate_page_dependencies(monkeypatch)
    monkeypatch.setattr(
        "app.ui.modern_main_window.DashboardController.start",
        lambda _self: None,
    )
    monkeypatch.setattr(
        socket.socket,
        "connect",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("network I/O during composition")
        ),
    )
    return ModernMainWindow()


def test_modern_shell_mounts_page_without_hidden_legacy_main_window(monkeypatch) -> None:
    app = _app()
    window = _window(monkeypatch)

    assert isinstance(window, QMainWindow)
    assert isinstance(window.tender_workspace_page, TenderWorkspacePage)
    assert not hasattr(window, "_legacy_window")
    assert window.findChildren(QMainWindow) == []
    tender_index, _title = window.workspace._page_index["tenders"]
    assert window.workspace.pages.widget(tender_index) is window.tender_workspace_page

    window.close()
    window.deleteLater()
    app.processEvents()


def test_dashboard_navigation_and_topbar_use_the_page_api(monkeypatch) -> None:
    app = _app()
    window = _window(monkeypatch)

    window._open_tender_from_dashboard("tender-7")
    assert window.workspace.sidebar.current_item == "tenders"
    assert window.tender_workspace_page.current_id == "tender-7"
    assert window.tender_workspace_page.table.currentRow() == 0

    previous_id = window.tender_workspace_page.current_id
    window._open_tender_from_dashboard("missing")
    assert window.workspace.sidebar.current_item == "tenders"
    assert window.tender_workspace_page.current_id == previous_id

    previous_tab = window.tender_workspace_page.tabs.currentIndex()
    window.tender_workspace_page.catalog_query.setText("прайс остаётся")
    window._global_search("  камеры  ")
    assert window.tender_workspace_page.catalog_query.text() == "прайс остаётся"
    assert window.tender_workspace_page.tabs.currentIndex() == previous_tab
    assert window.workspace.sidebar.current_item == "tenders"

    window.close()
    window.deleteLater()
    app.processEvents()


def test_controller_binds_the_same_actions_to_window_and_page(tmp_path, monkeypatch) -> None:
    app = _app()
    window = _window(monkeypatch)
    controller = TenderSearchUiController(tmp_path, parent=window)

    controller.install_on_main_window(window)
    controller.install_on_tender_workspace(window.tender_workspace_page)
    controller.install_on_tender_workspace(window.tender_workspace_page)

    expected = (
        controller.action,
        controller.registry_action,
        controller.providers_action,
        controller.collector_action,
        controller.company_capability_action,
        controller.matching_catalog_action,
        controller.aggregator_discovery_action,
        controller.scheduler_ui_controller.schedule_action,
        controller.scheduler_ui_controller.notifications_action,
    )
    assert tuple(window.tender_workspace_page.actions()) == expected
    assert all(action in controller._tender_menu.actions() for action in expected)
    assert all(action in controller._tender_toolbar.actions() for action in expected)
    assert len({id(action) for action in expected}) == len(expected)
    assert controller.action.shortcut().toString() == "Ctrl+Shift+F"
    assert controller.registry_action.shortcut().toString() == "Ctrl+Shift+R"
    assert controller.providers_action.shortcut().toString() == "Ctrl+Shift+S"
    assert controller.collector_action.shortcut().toString() == "Ctrl+Shift+C"

    window.close()
    window.deleteLater()
    app.processEvents()


def test_close_does_not_depend_on_a_legacy_wrapper(monkeypatch) -> None:
    app = _app()
    window = _window(monkeypatch)
    shutdown_calls: list[bool] = []
    monkeypatch.setattr(
        window.dashboard_controller,
        "shutdown",
        lambda: shutdown_calls.append(True),
    )

    assert window.close() is True
    app.processEvents()

    assert shutdown_calls == [True]
    assert not hasattr(window, "_legacy_window")
