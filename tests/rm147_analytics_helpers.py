"""Small deterministic fixtures for RM-147 contract tests."""

from __future__ import annotations

from datetime import datetime, timezone


def make_query(
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    timezone_name: str = "+03:00",
    source_ids: tuple[str, ...] = (),
):
    from app.tenders.analytics import (
        AnalyticsGrain,
        AnalyticsInterval,
        TenderAnalyticsQuery,
    )

    return TenderAnalyticsQuery(
        interval=AnalyticsInterval(
            start or datetime(2026, 7, 1, tzinfo=timezone.utc),
            end or datetime(2026, 8, 1, tzinfo=timezone.utc),
            timezone_name,
        ),
        grain=AnalyticsGrain.DAY,
        source_ids=source_ids,
    )


def make_record(
    registry_key: str,
    *,
    first_seen_at: str = "2026-07-18T09:00:00+00:00",
    last_seen_at: str = "2026-07-19T09:00:00+00:00",
    published_at: str = "2026-07-10T09:00:00+00:00",
    source_id: str = "eis",
    status: str = "published",
    application_deadline: str = "",
):
    from app.tenders.analytics import AnalyticsTenderFact

    return AnalyticsTenderFact(
        registry_key=registry_key,
        source_id=source_id,
        external_id=f"external-{registry_key}",
        status=status,
        first_seen_at=first_seen_at,
        last_seen_at=last_seen_at,
        published_at=published_at,
        application_deadline=application_deadline,
    )


def aggregate(records, *, query=None, outcomes=(), conflicts=(), observations=()):
    from app.tenders.analytics import TenderAnalyticsService

    return TenderAnalyticsService().aggregate(
        query or make_query(),
        tuple(records),
        source_observations=tuple(observations),
        provider_outcomes=tuple(outcomes),
        conflicts=tuple(conflicts),
        as_of=datetime(2026, 7, 19, 9, tzinfo=timezone.utc),
        generation=4,
    )
