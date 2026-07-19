"""Tests for Dashboard KPI Center."""

from __future__ import annotations

from app.ui.viewmodels.dashboard_viewmodel import DashboardViewModel


def test_dashboard_has_six_kpis_in_stable_order() -> None:
    viewmodel = DashboardViewModel()

    assert [item.key for item in viewmodel.ordered_kpis()] == [
        "potential_profit",
        "new_tenders",
        "recommended",
        "proposals_in_work",
        "active_projects",
        "attention",
    ]


def test_set_kpi_preserves_existing_metadata() -> None:
    viewmodel = DashboardViewModel()

    viewmodel.set_kpi(
        "new_tenders",
        value="24",
        trend="+5 сегодня",
    )

    updated = viewmodel.state.kpis["new_tenders"]
    assert updated.value == "24"
    assert updated.trend == "+5 сегодня"
    assert updated.title == "Новые тендеры сегодня"
    assert updated.tone == "info"
