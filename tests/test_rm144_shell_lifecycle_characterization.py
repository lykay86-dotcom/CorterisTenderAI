"""Passing RM-144 characterization before lifecycle contract changes."""

from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget

from app.repositories.business_metrics import BusinessMetricsRepository
from app.ui.pages.business_workflow_page import BusinessWorkflowPage
from app.ui.pages.tender_workspace_page import TenderWorkspacePage
from tests.test_rm127_modern_main_window_composition import _window as _rm127_window
from tests.test_rm127_tender_workspace_contract import _isolate_page_dependencies


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _window(monkeypatch):
    monkeypatch.setattr(
        "app.ui.pages.business_workflow_page.SystemHealthMonitor.request_refresh",
        lambda _self: False,
    )
    return _rm127_window(monkeypatch)


def test_canonical_tender_page_is_directly_constructible(monkeypatch) -> None:
    app = _app()
    _isolate_page_dependencies(monkeypatch)
    page = TenderWorkspacePage()

    assert page.__class__ is TenderWorkspacePage
    assert page.findChildren(QMainWindow) == []

    page.close()
    page.deleteLater()
    app.processEvents()


def test_shell_keeps_one_stack_and_one_workflow_entry_point(monkeypatch) -> None:
    app = _app()
    window = _window(monkeypatch)

    assert window.findChildren(QMainWindow) == []
    assert window.workspace.findChildren(
        QStackedWidget,
        options=Qt.FindChildOption.FindDirectChildrenOnly,
    ) == [window.workspace.pages]
    assert isinstance(window.workflow_page, BusinessWorkflowPage)
    assert window.workflow_page.repository is window.business_repository
    assert not hasattr(window, "quotes_page")
    assert not hasattr(window, "estimates_page")
    assert window.tender_workspace_page.statusBar() is window.statusBar()

    window.close()
    window.deleteLater()
    app.processEvents()


def test_workflow_page_owns_repeating_and_startup_scheduling(tmp_path, monkeypatch) -> None:
    app = _app()
    startup_callbacks: list[tuple[int, str]] = []
    monkeypatch.setattr(
        "app.ui.pages.business_workflow_page.QTimer.singleShot",
        lambda delay, callback: startup_callbacks.append((delay, callback.__name__)),
    )
    monkeypatch.setattr(
        "app.ui.pages.business_workflow_page.SystemHealthMonitor.request_refresh",
        lambda _self: False,
    )

    page = BusinessWorkflowPage(repository=BusinessMetricsRepository(tmp_path / "workflow.json"))

    assert page._auto_backup_timer.parent() is page
    assert page._auto_backup_timer.interval() == 15 * 60 * 1000
    assert page._auto_backup_timer.isActive()
    assert page._system_health_timer.parent() is page
    assert page._system_health_timer.interval() == 2 * 60 * 1000
    assert page._system_health_timer.isActive()
    assert page.system_health_monitor.parent() is page
    assert [delay for delay, _name in startup_callbacks] == [0, 250]

    page.close()
    page.deleteLater()
    app.processEvents()


def test_tender_search_veto_prevents_terminal_owner_shutdown(monkeypatch) -> None:
    app = _app()
    window = _window(monkeypatch)
    calls: list[str] = []
    window._tender_search_ui_controller = SimpleNamespace(
        shutdown=lambda: calls.append("search") or False,
    )
    monkeypatch.setattr(
        window.dashboard_controller,
        "shutdown",
        lambda: calls.append("dashboard"),
    )

    assert window.close() is False
    app.processEvents()
    assert calls == ["search"]

    del window._tender_search_ui_controller
    window.close()
    window.deleteLater()
    app.processEvents()
