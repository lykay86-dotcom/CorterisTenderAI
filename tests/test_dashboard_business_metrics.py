"""Tests for Dashboard KPI synchronization with business metrics."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.repositories.business_metrics import (
    BusinessMetricsSnapshot,
)
from app.ui.controllers.dashboard_controller import (
    DashboardSnapshotBuilder,
)


NOW = datetime(2026, 7, 11, 12, 0)


def test_business_metrics_drive_kpi_values() -> None:
    builder = DashboardSnapshotBuilder()
    business = BusinessMetricsSnapshot(
        proposals_in_work=4,
        estimates_in_work=3,
        active_projects=2,
        attention=1,
        potential_profit=Decimal("870000"),
        profit_sources=3,
    )

    snapshot = builder.build(
        [],
        now=NOW,
        business=business,
    )
    values = {item.key: item.value for item in snapshot.kpis}
    trends = {item.key: item.trend for item in snapshot.kpis}

    assert values["potential_profit"] == "870 000 ₽"
    assert values["proposals_in_work"] == "4"
    assert values["active_projects"] == "2"
    assert values["attention"] == "1"
    assert trends["proposals_in_work"] == "Смет в работе: 3"


def test_analysis_profit_is_fallback_without_saved_estimates() -> None:
    class Analysis:
        estimated_profit = 150000
        created_at = NOW

    class Tender:
        id = 1
        number = "1"
        title = "Тендер"
        customer = ""
        nmck = 0
        deadline = ""
        score = 0
        status = "Новый"
        recommendation = ""
        platform = ""
        created_at = NOW
        analyses = [Analysis()]

    builder = DashboardSnapshotBuilder()
    snapshot = builder.build(
        [Tender()],
        now=NOW,
        business=BusinessMetricsSnapshot(),
    )
    profit = next(
        item
        for item in snapshot.kpis
        if item.key == "potential_profit"
    )

    assert profit.value == "150 000 ₽"
