from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from app.tenders.collector.participation_score import ParticipationRecommendation
from app.tenders.collector.verification import TenderVerificationStatus
from app.tenders.commercial_estimator import CommercialEstimateStatus
from app.tenders.participation_decision import ParticipationDecisionRecommendation
from app.tenders.participation_decision_service import ParticipationDecisionService
from app.core.ai.schemas import (
    AI_ANALYSIS_SCHEMA_VERSION,
    AiAnalysisProvenance,
    AiDocument,
    AiDocumentAnalysis,
    AiEvidence,
    AiEvidenceVerificationMethod,
    AiFinding,
    AiFindingStatus,
    AiSourceSnapshot,
)
from app.core.ai.citations import resolve_citation
from app.tenders.collector.stop_factor import StopFactorStatus


def _verified_evidence(quote: str, confidence: float) -> AiEvidence:
    return AiEvidence(
        citation_id="cit_" + "a" * 32,
        document_id="doc",
        quote=quote,
        character_start=0,
        character_end=len(quote),
        section="",
        page=None,
        confidence=confidence,
        verification_method=AiEvidenceVerificationMethod.EXACT_QUOTE,
        checksum_sha256="b" * 64,
        source_ref="doc_" + "c" * 32,
        context_fingerprint="d" * 64,
    )


def _current_analysis_with_risk() -> AiDocumentAnalysis:
    fingerprint = "d" * 64
    checksum = "b" * 64
    document = AiDocument(
        "doc",
        "tender.pdf",
        "local_document_store",
        "pdf",
        "2026-07-14T10:00:00+00:00",
        "verified",
        "10 days",
        checksum,
        original_character_count=7,
    )
    evidence = resolve_citation(
        document_id="doc",
        quote="10 days",
        section="",
        page=None,
        confidence=0.8,
        documents=(document,),
        context_fingerprint=fingerprint,
    ).evidence
    assert evidence is not None
    source = AiSourceSnapshot(
        document_id="doc",
        display_name="tender.pdf",
        document_type="pdf",
        checksum_sha256=checksum,
        verification_status="verified",
        received_at="2026-07-14T10:00:00+00:00",
        truncated=False,
        included_character_count=7,
        original_character_count=7,
    )
    provenance = AiAnalysisProvenance(
        analysis_id="analysis_123",
        context_fingerprint=fingerprint,
        created_at="2026-07-14T10:01:00+00:00",
        prompt_version="3",
        output_schema_version="1",
        persisted_schema_version=AI_ANALYSIS_SCHEMA_VERSION,
        analyzer_version="4",
        context_version="2",
        citation_resolver_version="1",
        provider_id="openai",
        provider_model="gpt-5",
        provider_response_id="resp_" + "a" * 64,
        sources=(source,),
    )
    finding = AiFinding(
        "risk",
        "Short deadline",
        evidence,
        AiFindingStatus.VERIFIED,
    )
    return AiDocumentAnalysis(
        "procurement:1",
        "Summary",
        risks=(finding,),
        status="complete",
        provenance=provenance,
    )


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
    analysis = _current_analysis_with_risk()

    decision = ParticipationDecisionService(
        _ScoreService(score),
        _StateRepository(verification),
        _EstimateRepository(estimate),
        ai_analysis_repository=_AiRepository(analysis),
    ).evaluate("procurement:1")

    assert decision.recommendation == ParticipationDecisionRecommendation.PARTICIPATE_AFTER_REVIEW
    assert any(item.source == "ai_document_analysis" for item in decision.evidence)


def test_only_current_citation_can_add_ai_decision_evidence_or_action() -> None:
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
    current = _current_analysis_with_risk()
    finding = current.risks[0]
    assert finding.evidence is not None
    assert current.provenance is not None
    damaged_source = replace(current.provenance.sources[0], checksum_sha256="c" * 64)
    variants = (
        replace(current, provenance=None),
        replace(current, provenance=replace(current.provenance, context_fingerprint="e" * 64)),
        replace(current, provenance=replace(current.provenance, sources=(damaged_source,))),
        replace(
            current,
            risks=(
                replace(finding, evidence=replace(finding.evidence, citation_id="cit_" + "0" * 32)),
            ),
        ),
        replace(current, risks=(replace(finding, status=AiFindingStatus.UNVERIFIED),)),
    )

    for analysis in variants:
        decision = ParticipationDecisionService(
            _ScoreService(score),
            _StateRepository(verification),
            _EstimateRepository(estimate),
            ai_analysis_repository=_AiRepository(analysis),
        ).evaluate("procurement:1")

        assert decision.recommendation == ParticipationDecisionRecommendation.PARTICIPATE
        assert not any(item.source == "ai_document_analysis" for item in decision.evidence)
        assert not any("AI-" in action for action in decision.actions)


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
        _verified_evidence("old quote", 0.9),
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
        ai_analysis_repository=_AiRepository(_current_analysis_with_risk()),
    ).evaluate("procurement:1")

    assert decision.recommendation == ParticipationDecisionRecommendation.DO_NOT_PARTICIPATE
    assert decision.score == 100
    assert decision.stop_factors == ("Missing license",)
    assert "Obtain required license" in decision.actions
    assert decision.evidence[0].impact == -100
