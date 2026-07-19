"""Expected-red translation-only RM-146 chart adapter contract for RM-148."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.financial import (
    FinancialAnalyticsService,
    FinancialChartAdapter,
    FinancialMetricId,
    WorkflowFinancialFact,
    parse_money,
)


def test_chart_uses_exact_snapshot_value_without_recalculation() -> None:
    now = datetime(2026, 7, 19, 12, 0, tzinfo=ZoneInfo("Europe/Moscow"))
    fact = WorkflowFinancialFact(
        record_id="record-1",
        tender_id="T-1",
        kind="proposal",
        status="ready",
        total=parse_money("0.10"),
        profit=parse_money("0.01"),
        created_at=now,
    )
    snapshot = FinancialAnalyticsService().build((fact,), generated_at=now)
    metric = snapshot.metric(FinancialMetricId.POTENTIAL_PROFIT)

    chart = FinancialChartAdapter().adapt(metric)

    assert chart.series[0].points[0].y == Decimal("0.01")
    assert chart.series[0].points[0].label == "0.01 RUB"
    assert chart.y_axis.unit == "RUB"
    assert chart.series[0].points[0].point_id == "fa-02-current"
