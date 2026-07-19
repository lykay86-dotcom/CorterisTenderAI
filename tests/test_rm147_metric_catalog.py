"""Expected-red catalog and time-boundary contracts for RM-147."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest


def test_metric_catalog_ids_versions_and_order_are_exact() -> None:
    from app.tenders.analytics import TENDER_ANALYTICS_METRICS

    assert tuple(
        (item.metric_id, item.version, item.order) for item in TENDER_ANALYTICS_METRICS
    ) == (
        ("tenders_discovered", "tender-discovery-v1", 1),
        ("tenders_by_status", "tender-status-current-v1", 2),
        ("source_observations", "source-reference-observations-v1", 3),
        ("application_deadline_horizon", "deadline-horizon-v1", 4),
    )


@pytest.mark.parametrize(
    ("grain", "expected_starts"),
    (
        ("day", ("2026-07-06T00:00:00+03:00", "2026-07-07T00:00:00+03:00")),
        ("week", ("2026-07-06T00:00:00+03:00",)),
        ("month", ("2026-07-01T00:00:00+03:00",)),
    ),
)
def test_aware_half_open_day_week_month_buckets_have_exact_boundaries(
    grain: str,
    expected_starts: tuple[str, ...],
) -> None:
    from app.tenders.analytics import AnalyticsGrain, AnalyticsInterval, iter_time_buckets

    interval = AnalyticsInterval(
        datetime.fromisoformat("2026-07-05T21:00:00+00:00"),
        datetime.fromisoformat("2026-07-07T21:00:00+00:00"),
        "+03:00",
    )
    buckets = iter_time_buckets(interval, AnalyticsGrain(grain))

    assert tuple(item.start_inclusive.isoformat() for item in buckets) == expected_starts
    assert buckets[0].start_inclusive == interval.start_inclusive
    assert buckets[-1].end_exclusive == interval.end_exclusive
    assert all(
        left.end_exclusive == right.start_inclusive for left, right in zip(buckets, buckets[1:])
    )


def test_naive_interval_bound_is_rejected() -> None:
    from app.tenders.analytics import AnalyticsInterval

    with pytest.raises(ValueError, match="timezone-aware"):
        AnalyticsInterval(
            datetime(2026, 7, 1),
            datetime(2026, 7, 2, tzinfo=timezone.utc),
            "UTC",
        )
