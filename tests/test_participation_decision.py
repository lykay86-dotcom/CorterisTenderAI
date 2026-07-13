from __future__ import annotations

import pytest

from app.tenders.participation_decision import (
    ParticipationDecision,
    ParticipationDecisionEvidence,
    ParticipationDecisionInput,
    ParticipationDecisionRecommendation,
)


def _evidence() -> ParticipationDecisionEvidence:
    return ParticipationDecisionEvidence(
        code="score_available",
        title="Предварительный рейтинг",
        detail="Рейтинг рассчитан по карточке закупки.",
        confidence=0.7,
        source="participation_score",
    )


def test_decision_model_keeps_evidence_and_public_payload() -> None:
    decision = ParticipationDecision(
        decision_id="decision-1",
        registry_key="procurement:1",
        recommendation=ParticipationDecisionRecommendation.DATA_INSUFFICIENT,
        confidence=0.7,
        summary="Недостаточно данных для решения.",
        evidence=(_evidence(),),
        input=ParticipationDecisionInput(registry_key="procurement:1"),
        decided_at="2026-07-13T00:00:00+00:00",
        policy_version="rm-107-v1",
    )

    payload = decision.to_payload()

    assert payload["recommendation"] == "data_insufficient"
    assert payload["evidence"] == [_evidence().to_payload()]
    assert payload["score"] == 0
    assert payload["score_details"] is None
    assert payload["reasons"][0]["impact"] == 0
    assert payload["reasons"][0]["factor"] == _evidence().title
    assert payload["explanation"] == decision.summary
    assert payload["confidence_level"] == "medium"
    assert payload["stop_factors"] == []
    assert payload["missing"] == []
    assert payload["actions"] == []


def test_decision_model_rejects_mismatched_input_key() -> None:
    with pytest.raises(ValueError, match="registry_key"):
        ParticipationDecision(
            decision_id="decision-1",
            registry_key="procurement:1",
            recommendation=ParticipationDecisionRecommendation.DATA_INSUFFICIENT,
            confidence=0.7,
            summary="Недостаточно данных для решения.",
            evidence=(_evidence(),),
            input=ParticipationDecisionInput(registry_key="procurement:2"),
            decided_at="2026-07-13T00:00:00+00:00",
            policy_version="rm-107-v1",
        )
