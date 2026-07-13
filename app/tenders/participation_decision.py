"""RM-107 unified, explainable participation-decision model.

This module deliberately contains no scoring policy.  It is the stable result
contract that the future decision service will populate from the existing
score, stop-factor, commercial-estimate and verification subsystems.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.tenders.collector.participation_score import (
    CorterisParticipationScore,
)
from app.tenders.collector.stop_factor import StopFactorAssessment
from app.tenders.collector.verification import TenderVerificationState
from app.tenders.commercial_estimator import CommercialEstimateResult


class ParticipationDecisionRecommendation(StrEnum):
    PARTICIPATE = "participate"
    PARTICIPATE_AFTER_REVIEW = "participate_after_review"
    DO_NOT_PARTICIPATE = "do_not_participate"
    DATA_INSUFFICIENT = "data_insufficient"


@dataclass(frozen=True, slots=True)
class ParticipationDecisionEvidence:
    """Public reason and source for one final decision conclusion."""

    code: str
    title: str
    detail: str
    confidence: float
    source: str

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (self.code, self.title, self.detail, self.source)
        ):
            raise ValueError("decision evidence fields must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

    def to_payload(self) -> dict[str, object]:
        return {
            "code": self.code,
            "title": self.title,
            "detail": self.detail,
            "confidence": self.confidence,
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class ParticipationDecisionInput:
    """Immutable snapshot of existing subsystems for one tender."""

    registry_key: str
    score: CorterisParticipationScore | None = None
    stop_factor_assessment: StopFactorAssessment | None = None
    commercial_estimate: CommercialEstimateResult | None = None
    verification: TenderVerificationState | None = None

    def __post_init__(self) -> None:
        if not self.registry_key.strip():
            raise ValueError("registry_key must not be empty")
        for item in (
            self.stop_factor_assessment,
            self.commercial_estimate,
            self.verification,
        ):
            if item is not None and item.registry_key != self.registry_key:
                raise ValueError("all decision inputs must use the same registry_key")


@dataclass(frozen=True, slots=True)
class ParticipationDecision:
    """One auditable recommendation; never a substitute for user approval."""

    decision_id: str
    registry_key: str
    recommendation: ParticipationDecisionRecommendation
    confidence: float
    summary: str
    evidence: tuple[ParticipationDecisionEvidence, ...]
    input: ParticipationDecisionInput
    decided_at: str
    policy_version: str

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (
                self.decision_id,
                self.registry_key,
                self.summary,
                self.decided_at,
                self.policy_version,
            )
        ):
            raise ValueError("decision identity fields must not be empty")
        if self.input.registry_key != self.registry_key:
            raise ValueError("decision input registry_key must match decision")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if not self.evidence:
            raise ValueError("a decision must contain evidence")

    def to_payload(self) -> dict[str, object]:
        """Return only decision-facing data; raw credentials are never present."""
        return {
            "decision_id": self.decision_id,
            "registry_key": self.registry_key,
            "recommendation": self.recommendation.value,
            "confidence": self.confidence,
            "summary": self.summary,
            "evidence": [item.to_payload() for item in self.evidence],
            "decided_at": self.decided_at,
            "policy_version": self.policy_version,
            "score": (
                self.input.score.to_payload() if self.input.score is not None else None
            ),
            "stop_factor_status": (
                self.input.stop_factor_assessment.status.value
                if self.input.stop_factor_assessment is not None
                else None
            ),
            "commercial_estimate_status": (
                self.input.commercial_estimate.status.value
                if self.input.commercial_estimate is not None
                else None
            ),
            "verification_status": (
                self.input.verification.status.value
                if self.input.verification is not None
                else None
            ),
        }


__all__ = [
    "ParticipationDecision",
    "ParticipationDecisionEvidence",
    "ParticipationDecisionInput",
    "ParticipationDecisionRecommendation",
]
