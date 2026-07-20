from __future__ import annotations

from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from app.ui.navigation import NavigationCause, RouteId, RouteRequest
from app.ui.theme.colors import ThemeName
from scripts.benchmark_rm153_ui import _dispose, _window


def _opposite(theme: ThemeName) -> ThemeName:
    return ThemeName.LIGHT if theme is ThemeName.DARK else ThemeName.DARK


def test_reapplying_current_theme_is_idempotent(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    window = _window(tmp_path)
    try:
        with (
            patch.object(window, "setStyleSheet") as root_style,
            patch.object(window.dashboard_page, "set_theme") as dashboard_theme,
            patch.object(window.workflow_page, "apply_theme") as workflow_theme,
            patch.object(window.analytics_page, "apply_theme") as analytics_theme,
            patch.object(window._settings, "setValue") as persist_theme,
        ):
            window.apply_theme(window._theme)

        root_style.assert_not_called()
        dashboard_theme.assert_not_called()
        workflow_theme.assert_not_called()
        analytics_theme.assert_not_called()
        persist_theme.assert_not_called()
    finally:
        _dispose(window, app)


def test_theme_change_updates_only_active_page_then_updates_stale_page_on_route(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    window = _window(tmp_path)
    try:
        assert window.workspace.current_snapshot is not None
        assert window.workspace.current_snapshot.route_id is RouteId.DASHBOARD
        next_theme = _opposite(window._theme)

        with (
            patch.object(window.dashboard_page, "set_theme") as dashboard_theme,
            patch.object(window.workflow_page, "apply_theme") as workflow_theme,
            patch.object(window.analytics_page, "apply_theme") as analytics_theme,
        ):
            window.apply_theme(next_theme)

        dashboard_theme.assert_called_once_with(next_theme)
        workflow_theme.assert_not_called()
        analytics_theme.assert_not_called()

        result = window.workspace.navigate(
            RouteRequest(RouteId.WORKFLOW, cause=NavigationCause.PROGRAMMATIC)
        )
        assert result.succeeded

        window.apply_theme(_opposite(next_theme))
        with patch.object(window.dashboard_page, "set_theme") as dashboard_theme:
            result = window.workspace.navigate(
                RouteRequest(RouteId.DASHBOARD, cause=NavigationCause.PROGRAMMATIC)
            )

        assert result.succeeded
        dashboard_theme.assert_called_once_with(window._theme)
    finally:
        _dispose(window, app)
