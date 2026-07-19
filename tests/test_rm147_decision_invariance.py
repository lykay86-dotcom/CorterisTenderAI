"""Expected-red guard for deterministic decision authority during analytics reads."""

from __future__ import annotations

from tests.rm147_analytics_helpers import aggregate, make_record
from tests.test_tender_registry import _evaluated_tender, _run


def test_analytics_does_not_change_score_recommendation_or_stop_factor(tmp_path) -> None:
    from app.tenders.tender_registry import TenderRegistryRepository

    repository = TenderRegistryRepository(tmp_path / "tender_registry.sqlite3")
    repository.record_profile_run(_run(_evaluated_tender(score=88)), run_id="run-1")
    before = repository.get_by_procurement_number("0373100000126000001")
    assert before is not None

    snapshot = aggregate((make_record(before.registry_key, status=before.status),))
    after = repository.get_record(before.registry_key)

    assert snapshot.metrics
    assert after is not None
    assert (after.relevance_score, after.relevance_grade, after.last_accepted) == (
        before.relevance_score,
        before.relevance_grade,
        before.last_accepted,
    )
