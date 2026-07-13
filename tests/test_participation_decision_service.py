from __future__ import annotations

from types import SimpleNamespace

from app.tenders.collector.participation_score import ParticipationRecommendation
from app.tenders.collector.verification import TenderVerificationStatus
from app.tenders.commercial_estimator import CommercialEstimateStatus
from app.tenders.participation_decision import ParticipationDecisionRecommendation
from app.tenders.participation_decision_service import ParticipationDecisionService
from app.core.ai.schemas import AiDocumentAnalysis, AiEvidence, AiFinding, AiFindingStatus


class _ScoreService:
    def __init__(self, score):
        self.score = score

    def latest(self, _key):
        return self.score


class _StateRepository:
    def __init__(self, verification=None, stop=None):
        self.verification = verification
        self.stop = stop

    def get_verification_state(self, _key):
        return self.verification

    def get_latest_stop_factor_assessment(self, _key):
        return self.stop


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
    decision = ParticipationDecisionService(
        _ScoreService(None), _StateRepository(), _EstimateRepository()
    ).evaluate("procurement:1")

    assert decision.recommendation == ParticipationDecisionRecommendation.DATA_INSUFFICIENT
    assert {item.code for item in decision.evidence} >= {
        "score_missing", "estimate_incomplete", "verification_incomplete"
    }


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


def test_verified_ai_risk_requires_review_but_unverified_does_not() -> None:
    score = SimpleNamespace(total_score=90, recommendation=ParticipationRecommendation.RECOMMENDED, recommendation_text="Participate")
    verification = SimpleNamespace(registry_key="procurement:1", status=TenderVerificationStatus.VERIFIED_OFFICIAL_API, minimum_confidence=0.9)
    estimate = SimpleNamespace(registry_key="procurement:1", status=CommercialEstimateStatus.COMPLETE)
    risk = AiFinding("risk", "Short deadline", AiEvidence("doc", "10 days", confidence=0.8), AiFindingStatus.VERIFIED)
    analysis = AiDocumentAnalysis("procurement:1", "Summary", risks=(risk,), status="complete")

    decision = ParticipationDecisionService(
        _ScoreService(score), _StateRepository(verification), _EstimateRepository(estimate),
        ai_analysis_repository=_AiRepository(analysis),
    ).evaluate("procurement:1")

    assert decision.recommendation == ParticipationDecisionRecommendation.PARTICIPATE_AFTER_REVIEW
    assert any(item.source == "ai_document_analysis" for item in decision.evidence)
