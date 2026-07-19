"""Tests for unified Dashboard data states."""

from __future__ import annotations

from dataclasses import replace
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.ui.dashboard.data_state import (
    DataState,
    DataStateKind,
    DataStatePanel,
)
from app.ui.dashboard.kpi_center import KpiCenter
from app.ui.dashboard.tender_feed import TenderFeed
from app.ui.viewmodels.dashboard_viewmodel import DashboardKpiState, DashboardViewModel


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_data_state_factories() -> None:
    assert DataState.ready().kind == DataStateKind.READY
    assert DataState.loading().blocking is True
    assert DataState.empty().has_action is True
    assert DataState.partial().blocking is False


def test_state_panel_action_emits_key() -> None:
    _app()
    panel = DataStatePanel()
    received: list[str] = []

    panel.action_requested.connect(received.append)
    panel.set_state(
        DataState.error(
            "Нет соединения",
            action_key="refresh_dashboard",
        )
    )
    panel.action_button.click()

    assert received == ["refresh_dashboard"]


def test_tender_feed_hides_table_for_blocking_state() -> None:
    _app()
    feed = TenderFeed()
    feed.set_data_state(DataState.loading())

    assert feed.data_state.kind == DataStateKind.LOADING
    assert feed.table.isHidden()
    assert not feed.state_panel.isHidden()

    feed.set_data_state(DataState.ready())
    assert not feed.table.isHidden()
    assert feed.state_panel.isHidden()


def test_kpi_center_renders_loading_and_restores_values() -> None:
    _app()
    kpi = replace(
        DashboardViewModel().state.kpis["new_tenders"],
        value="24",
        raw_value=24,
        trend="+5 сегодня",
        state=DashboardKpiState.READY,
    )
    center = KpiCenter([kpi])
    card = center.cards["new_tenders"]

    center.set_data_state(DataState.loading())
    assert card.value == "…"
    assert not card.isEnabled()

    center.set_data_state(DataState.ready())
    assert card.value == "24"
    assert card.isEnabled()
