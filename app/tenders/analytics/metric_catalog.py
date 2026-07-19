"""The one ordered RM-147 metric catalog."""

from app.tenders.analytics.contracts import AnalyticsMetricDefinition


TENDER_ANALYTICS_METRICS = (
    AnalyticsMetricDefinition(
        "tenders_discovered",
        "tender-discovery-v1",
        1,
        "Обнаруженные тендеры",
        "count",
    ),
    AnalyticsMetricDefinition(
        "tenders_by_status",
        "tender-status-current-v1",
        2,
        "Текущий состав по статусу",
        "count",
    ),
    AnalyticsMetricDefinition(
        "source_observations",
        "source-reference-observations-v1",
        3,
        "Наблюдения по источникам",
        "observation_count",
    ),
    AnalyticsMetricDefinition(
        "application_deadline_horizon",
        "deadline-horizon-v1",
        4,
        "Горизонт сроков подачи",
        "count",
    ),
)

METRIC_BY_ID = {item.metric_id: item for item in TENDER_ANALYTICS_METRICS}


__all__ = ["METRIC_BY_ID", "TENDER_ANALYTICS_METRICS"]
