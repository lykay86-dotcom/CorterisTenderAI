"""Expected RM-142 one-owner shell navigation integration."""

from __future__ import annotations

import os
import socket

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QStackedWidget, QWidget

from app.ui.navigation import (
    NavigationCause,
    NavigationStatus,
    RouteId,
    RouteRequest,
)
from app.ui.widgets.dashboard_layout import DashboardLayout


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _layout() -> tuple[DashboardLayout, dict[str, QWidget]]:
    _app()
    layout = DashboardLayout()
    pages = {
        "dashboard": QWidget(),
        "tenders": QWidget(),
        "quotes": QWidget(),
        "estimates": QWidget(),
    }
    layout.add_page("dashboard", "Рабочий стол", pages["dashboard"])
    layout.add_page("tenders", "Тендеры и рабочие модули", pages["tenders"])
    layout.add_page("quotes", "КП, сметы и проекты", pages["quotes"])
    layout.add_page("estimates", "КП, сметы и проекты", pages["estimates"])
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
