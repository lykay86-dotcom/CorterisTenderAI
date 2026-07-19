"""Focused RM-147 acceptance guards beyond the initial expected-red set."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest

from tests.rm147_analytics_helpers import aggregate, make_query, make_record


def _metric(snapshot, metric_id: str):
    return next(item for item in snapshot.metrics if item.metric_id == metric_id)


def test_ta03_counts_exact_observations_and_distinct_parent_contributors() -> None:
    from app.tenders.analytics import AnalyticsSourceObservation

    records = (make_record("a"), make_record("b", source_id="rts"))
    observations = (
        AnalyticsSourceObservation("a", "eis", "one", "2026-07-18T09:00:00+00:00"),
        AnalyticsSourceObservation("a", "eis", "two", "2026-07-18T10:00:00+00:00"),
        AnalyticsSourceObservation("b", "rts", "three", "2026-07-18T11:00:00+00:00"),
    )

    metric = _metric(aggregate(records, observations=observations), "source_observations")

    assert tuple(point.bucket_key for point in metric.points) == ("eis", "rts")
    assert metric.points[0].value == 2
    assert metric.points[0].contributor_ids == ("a",)
    assert metric.unit == "observation_count"


def test_ta04_uses_exact_local_calendar_horizon_boundaries() -> None:
    records = (
        make_record("expired", application_deadline="2026-07-18T23:59:59+03:00"),
        make_record("today", application_deadline="2026-07-19T00:00:00+03:00"),
        make_record("one-three", application_deadline="2026-07-22T23:59:59+03:00"),
        make_record("four-seven", application_deadline="2026-07-23T00:00:00+03:00"),
        make_record("later", application_deadline="2026-07-27T00:00:00+03:00"),
        make_record("unknown", application_deadline="2026-07-20T00:00:00"),
    )

    metric = _metric(aggregate(records), "application_deadline_horizon")
    memberships = {point.bucket_key: point.contributor_ids for point in metric.points}

    assert memberships == {
        "expired": ("expired",),
        "due_today": ("today",),
        "due_1_3_days": ("one-three",),
        "due_4_7_days": ("four-seven",),
        "due_later": ("later",),
        "unknown_or_unconfirmed": ("unknown",),
    }


def test_equivalent_instants_have_one_canonical_query_fingerprint() -> None:
    utc_query = make_query(
        start=datetime.fromisoformat("2026-07-17T21:00:00+00:00"),
        end=datetime.fromisoformat("2026-07-19T21:00:00+00:00"),
    )
    local_query = make_query(
        start=datetime.fromisoformat("2026-07-18T00:00:00+03:00"),
        end=datetime.fromisoformat("2026-07-20T00:00:00+03:00"),
    )

    assert utc_query.fingerprint == local_query.fingerprint


def test_unsupported_status_filter_fails_closed() -> None:
    from app.tenders.analytics import AnalyticsGrain, TenderAnalyticsQuery

    base = make_query()
    with pytest.raises(ValueError, match="unsupported status"):
        TenderAnalyticsQuery(
            base.interval,
            AnalyticsGrain.DAY,
            statuses=("provider_magic",),
        )


def test_explicit_record_limit_returns_too_large_without_sampling() -> None:
    from app.tenders.analytics import AnalyticsState, MAX_ANALYTICS_RECORDS

    records = tuple(
        make_record(f"record-{index:05d}") for index in range(MAX_ANALYTICS_RECORDS + 1)
    )
    snapshot = aggregate(records)

    assert snapshot.state is AnalyticsState.TOO_LARGE
    assert snapshot.reason_codes == ("record_limit_exceeded",)
    assert all(not metric.points for metric in snapshot.metrics)
    assert all(
        metric.evidence.excluded_count == MAX_ANALYTICS_RECORDS + 1 for metric in snapshot.metrics
    )


def test_late_generation_cannot_replace_the_displayed_snapshot() -> None:
    from app.tenders.analytics import TenderAnalyticsViewModel

    older = aggregate((make_record("old"),))
    newer = replace(aggregate((make_record("new"),)), generation=6)
    view_model = TenderAnalyticsViewModel()

    assert view_model.accept(newer, generation=6)
    assert not view_model.accept(older, generation=5)
    assert view_model.displayed_snapshot is newer


def test_bulk_collector_analytics_reads_are_passive_for_missing_database(tmp_path) -> None:
    from app.tenders.collector.store import CollectorStateRepository

    path = tmp_path / "missing.sqlite3"
    repository = CollectorStateRepository(path)

    assert repository.list_analytics_source_observations() == ()
    assert repository.list_analytics_conflicts() == ()
    assert not path.exists()


def test_repository_bulk_reads_share_registry_key_and_existing_deadline_owner(tmp_path) -> None:
    from datetime import timezone

    from app.tenders.analytics import resolve_timezone
    from app.tenders.collector.store import CollectorStateRepository
    from app.tenders.tender_registry import TenderRegistryRepository
    from tests.collector_c3_helpers import make_tender
    from tests.test_collector_store import _run_and_save

    path = tmp_path / "tender_registry.sqlite3"
    collector = CollectorStateRepository(path)
    deduplicated, _summary = _run_and_save(collector, make_tender(), "run-1")
    registry_key = deduplicated.items[0].canonical_key

    facts = TenderRegistryRepository(path).list_analytics_facts(
        deadline_now=datetime(2026, 7, 19, 9, tzinfo=timezone.utc),
        deadline_user_timezone=resolve_timezone("Europe/Moscow"),
    )
    observations = collector.list_analytics_source_observations()

    assert tuple(item.registry_key for item in facts) == (registry_key,)
    assert facts[0].application_deadline == "2026-07-20T12:00:00+00:00"
    assert tuple(item.registry_key for item in observations) == (registry_key,)


def test_csv_formula_safety_and_atomic_replace_use_snapshot_bytes(tmp_path) -> None:
    from app.tenders.analytics import export_snapshot_csv, write_export_atomically

    snapshot = aggregate((make_record("a"),))
    metric = _metric(snapshot, "tenders_by_status")
    point = replace(metric.points[0], bucket_label="=cmd")
    safe_metric = replace(metric, points=(point, *metric.points[1:]))
    safe_snapshot = replace(
        snapshot,
        metrics=(snapshot.metrics[0], safe_metric, *snapshot.metrics[2:]),
    )
    payload = export_snapshot_csv(safe_snapshot)
    target = tmp_path / "analytics.csv"
    target.write_bytes(b"previous")

    write_export_atomically(target, payload)

    assert b"'=cmd" in payload
    assert target.read_bytes() == payload
    assert not tuple(tmp_path.glob("*.tmp"))


def test_control_and_bidi_bucket_labels_are_rejected() -> None:
    snapshot = aggregate((make_record("a"),))
    point = _metric(snapshot, "tenders_by_status").points[0]

    with pytest.raises(ValueError, match="control"):
        replace(point, bucket_label="unsafe\u202e")
