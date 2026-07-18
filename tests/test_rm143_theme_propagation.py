"""Expected RM-143 theme propagation and RM-142 compatibility guards."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget

from app.ui.modern_main_window import ModernMainWindow
from app.ui.navigation import DEFAULT_ROUTE_REGISTRY, RouteId
from app.ui.theme.colors import ThemeName


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_repeated_shell_theme_switch_preserves_route_and_one_owner(monkeypatch) -> None:
    _app()
    monkeypatch.setattr("app.ui.modern_main_window.DashboardController.start", lambda self: None)
    window = ModernMainWindow()
    snapshot = window.workspace.current_snapshot

    for theme in (ThemeName.LIGHT, ThemeName.DARK, ThemeName.LIGHT):
        window.apply_theme(theme)

    assert window.workspace.current_snapshot == snapshot
    assert window.findChildren(QMainWindow) == []
    assert window.findChildren(QStackedWidget) == [window.workspace.pages]
    assert tuple(spec.route_id for spec in DEFAULT_ROUTE_REGISTRY.primary_routes) == (
        RouteId.DASHBOARD,
        RouteId.TENDERS,
        RouteId.WORKFLOW,
    )
    window.dashboard_controller.shutdown()
    window.deleteLater()
