"""Persistence and registry integration tests for participation scores."""

from __future__ import annotations

from datetime import datetime, timezone

from app.tenders.collector.deduplicator import TenderDeduplicator
from app.tenders.collector.normalizer import TenderNormalizer
from app.tenders.collector.participation_score import (
    CorterisParticipationRanker,
    ParticipationScoringContext,
)
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.provider_base import TenderSearchQuery
from app.tenders.tender_registry import TenderRegistryRepository
from tests.collector_c3_helpers import make_tender


def test_save_batch_persists_score_and_updates_registry(tmp_path) -> None:
    repository = CollectorStateRepository(
        tmp_path / "tender_registry.sqlite3"
    )
    tender = make_tender(deadline_day=30)
    normalized = TenderNormalizer().normalize(tender)
    deduplicated = TenderDeduplicator().deduplicate((normalized,))
    score = CorterisParticipationRanker().score(
        tender,
        ParticipationScoringContext(
            now=datetime(2026, 7, 12, tzinfo=timezone.utc)
        ),
    )
    run_id = repository.start_run(
        TenderSearchQuery(keywords=("видеонаблюдение",))
    )

    summary = repository.save_batch(
        run_id,
        deduplicated,
        rankings={normalized.canonical_key: score},
    )

    assert summary.ranked_count == 1
    assert repository.list_run_scores(run_id) == (score,)
    record = TenderRegistryRepository(repository.path).get_record(
        normalized.canonical_key
    )
    assert record is not None
    assert record.relevance_score == score.total_score
    assert record.relevance_grade == score.recommendation.value


def test_manual_score_is_deduplicated_by_fingerprint(tmp_path) -> None:
    repository = CollectorStateRepository(
        tmp_path / "tender_registry.sqlite3"
    )
    tender = make_tender()
    normalized = TenderNormalizer().normalize(tender)
    run_id = repository.start_run(TenderSearchQuery())
    repository.save_batch(
        run_id,
        TenderDeduplicator().deduplicate((normalized,)),
    )
    score = CorterisParticipationRanker().score(tender)

    repository.save_score(
        normalized.canonical_key,
        score,
        source="manual",
    )
    repository.save_score(
        normalized.canonical_key,
        score,
        source="manual",
    )

    with repository._connect() as connection:
        count = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM collector_tender_scores
            WHERE registry_key = ? AND source = 'manual'
            """,
            (normalized.canonical_key,),
        ).fetchone()["total"]
    assert count == 1
