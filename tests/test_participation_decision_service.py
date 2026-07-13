from __future__ import annotations

from types import SimpleNamespace

from app.tenders.collector.participation_score import ParticipationRecommendation
from app.tenders.collector.verification import TenderVerificationStatus
from app.tenders.commercial_estimator import CommercialEstimateStatus
from app.tenders.participation_decision import ParticipationDecisionRecommendation
from app.tenders.participation_decision_service import ParticipationDecisionService
from app.core.ai.schemas import AiDocumentAnalysis, AiEvidence, AiFinding, AiFindingStatus
from app.tenders.collector.stop_factor import StopFactorStatus


class _ScoreService:
    def __init__(self, score):
        self.score = score

    def latest(self, _key):
        return self.score


class _StateRepository:
    def __init__(self, verification=None, stop=None):
        self.verification = verification
        self.stop = stop
        self.saved = []

    def get_verification_state(self, _key):
        return self.verification

    def get_latest_stop_factor_assessment(self, _key):
        return self.stop

    def save_participation_decision(self, decision):
        self.saved.append(decision)


class _EstimateRepository:
    def __init__(self, estimate=None):
        self.estimate = estimate

    def latest(self, _key):
        return (None, self.estimate) if self.estimate is not None else None


class _AiRepository:
    def __init__(self, analysis):
        self.analysis = analysis

    def latest(self, _key):
        return self.analysis


def test_service_returns_data_insufficient_without_required_evidence() -> None:
    state = _StateRepository()
    decision = ParticipationDecisionService(
        _ScoreService(None), state, _EstimateRepository()
    ).evaluate("procurement:1")

    assert decision.recommendation == ParticipationDecisionRecommendation.DATA_INSUFFICIENT
    assert {item.code for item in decision.evidence} >= {
        "score_missing",
        "estimate_incomplete",
        "verification_incomplete",
    }
    assert decision.score == 0
    assert decision.missing
    assert decision.actions
    assert decision.confidence_level == "low"
    assert state.saved == [decision]


def test_service_maps_complete_existing_evidence_to_participate() -> None:
    score = SimpleNamespace(
        total_score=90,
        recommendation=ParticipationRecommendation.RECOMMENDED,
        recommendation_text="Рекомендуется участвовать",
    )
    verification = SimpleNamespace(
        registry_key="procurement:1",
        status=TenderVerificationStatus.VERIFIED_OFFICIAL_API,
        minimum_confidence=0.9,
    )
    estimate = SimpleNamespace(
        registry_key="procurement:1",
        status=CommercialEstimateStatus.COMPLETE,
    )
    decision = ParticipationDecisionService(
        _ScoreService(score), _StateRepository(verification), _EstimateRepository(estimate)
    ).evaluate("procurement:1")

    assert decision.recommendation == ParticipationDecisionRecommendation.PARTICIPATE
    assert decision.confidence == 0.75
    assert decision.score == 90
    assert decision.actions == (
        "Подготовить коммерческое предложение",
        "Проверить сроки подачи заявки",
    )


def test_verified_ai_risk_requires_review_but_unverified_does_not() -> None:
    score = SimpleNamespace(
        total_score=90,
        recommendation=ParticipationRecommendation.RECOMMENDED,
        recommendation_text="Participate",
    )
    verification = SimpleNamespace(
        registry_key="procurement:1",
        status=TenderVerificationStatus.VERIFIED_OFFICIAL_API,
        minimum_confidence=0.9,
    )
    estimate = SimpleNamespace(
        registry_key="procurement:1", status=CommercialEstimateStatus.COMPLETE
    )
    risk = AiFinding(
        "risk",
        "Short deadline",
        AiEvidence("doc", "10 days", confidence=0.8),
        AiFindingStatus.VERIFIED,
    )
    analysis = AiDocumentAnalysis("procurement:1", "Summary", risks=(risk,), status="complete")

    decision = ParticipationDecisionService(
        _ScoreService(score),
        _StateRepository(verification),
        _EstimateRepository(estimate),
        ai_analysis_repository=_AiRepository(analysis),
    ).evaluate("procurement:1")

    assert decision.recommendation == ParticipationDecisionRecommendation.PARTICIPATE_AFTER_REVIEW
    assert any(item.source == "ai_document_analysis" for item in decision.evidence)


def test_current_unverified_ai_result_overrides_stale_verified_repository_result() -> None:
    score = SimpleNamespace(
        total_score=90,
        recommendation=ParticipationRecommendation.RECOMMENDED,
        recommendation_text="Participate",
        components=(),
        missing_documents=(),
    )
    verification = SimpleNamespace(
        registry_key="procurement:1",
        status=TenderVerificationStatus.VERIFIED_OFFICIAL_API,
        minimum_confidence=0.9,
        missing_fields=(),
    )
    estimate = SimpleNamespace(
        registry_key="procurement:1",
        status=CommercialEstimateStatus.COMPLETE,
        margin_percent=20,
    )
    verified = AiFinding(
        "risk",
        "Old risk",
        AiEvidence("doc", "old quote", confidence=0.9),
        AiFindingStatus.VERIFIED,
    )
    stale = AiDocumentAnalysis("procurement:1", "Old", risks=(verified,), status="complete")
    current = AiDocumentAnalysis(
        "procurement:1",
        "Provider unavailable",
        status="provider_error",
    )
    service = ParticipationDecisionService(
        _ScoreService(score),
        _StateRepository(verification),
        _EstimateRepository(estimate),
        ai_analysis_repository=_AiRepository(stale),
    )

    decision = service.evaluate(
        "procurement:1",
        ai_document_analysis=current,
    )

    assert decision.recommendation == ParticipationDecisionRecommendation.PARTICIPATE
    assert not any(item.source == "ai_document_analysis" for item in decision.evidence)


def test_blocked_stop_factor_has_absolute_priority_over_high_score() -> None:
    score = SimpleNamespace(
        total_score=100,
        recommendation=ParticipationRecommendation.RECOMMENDED,
        recommendation_text="Participate",
        components=(),
        missing_documents=(),
    )
    stop = SimpleNamespace(
        registry_key="procurement:1",
        status=StopFactorStatus.BLOCKED_BY_REQUIREMENT,
        factors=(
            SimpleNamespace(
                title="Missing license",
                evidence=SimpleNamespace(remediation="Obtain required license"),
            ),
        ),
    )
    verification = SimpleNamespace(
        registry_key="procurement:1",
        status=TenderVerificationStatus.VERIFIED_OFFICIAL_API,
        minimum_confidence=1.0,
        missing_fields=(),
    )
    estimate = SimpleNamespace(
        registry_key="procurement:1",
        status=CommercialEstimateStatus.COMPLETE,
        margin_percent=20,
    )

    decision = ParticipationDecisionService(
        _ScoreService(score),
        _StateRepository(verification, stop),
        _EstimateRepository(estimate),
    ).evaluate("procurement:1")

    assert decision.recommendation == ParticipationDecisionRecommendation.DO_NOT_PARTICIPATE
    assert decision.score == 100
    assert decision.stop_factors == ("Missing license",)
    assert "Obtain required license" in decision.actions
    assert decision.evidence[0].impact == -100
