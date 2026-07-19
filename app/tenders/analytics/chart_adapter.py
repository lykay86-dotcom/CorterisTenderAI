"""Translation-only adapter from RM-147 metrics to the RM-146 chart model."""

from __future__ import annotations

from decimal import Decimal

from app.tenders.analytics.contracts import (
    AnalyticsSourceCoverage,
    AnalyticsState,
    TenderAnalyticsMetric,
)
from app.ui.charts import (
    ChartAxis,
    ChartAxisScale,
    ChartKind,
    ChartPoint,
    ChartSeries,
    ChartSourceEvidence,
    ChartSpec,
    ChartState,
)


_STATE_MAP = {
    AnalyticsState.LOADING: ChartState.LOADING,
    AnalyticsState.READY: ChartState.READY,
    AnalyticsState.EMPTY: ChartState.EMPTY,
    AnalyticsState.PARTIAL: ChartState.PARTIAL,
    AnalyticsState.STALE: ChartState.STALE,
    AnalyticsState.CONFLICTED: ChartState.PARTIAL,
    AnalyticsState.ERROR: ChartState.ERROR,
    AnalyticsState.TOO_LARGE: ChartState.TOO_LARGE,
}


class TenderAnalyticsChartAdapter:
    """Translate exact point identity/order/value without business calculation."""

    def adapt(
        self,
        metric: TenderAnalyticsMetric,
        coverage: tuple[AnalyticsSourceCoverage, ...],
    ) -> ChartSpec:
        is_time = metric.metric_id == "tenders_discovered"
        evidence = tuple(
            ChartSourceEvidence(
                source_id=item.source_id,
                generation=0,
                observed_at=item.observed_at,
                record_count=item.item_count or 0,
                complete=item.outcome in {"success", "empty"},
                refresh_failed=item.outcome in {"failed", "timed_out"},
                reason=item.reason_code,
            )
            for item in coverage
            if item.observed_at is not None
        )
        translated_points: list[ChartPoint] = []
        for point in metric.points:
            x_value = point.bucket_start if is_time else point.bucket_key
            if x_value is None:
                raise ValueError("time metric point is missing bucket_start")
            translated_points.append(
                ChartPoint(
                    point.point_id,
                    x_value,
                    Decimal(point.value),
                    point.bucket_label,
                )
            )
        points = tuple(translated_points)
        detail = (
            "Есть нерешённый конфликт; подробности доступны в таблице данных."
            if metric.state is AnalyticsState.CONFLICTED
            else ""
        )
        return ChartSpec(
            chart_id=metric.metric_id.replace("_", "-"),
            kind=ChartKind.LINE if is_time else ChartKind.BAR,
            title=metric.title,
            x_axis=ChartAxis(
                ChartAxisScale.TIME if is_time else ChartAxisScale.CATEGORY,
                title="Период" if is_time else "Категория",
            ),
            y_axis=ChartAxis(ChartAxisScale.NUMERIC, title=metric.unit),
            series=(ChartSeries("values", metric.title, points),),
            state=_STATE_MAP[metric.state],
            source_evidence=evidence,
            state_detail=detail,
        )


__all__ = ["TenderAnalyticsChartAdapter"]
