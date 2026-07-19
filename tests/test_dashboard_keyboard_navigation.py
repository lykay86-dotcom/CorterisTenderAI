"""Tests for Dashboard keyboard navigation."""

from __future__ import annotations

from dataclasses import replace
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QWidget

from app.ui.dashboard.keyboard_navigation import (
    DEFAULT_DASHBOARD_SHORTCUTS,
    DashboardShortcutManager,
)
from app.ui.dashboard.kpi_center import KpiCenter
from app.ui.dashboard.quick_actions import QuickActions
from app.ui.navigation.contracts import DashboardFilterId
from app.ui.viewmodels.dashboard_viewmodel import DashboardKpiState, DashboardViewModel


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _return_event() -> QKeyEvent:
    return QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Return,
        Qt.KeyboardModifier.NoModifier,
    )


def test_default_shortcuts_have_unique_keys_and_sequences() -> None:
    keys = [item.key for item in DEFAULT_DASHBOARD_SHORTCUTS]
    sequences = [item.sequence for item in DEFAULT_DASHBOARD_SHORTCUTS]

    assert len(keys) == len(set(keys))
    assert len(sequences) == len(set(sequences))


def test_shortcut_manager_emits_semantic_action() -> None:
    _app()
    host = QWidget()
    manager = DashboardShortcutManager(host)
    received: list[str] = []

    manager.action_requested.connect(received.append)
    manager.trigger("focus_tenders")

    assert received == ["focus_tenders"]


def test_quick_action_activates_with_enter() -> None:
    _app()
    actions = QuickActions()
    received: list[str] = []
    tile = actions.tiles[0]

    actions.action_requested.connect(received.append)
    tile.keyPressEvent(_return_event())

    assert received == ["find_tenders"]
    assert tile.focusPolicy() == Qt.FocusPolicy.StrongFocus


def test_kpi_card_activates_with_enter() -> None:
    _app()
    kpi = replace(
        DashboardViewModel().state.kpis["new_tenders"],
        value="5",
        raw_value=5,
        state=DashboardKpiState.READY,
    )
    center = KpiCenter([kpi])
    received: list[object] = []
    card = center.cards["new_tenders"]

    center.kpi_clicked.connect(received.append)
    card.keyPressEvent(_return_event())

    assert len(received) == 1
    assert received[0].filter_id is DashboardFilterId.TENDERS_CREATED_TODAY
    assert card.focusPolicy() == Qt.FocusPolicy.StrongFocus
