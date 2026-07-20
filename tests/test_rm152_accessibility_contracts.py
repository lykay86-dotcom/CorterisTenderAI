"""Expected-red RM-152 keyboard, focus, semantics, and DPI contracts."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
import shiboken6
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.repositories.business_metrics import BusinessMetricsRepository
from app.tenders.provider_credentials import CredentialState, CredentialStateResult
from app.ui.business_workflow.system_health_badge import SystemHealthBadge
from app.ui.navigation import NavigationCause, RouteId, RouteRequest
from app.ui.provider_credentials_dialog import ProviderCredentialsDialog
from app.ui.theme.colors import DARK_PALETTE, ThemeName
from app.ui.theme.stylesheet import build_stylesheet
from app.ui.tender_search_ui_controller import TenderSearchUiController
from app.ui.widgets.topbar import TopBar
from tests.test_rm127_modern_main_window_composition import _window as _rm127_window


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _window(monkeypatch, tmp_path):
    repository = BusinessMetricsRepository(tmp_path / "business_workflow.json")
    monkeypatch.setattr(
        "app.ui.modern_main_window.BusinessMetricsRepository",
        lambda: repository,
    )
    monkeypatch.setattr(
        "app.ui.pages.business_workflow_page.SystemHealthMonitor.request_refresh",
        lambda _self: False,
    )
    monkeypatch.setattr(
        "app.ui.pages.business_workflow_page.BusinessWorkflowPage._initialize_database_safety",
        lambda _self: None,
    )
    monkeypatch.setattr(
        "app.ui.pages.business_workflow_page.BusinessWorkflowPage._check_automatic_backup",
        lambda _self: None,
    )
    return _rm127_window(monkeypatch)


def test_full_shell_tab_traversal_reaches_task_controls_without_page_subcycle(
    monkeypatch,
    tmp_path,
) -> None:
    app = _app()
    window = _window(monkeypatch, tmp_path)
    window.show()
    app.processEvents()
    expected = (
        "SidebarRoute_dashboard",
        "SidebarRoute_tenders",
        "SidebarRoute_workflow",
        "SidebarRoute_analytics",
        "TopBarTenderSearch",
        "TopBarAiButton",
        "TopBarNotificationsButton",
        "TopBarThemeButton",
        "TopBarProfileButton",
        "DashboardRefreshButton",
        "DashboardFindTendersAction",
        "QuickAction_find_tenders",
        "QuickAction_analyze_documents",
        "QuickAction_create_proposal",
        "QuickAction_create_estimate",
        "ActivityFeedScroll",
    )
    first = window.workspace.sidebar._buttons["dashboard"]
    first.setFocus(Qt.FocusReason.TabFocusReason)
    app.processEvents()
    observed: list[str] = []

    for _step in range(96):
        focused = app.focusWidget()
        assert focused is not None and focused.isVisibleTo(window) and focused.isEnabled()
        observed.append(focused.objectName())
        QTest.keyClick(focused, Qt.Key.Key_Tab)
        app.processEvents()
        if app.focusWidget() is first and len(observed) > 1:
            break

    try:
        assert tuple(item for item in observed if item in expected) == expected
        assert app.focusWidget() is first
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_empty_or_cell_focused_tender_table_releases_tab_to_next_task(
    monkeypatch,
    tmp_path,
) -> None:
    app = _app()
    window = _window(monkeypatch, tmp_path)
    window.show()
    window.workspace.navigate(RouteRequest(RouteId.TENDERS, cause=NavigationCause.PROGRAMMATIC))
    table = window.tender_workspace_page.table
    table.setFocus(Qt.FocusReason.TabFocusReason)
    app.processEvents()

    QTest.keyClick(table, Qt.Key.Key_Tab)
    app.processEvents()

    try:
        assert app.focusWidget() is not table
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_dark_theme_styles_every_native_surface_seen_in_owner_evidence() -> None:
    stylesheet = build_stylesheet(ThemeName.DARK.value)

    for selector in (
        "QTableCornerButton::section",
        "QAbstractScrollArea::corner",
        "QScrollBar:horizontal",
        "QScrollBar::add-line:vertical",
        "QScrollBar::add-line:horizontal",
        "QTabWidget::pane",
        "QTabBar::tab",
        "QProgressBar",
        "QProgressBar::chunk",
    ):
        assert selector in stylesheet


def test_shell_theme_change_rethemes_controller_owned_search_panel(
    monkeypatch,
    tmp_path,
) -> None:
    app = _app()
    window = _window(monkeypatch, tmp_path)
    controller = TenderSearchUiController(
        tmp_path,
        theme=ThemeName.LIGHT,
        parent=window,
    )
    controller.install_on_main_window(window)
    controller.install_on_tender_workspace(window.tender_workspace_page)

    window.apply_theme(ThemeName.DARK)

    try:
        assert controller._theme is ThemeName.DARK
        assert controller._unified_search_panel is not None
        assert DARK_PALETTE.panel_background in controller._unified_search_panel.styleSheet()
    finally:
        controller.shutdown()
        window.close()
        window.deleteLater()
        app.processEvents()


def test_credential_dialog_escape_restores_exact_live_origin() -> None:
    app = _app()
    parent = QWidget()
    layout = QVBoxLayout(parent)
    origin = QPushButton("Управление credential", parent)
    origin.setObjectName("CredentialOrigin")
    layout.addWidget(origin)
    parent.show()
    origin.setFocus(Qt.FocusReason.ShortcutFocusReason)
    app.processEvents()
    state = CredentialStateResult(
        provider_id="synthetic-provider",
        secret_name="synthetic-secret-name",
        state=CredentialState.CONFIGURED,
        message="Credential настроен",
        observed_at="2026-07-20T12:00:00+03:00",
    )
    dialog = ProviderCredentialsDialog(
        "synthetic-provider",
        "Синтетический источник",
        state=state,
        parent=parent,
    )
    dialog.show()
    dialog.activateWindow()
    app.processEvents()

    QTest.keyClick(dialog.token_input, Qt.Key.Key_Escape)
    app.processEvents()

    try:
        assert app.focusWidget() is origin
        assert dialog.token_input.text() == ""
    finally:
        dialog.close()
        parent.close()
        parent.deleteLater()
        app.processEvents()


def test_topbar_search_has_task_name_without_placeholder_dependency() -> None:
    _app()
    topbar = TopBar()

    assert topbar.search.accessibleName() == "Глобальный поиск тендеров"
    assert "профил" in topbar.search.accessibleDescription().casefold()


def test_unnamed_icon_only_control_is_rejected_by_shared_semantics() -> None:
    from app.ui.accessibility.semantics import require_accessible_name

    _app()
    tool = QToolButton()
    tool.setIcon(TopBar().theme_button.icon())

    with pytest.raises(ValueError, match="accessible name"):
        require_accessible_name(tool)


def test_system_health_status_exposes_text_state_not_color_only() -> None:
    _app()
    badge = SystemHealthBadge()

    assert badge.accessibleName() == "Состояние системы"
    assert "Проверка системы" in badge.accessibleDescription()
    assert "Проверка системы" in badge.text()


def test_global_focus_style_covers_tabs_scrolls_and_existing_controls() -> None:
    stylesheet = build_stylesheet("dark")

    assert "QTabBar::tab:focus" in stylesheet
    assert "QScrollArea:focus" in stylesheet
    assert "QTableView:focus" in stylesheet


def test_removed_focus_target_falls_back_without_touching_deleted_qobject() -> None:
    from app.ui.accessibility.focus import restore_focus

    app = _app()
    parent = QWidget()
    layout = QVBoxLayout(parent)
    removed = QPushButton("Удаляемая строка", parent)
    fallback = QPushButton("Таблица", parent)
    fallback.setObjectName("TableFallback")
    layout.addWidget(removed)
    layout.addWidget(fallback)
    parent.show()
    removed.setFocus()
    app.processEvents()
    shiboken6.delete(removed)

    restored = restore_focus(removed, fallback)
    app.processEvents()

    assert restored is fallback
    assert app.focusWidget() is fallback


def test_shell_supported_minimum_fits_1366x768_at_125_percent(
    monkeypatch,
    tmp_path,
) -> None:
    app = _app()
    window = _window(monkeypatch, tmp_path)
    logical_width = int(1366 / 1.25)
    logical_height = int(768 / 1.25)

    try:
        assert window.minimumWidth() <= logical_width
        assert window.minimumHeight() <= logical_height
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_long_russian_topbar_title_keeps_full_accessible_text() -> None:
    app = _app()
    topbar = TopBar()
    long_title = (
        "Реестр найденных тендеров с проверкой критических ограничений и подтверждением источника"
    )
    topbar.set_page_title(long_title)
    topbar.resize(760, 80)
    topbar.show()
    app.processEvents()

    try:
        assert topbar.page_title.accessibleName() == long_title
        assert topbar.page_title.toolTip() == long_title
        assert topbar.profile_button.geometry().right() <= topbar.contentsRect().right()
    finally:
        topbar.close()
        topbar.deleteLater()
        app.processEvents()


def test_offscreen_or_removed_monitor_geometry_is_clamped_deterministically() -> None:
    from app.ui.accessibility.geometry import Rect, clamp_rect_to_screens

    restored = clamp_rect_to_screens(
        Rect(-5000, -4000, 1180, 720),
        screens=(Rect(0, 0, 1093, 614),),
        minimum_size=(960, 540),
    )

    assert restored == Rect(0, 0, 1093, 614)


def test_native_matrix_validator_never_promotes_unobserved_cell_to_pass() -> None:
    from app.ui.accessibility.native_matrix import validate_native_matrix

    errors = validate_native_matrix(
        {
            "schema": "rm152-native-matrix-v1",
            "cells": [
                {
                    "id": "SR-01",
                    "status": "PASS",
                    "observed": False,
                    "environment": {},
                    "evidence": [],
                }
            ],
        },
        require_complete=True,
    )

    assert "SR-01: pass_without_observation" in errors
    assert "SR-01: missing_environment" in errors


def test_native_matrix_accepts_named_owner_exception_without_promoting_status() -> None:
    from app.ui.accessibility.native_matrix import validate_native_matrix

    cell = {
        "id": "SR-01-DEV",
        "status": "NOT_EXECUTED",
        "observed": False,
        "environment": {},
        "evidence": [],
        "note": "Native observation was unavailable.",
    }
    payload = {
        "schema": "rm152-native-matrix-v1",
        "owner_exception_decision": {
            "id": "RM152-OWNER-EXCEPTIONS-2026-07-20",
            "approved": True,
            "approved_by": "project_owner",
            "approved_at": "2026-07-20 Europe/Moscow",
            "policy": "Retain BLOCKED and NOT_EXECUTED statuses; never convert an exception to PASS.",
        },
        "owner_exceptions": [
            {
                "id": "RM152-EX-SR-01-DEV",
                "cell_id": "SR-01-DEV",
                "approved_by": "project_owner",
                "approved_at": "2026-07-20 Europe/Moscow",
                "environment": {
                    "available": "single 1920x1080 Windows host",
                    "unavailable": "complete dev screen-reader journey",
                },
                "reason": "The required complete journey was not executed in the available session.",
                "residual_risk": "Dev-only screen-reader regressions may remain undiscovered.",
                "status_retained": "NOT_EXECUTED",
                "accepted_without_pass": True,
            }
        ],
        "cells": [cell],
    }

    assert validate_native_matrix(payload, require_complete=True) == ()
    assert cell["status"] == "NOT_EXECUTED"
