"""Expected-red provenance, partial, conflict, and stale contracts for RM-147."""

from __future__ import annotations

from datetime import datetime, timezone

from tests.rm147_analytics_helpers import aggregate, make_query, make_record


def test_failed_source_is_partial_and_never_an_exact_zero() -> None:
    from app.tenders.analytics import AnalyticsProviderOutcome, AnalyticsState

    outcome = AnalyticsProviderOutcome(
        source_id="eis",
        run_id="run-failed",
        outcome="failed",
        observed_at=datetime(2026, 7, 19, 8, tzinfo=timezone.utc),
        item_count=None,
        reason_code="provider_failed",
    )
    snapshot = aggregate((), query=make_query(source_ids=("eis",)), outcomes=(outcome,))

    assert snapshot.state is AnalyticsState.PARTIAL
    assert snapshot.coverage[0].outcome == "failed"
    assert snapshot.coverage[0].item_count is None


def test_stale_retained_snapshot_preserves_original_observation_time() -> None:
    from app.tenders.analytics import AnalyticsState, TenderAnalyticsViewModel

    snapshot = aggregate((make_record("a"),))
    view_model = TenderAnalyticsViewModel()
    assert view_model.accept(snapshot, generation=4)
    original_as_of = snapshot.as_of

    view_model.fail(generation=5, reason_code="repository_unavailable")

    assert view_model.state is AnalyticsState.STALE
    assert view_model.displayed_snapshot is snapshot
    assert view_model.displayed_snapshot.as_of == original_as_of
    assert view_model.generation == 5


def test_unresolved_bucket_conflict_remains_visible_and_selectable() -> None:
    from app.tenders.analytics import AnalyticsConflict, AnalyticsState

    snapshot = aggregate(
        (make_record("conflicted", status="published"),),
        conflicts=(
            AnalyticsConflict(
                registry_key="conflicted",
                field_name="status",
                unresolved=True,
            ),
        ),
    )
    status_metric = next(item for item in snapshot.metrics if item.metric_id == "tenders_by_status")
    unknown = next(item for item in status_metric.points if item.bucket_key == "unknown")

    assert snapshot.state is AnalyticsState.CONFLICTED
    assert unknown.contributor_ids == ("conflicted",)
    assert unknown.evidence.conflict_count == 1
    assert "unresolved_status_conflict" in unknown.evidence.reason_codes
