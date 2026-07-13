"""RM-107.4 explicit participation-decision thresholds and gate priority."""

from __future__ import annotations

from dataclasses import dataclass

from app.tenders.collector.stop_factor import StopFactorStatus
from app.tenders.participation_decision import ParticipationDecisionRecommendation


@dataclass(frozen=True, slots=True)
class ParticipationDecisionPolicy:
    """The approved RM-107 bands; hard gates always outrank a score."""

    policy_version: str = "rm-107-policy-v1"
    no_participation_max: int = 39
    review_max: int = 74
    recommended_max: int = 89

    def __post_init__(self) -> None:
        if not 0 <= self.no_participation_max < self.review_max < self.recommended_max <= 100:
            raise ValueError("decision score thresholds must be strictly ordered within 0..100")
        if not self.policy_version.strip():
            raise ValueError("policy_version must not be empty")

    def recommendation_for_score(
        self,
        score: int,
    ) -> ParticipationDecisionRecommendation:
        if not 0 <= score <= 100:
            raise ValueError("score must be between 0 and 100")
        if score <= self.no_participation_max:
            return ParticipationDecisionRecommendation.DO_NOT_PARTICIPATE
        if score <= self.review_max:
            return ParticipationDecisionRecommendation.PARTICIPATE_AFTER_REVIEW
        return ParticipationDecisionRecommendation.PARTICIPATE

    def recommendation_for_stop_factor(
        self,
        status: StopFactorStatus | None,
    ) -> ParticipationDecisionRecommendation | None:
        if status == StopFactorStatus.BLOCKED_BY_REQUIREMENT:
            return ParticipationDecisionRecommendation.DO_NOT_PARTICIPATE
        if status == StopFactorStatus.DATA_INSUFFICIENT:
            return ParticipationDecisionRecommendation.DATA_INSUFFICIENT
        if status == StopFactorStatus.CONDITIONAL:
            return ParticipationDecisionRecommendation.PARTICIPATE_AFTER_REVIEW
        return None


__all__ = ["ParticipationDecisionPolicy"]
