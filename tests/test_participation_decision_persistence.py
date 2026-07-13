from __future__ import annotations

from app.tenders.collector.deduplicator import TenderDeduplicator
from app.tenders.collector.normalizer import TenderNormalizer
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.participation_decision import (
    ParticipationDecision,
    ParticipationDecisionEvidence,
    ParticipationDecisionInput,
    ParticipationDecisionRecommendation,
)
from app.tenders.provider_base import TenderSearchQuery
from tests.collector_c3_helpers import make_tender


def test_participation_decision_is_persisted_in_registry_database(tmp_path) -> None:
    repository = CollectorStateRepository(tmp_path / "tender_registry.sqlite3")
    tender = make_tender()
    normalized = TenderNormalizer().normalize(tender)
    run_id = repository.start_run(TenderSearchQuery())
    repository.save_batch(
        run_id, TenderDeduplicator().deduplicate((normalized,))
    )
    decision = ParticipationDecision(
        decision_id="decision-1",
        registry_key=normalized.canonical_key,
        recommendation=ParticipationDecisionRecommendation.DATA_INSUFFICIENT,
        confidence=0.0,
        summary="Недостаточно данных для решения.",
        evidence=(
            ParticipationDecisionEvidence(
                code="missing",
                title="Данные",
                detail="Не хватает подтверждений.",
                confidence=0.0,
                source="verification",
            ),
        ),
        input=ParticipationDecisionInput(registry_key=normalized.canonical_key),
        decided_at="2026-07-13T00:00:00+00:00",
        policy_version="rm-107-policy-v1",
    )

    repository.save_participation_decision(decision)
    payload = repository.get_latest_participation_decision_payload(
        normalized.canonical_key
    )

    assert payload is not None
    assert payload["decision_id"] == "decision-1"
    assert payload["recommendation"] == "data_insufficient"
