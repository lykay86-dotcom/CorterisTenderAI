"""Expected RM-142 one-owner shell navigation integration."""

from __future__ import annotations

import os
import socket
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QStackedWidget, QWidget

from app.ui.navigation import (
    NavigationCause,
    NavigationStatus,
    RouteContext,
    RouteId,
    RouteRequest,
)
from app.ui.pages.business_workflow_page import WorkflowNavigationState
from app.ui.widgets.dashboard_layout import DashboardLayout
from tests.test_rm127_modern_main_window_composition import _window as _rm127_window


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _window(monkeypatch):
    monkeypatch.setattr(
        "app.ui.pages.business_workflow_page.SystemHealthMonitor.request_refresh",
        lambda _self: False,
    )
    return _rm127_window(monkeypatch)


def _layout() -> tuple[DashboardLayout, dict[str, QWidget]]:
    _app()
    layout = DashboardLayout()
    pages = {
        "dashboard": QWidget(),
        "tenders": QWidget(),
        "workflow": QWidget(),
    }
    layout.add_page("dashboard", "Рабочий стол", pages["dashboard"])
    layout.add_page("tenders", "Тендеры и рабочие модули", pages["tenders"])
    layout.add_page("workflow", "КП, сметы и проекты", pages["workflow"])
    return layout, pages


def test_sidebar_is_registry_driven_and_legacy_select_uses_one_owner() -> None:
    layout, pages = _layout()

    assert tuple(layout.sidebar._buttons) == ("dashboard", "tenders", "workflow")
    layout.sidebar.select("tenders")

    assert layout.pages.currentWidget() is pages["tenders"]
    assert layout.current_snapshot is not None
    assert layout.current_snapshot.route_id is RouteId.TENDERS
    assert layout.last_navigation_result.status is NavigationStatus.NAVIGATED
    assert layout.topbar.page_title.text() == "Тендеры и рабочие модули"
    assert layout.findChildren(QStackedWidget) == [layout.pages]


def test_unknown_and_planned_routes_do_not_change_current_page_or_history() -> None:
    layout, pages = _layout()
    layout.navigate(RouteRequest("dashboard"))
    history_size = len(layout.navigation_history)

    unknown = layout.navigate(RouteRequest("definitely-unknown"))
    planned = layout.navigate(RouteRequest("analytics"))

    assert unknown.status is NavigationStatus.UNKNOWN_ROUTE
    assert planned.status is NavigationStatus.UNAVAILABLE
    assert planned.resolved_route is RouteId.FUTURE_ANALYTICS
    assert layout.pages.currentWidget() is pages["dashboard"]
    assert len(layout.navigation_history) == history_size


def test_embedded_alias_activates_real_parent_and_back_restores_origin() -> None:
    layout, pages = _layout()
    calls = []
    layout.register_route_handler(RouteId.TENDER_AI, lambda context: calls.append(context) or True)
    layout.navigate(RouteRequest("dashboard"))

    result = layout.navigate(
        RouteRequest("ai", cause=NavigationCause.QUICK_ACTION, focus_token="QuickActionTile")
    )

    assert result.status is NavigationStatus.NAVIGATED
    assert layout.pages.currentWidget() is pages["tenders"]
    assert calls
    assert layout.sidebar.current_item == "tenders"

    returned = layout.back()
    assert returned.status is NavigationStatus.NAVIGATED
    assert layout.pages.currentWidget() is pages["dashboard"]


def test_registry_and_layout_composition_are_offline(monkeypatch) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("network I/O during route composition")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)

    layout, _pages = _layout()
    result = layout.navigate(RouteRequest("tenders", cause=NavigationCause.SIDEBAR))

    assert result.status is NavigationStatus.NAVIGATED


def test_production_shell_has_three_primary_areas_and_no_placeholder_pages(monkeypatch) -> None:
    app = _app()
    window = _window(monkeypatch)

    assert tuple(window.workspace.sidebar._buttons) == ("dashboard", "tenders", "workflow")
    assert tuple(window.workspace._page_index) == (
        "dashboard",
        "tenders",
        "workflow",
    )
    assert window.workspace.pages.count() == 3

    window.workspace.sidebar.select("ai")
    assert window.workspace.current_snapshot is not None
    assert window.workspace.current_snapshot.route_id is RouteId.TENDER_AI
    assert window.workspace.pages.currentWidget() is window.tender_workspace_page
    assert (
        window.tender_workspace_page.tabs.currentIndex()
        == window.tender_workspace_page._section_indexes["settings"]
    )
    assert (
        window.tender_workspace_page.settings_tabs.currentIndex()
        == window.tender_workspace_page._settings_section_indexes["ai"]
    )

    window.workspace.sidebar.select("analytics")
    assert window.workspace.last_navigation_result.status is NavigationStatus.UNAVAILABLE
    assert window.workspace.pages.currentWidget() is window.tender_workspace_page

    window.close()
    window.deleteLater()
    app.processEvents()


def test_dashboard_actions_and_back_preserve_workflow_intent(monkeypatch) -> None:
    app = _app()
    window = _window(monkeypatch)

    window.dashboard_page.create_proposal_requested.emit()
    assert window.workspace.current_snapshot is not None
    assert window.workspace.current_snapshot.route_id is RouteId.WORKFLOW_PROPOSALS
    assert window.workspace.pages.currentWidget() is window.quotes_page
    assert window.quotes_page.kind_filter.currentData() == "proposal"

    window.quotes_page.search_edit.setText("камера")
    window.dashboard_page.find_tenders_requested.emit()
    assert window.workspace.current_snapshot.route_id is RouteId.TENDERS

    returned = window.workspace.back()
    assert returned.status is NavigationStatus.NAVIGATED
    assert window.workspace.current_snapshot.route_id is RouteId.WORKFLOW_PROPOSALS
    assert window.quotes_page.search_edit.text() == "камера"

    window.quotes_page.apply_navigation_state(
        WorkflowNavigationState(kind="proposal", record_id=None)
    )
    window._navigate(
        RouteId.WORKFLOW_PROJECTS,
        cause=NavigationCause.PROGRAMMATIC,
        context=RouteContext(workflow_search="изменённый фильтр"),
    )
    assert window.quotes_page.search_edit.text() == "изменённый фильтр"

    returned = window.workspace.back()
    assert returned.status is NavigationStatus.NAVIGATED
    assert window.quotes_page.search_edit.text() == ""
    assert window.quotes_page.selected_record is None

    window.dashboard_page.create_estimate_requested.emit()
    assert window.workspace.current_snapshot.route_id is RouteId.WORKFLOW_ESTIMATES
    assert window.workspace.pages.currentWidget() is window.estimates_page
    assert window.estimates_page.kind_filter.currentData() == "estimate"

    window.close()
    window.deleteLater()
    app.processEvents()


def test_tender_deep_link_and_existing_controller_actions_converge(monkeypatch) -> None:
    app = _app()
    window = _window(monkeypatch)
    schedule_action = QAction(window)
    notifications_action = QAction(window)
    triggered: list[str] = []
    opened_documents: list[str] = []
    schedule_action.triggered.connect(lambda: triggered.append("schedule"))
    notifications_action.triggered.connect(lambda: triggered.append("notifications"))
    window._tender_search_ui_controller = SimpleNamespace(
        scheduler_ui_controller=SimpleNamespace(
            schedule_action=schedule_action,
            notifications_action=notifications_action,
        ),
        open_registry_documents=opened_documents.append,
        shutdown=lambda: True,
    )

    window._open_tender_from_dashboard("missing")
    assert window.workspace.current_snapshot is not None
    assert window.workspace.current_snapshot.route_id is RouteId.DASHBOARD

    window._open_tender_from_dashboard("tender-7")
    assert window.workspace.current_snapshot.route_id is RouteId.TENDERS
    assert window.tender_workspace_page.current_id == "tender-7"

    notification = window._navigate(
        RouteId.TENDER_NOTIFICATIONS,
        cause=NavigationCause.SHORTCUT,
    )
    scheduler = window._navigate(
        RouteId.TENDER_SCHEDULER,
        cause=NavigationCause.SHORTCUT,
    )
    documents = window._navigate(
        RouteId.TENDER_DOCUMENTS,
        cause=NavigationCause.DEEP_LINK,
        context=RouteContext(tender_id="000123"),
    )

    assert notification.status is NavigationStatus.NAVIGATED
    assert scheduler.status is NavigationStatus.NAVIGATED
    assert documents.status is NavigationStatus.NAVIGATED
    assert triggered == ["notifications", "schedule"]
    assert opened_documents == ["000123"]
    assert window.workspace.current_snapshot.route_id is RouteId.TENDERS

    window.close()
    window.deleteLater()
    app.processEvents()
