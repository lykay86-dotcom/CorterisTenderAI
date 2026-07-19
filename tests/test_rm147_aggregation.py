"""Expected-red aggregation, time, and determinism contracts for RM-147."""

from __future__ import annotations

from datetime import datetime

from tests.rm147_analytics_helpers import aggregate, make_query, make_record


def _metric(snapshot, metric_id: str):
    return next(item for item in snapshot.metrics if item.metric_id == metric_id)


def _point(metric, bucket_key: str):
    return next(item for item in metric.points if item.bucket_key == bucket_key)


def test_ta01_uses_first_seen_only_and_never_falls_back() -> None:
    snapshot = aggregate(
        (
            make_record(
                "aware",
                first_seen_at="2026-07-18T09:00:00+00:00",
                published_at="2026-07-01T09:00:00+00:00",
                last_seen_at="2026-07-30T09:00:00+00:00",
            ),
            make_record(
                "naive",
                first_seen_at="2026-07-18T09:00:00",
                published_at="2026-07-18T09:00:00+00:00",
            ),
        )
    )
    metric = _metric(snapshot, "tenders_discovered")

    assert sum(point.value for point in metric.points) == 1
    assert metric.evidence.unknown_time_count == 1
    assert tuple(key for point in metric.points for key in point.contributor_ids) == ("aware",)


def test_ta02_normalizes_current_status_and_keeps_unknown_bucket() -> None:
    snapshot = aggregate(
        (
            make_record("published", status=" PUBLISHED "),
            make_record("unrecognized", status="provider_magic"),
        )
    )
    metric = _metric(snapshot, "tenders_by_status")

    assert tuple(point.bucket_key for point in metric.points) == (
        "published",
        "accepting_applications",
        "applications_closed",
        "review",
        "completed",
        "cancelled",
        "unknown",
    )
    assert _point(metric, "published").contributor_ids == ("published",)
    assert _point(metric, "unknown").contributor_ids == ("unrecognized",)


def test_utc_instant_is_bucketed_in_the_correct_local_day() -> None:
    query = make_query(
        start=datetime.fromisoformat("2026-07-18T00:00:00+03:00"),
        end=datetime.fromisoformat("2026-07-20T00:00:00+03:00"),
    )
    snapshot = aggregate(
        (make_record("local-19", first_seen_at="2026-07-18T21:30:00+00:00"),),
        query=query,
    )

    assert _point(_metric(snapshot, "tenders_discovered"), "2026-07-19").contributor_ids == (
        "local-19",
    )


def test_shuffled_input_produces_identical_points_order_and_export_bytes() -> None:
    from app.tenders.analytics import export_snapshot_json

    records = (
        make_record("c", status="completed"),
        make_record("a", status="published"),
        make_record("b", status="unknown"),
    )
    first = aggregate(records)
    second = aggregate(tuple(reversed(records)))

    assert first.fingerprint == second.fingerprint
    assert first.metrics == second.metrics
    assert export_snapshot_json(first) == export_snapshot_json(second)
