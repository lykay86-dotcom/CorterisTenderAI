"""Translation-only adapter to the accepted RM-146 chart contract."""

from __future__ import annotations

from app.financial.contracts import FinancialMetricValue, FinancialUnit
from app.financial.decimal_codec import canonical_money, canonical_percentage
from app.ui.charts import (
    ChartAxis,
    ChartAxisScale,
    ChartKind,
    ChartPoint,
    ChartSeries,
    ChartSpec,
    ChartState,
)


class FinancialChartAdapter:
    def adapt(self, metric: FinancialMetricValue) -> ChartSpec:
        if metric.unit is FinancialUnit.MONEY:
            unit = metric.currency.value if metric.currency is not None else "UNKNOWN"
            label = (
                f"{canonical_money(metric.exact_value)} {unit}"
                if metric.exact_value is not None
                else "Missing"
            )
        else:
            unit = "percentage_point"
            label = (
                f"{canonical_percentage(metric.exact_value)} %"
                if metric.exact_value is not None
                else "Missing"
            )
        state = ChartState.READY if metric.exact_value is not None else ChartState.EMPTY
        return ChartSpec(
            chart_id=metric.metric_id.value,
            kind=ChartKind.BAR,
            title=metric.metric_id.value,
            x_axis=ChartAxis(ChartAxisScale.CATEGORY, title="Snapshot"),
            y_axis=ChartAxis(ChartAxisScale.NUMERIC, title=metric.metric_id.value, unit=unit),
            series=(
                ChartSeries(
                    "values",
                    metric.metric_id.value,
                    (
                        ChartPoint(
                            f"{metric.metric_id.value}-current",
                            "current",
                            metric.exact_value,
                            label,
                        ),
                    ),
                ),
            ),
            state=state,
            description=(
                f"Contributors: {', '.join(metric.contributor_ids)}"
                if metric.contributor_ids
                else "No contributors"
            ),
        )


__all__ = ["FinancialChartAdapter"]
