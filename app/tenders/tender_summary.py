"""RM-108 explainable, deterministic tender summary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping

from app.tenders.collector.company_capability import CompanyCapabilityProfile
from app.tenders.collector.stop_factor import StopFactorAssessment
from app.tenders.collector.verification import TenderVerificationState
from app.tenders.commercial_estimator import CommercialEstimateResult
from app.tenders.models import UnifiedTender
from app.tenders.participation_decision import ParticipationDecision
from app.tenders.requirement_analysis import TenderRequirementAnalysis


class TenderSummarySource(StrEnum):
    DETERMINISTIC = "deterministic"
    AI_ENHANCED = "ai_enhanced"


@dataclass(frozen=True, slots=True)
class TenderSummaryFact:
    label: str
    value: str
    source: str
    confidence: float
    provenance: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class TenderSummary:
    registry_key: str
    source: TenderSummarySource
    headline: str
    facts: tuple[TenderSummaryFact, ...]
    risks: tuple[str, ...]
    stop_factors: tuple[str, ...]
    missing_information: tuple[str, ...]
    company_profile: str
    financial_summary: str
    recommendation: str
    recommendation_confidence: float
    ai_explanation: str
    generated_at: str

    def __post_init__(self) -> None:
        if not self.registry_key.strip():
            raise ValueError("registry_key must not be empty")
        if not 0.0 <= self.recommendation_confidence <= 1.0:
            raise ValueError("recommendation_confidence must be between 0 and 1")

    def to_payload(self) -> dict[str, object]:
        return {
            "registry_key": self.registry_key,
            "source": self.source.value,
            "headline": self.headline,
            "facts": [
                {
                    "label": item.label,
                    "value": item.value,
                    "source": item.source,
                    "confidence": item.confidence,
                    "provenance": item.provenance,
                }
                for item in self.facts
            ],
            "risks": list(self.risks),
            "stop_factors": list(self.stop_factors),
            "missing_information": list(self.missing_information),
            "company_profile": self.company_profile,
            "financial_summary": self.financial_summary,
            "recommendation": self.recommendation,
            "recommendation_confidence": self.recommendation_confidence,
            "ai_explanation": self.ai_explanation,
            "generated_at": self.generated_at,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "TenderSummary":
        facts = payload.get("facts", ())
        return cls(
            registry_key=str(payload.get("registry_key", "")),
            source=TenderSummarySource(str(payload.get("source", "deterministic"))),
            headline=str(payload.get("headline", "")),
            facts=tuple(
                TenderSummaryFact(
                    label=str(item.get("label", "")),
                    value=str(item.get("value", "")),
                    source=str(item.get("source", "")),
                    confidence=float(item.get("confidence", 0.0)),
                    provenance=str(item.get("provenance", "")),
                )
                for item in facts
                if isinstance(item, Mapping)
            ),
            risks=_strings(payload.get("risks")),
            stop_factors=_strings(payload.get("stop_factors")),
            missing_information=_strings(payload.get("missing_information")),
            company_profile=str(payload.get("company_profile", "")),
            financial_summary=str(payload.get("financial_summary", "")),
            recommendation=str(payload.get("recommendation", "")),
            recommendation_confidence=float(payload.get("recommendation_confidence", 0.0)),
            ai_explanation=str(payload.get("ai_explanation", "")),
            generated_at=str(payload.get("generated_at", "")),
        )


class DeterministicTenderSummaryGenerator:
    """Assemble only existing evidence; never invent facts or a decision."""

    def generate(
        self,
        registry_key: str,
        tender: UnifiedTender,
        analysis: TenderRequirementAnalysis | None = None,
        *,
        decision: ParticipationDecision | None = None,
        verification: TenderVerificationState | None = None,
        stop_assessment: StopFactorAssessment | None = None,
        commercial_estimate: CommercialEstimateResult | None = None,
        company_profile: CompanyCapabilityProfile | None = None,
    ) -> TenderSummary:
        verified = verification is not None and verification.minimum_confidence > 0
        confidence = verification.minimum_confidence if verified else 0.0
        provenance = (
            f"verification:{verification.status.value}"
            if verification
            else "unverified:tender_card"
        )
        facts = (
            TenderSummaryFact(
                "Subject", tender.title or "Not specified", "tender_card", confidence, provenance
            ),
            TenderSummaryFact(
                "Customer",
                tender.customer.name or "Not specified",
                "tender_card",
                confidence,
                provenance,
            ),
            TenderSummaryFact(
                "NMCK",
                str(tender.price.amount) if tender.price else "Not specified",
                "tender_card",
                confidence,
                provenance,
            ),
            TenderSummaryFact(
                "Application deadline",
                tender.application_deadline.isoformat()
                if tender.application_deadline
                else "Not specified",
                "tender_card",
                confidence,
                provenance,
            ),
        )
        missing = list(verification.missing_fields if verification else ())
        if not tender.documents:
            missing.append("Tender documentation")
        if commercial_estimate is None:
            missing.append("Commercial estimate")
        if company_profile is None or not company_profile.is_configured:
            missing.append("Confirmed company capability profile")
        risks = tuple(
            item.title
            for item in (analysis.findings if analysis else ())
            if item.severity.value in {"warning", "critical"}
        )
        stop_factors = tuple(
            item.title for item in (stop_assessment.factors if stop_assessment else ())
        )
        profile = _profile_summary(company_profile)
        financial = _financial_summary(commercial_estimate)
        recommendation = decision.recommendation.value if decision else "data_insufficient"
        decision_confidence = decision.confidence if decision else 0.0
        explanation = (
            decision.summary if decision else "No final recommendation has been calculated."
        )
        return TenderSummary(
            registry_key=registry_key,
            source=TenderSummarySource.DETERMINISTIC,
            headline=tender.title or "Tender without a specified subject",
            facts=facts,
            risks=risks,
            stop_factors=stop_factors,
            missing_information=tuple(dict.fromkeys(missing)),
            company_profile=profile,
            financial_summary=financial,
            recommendation=recommendation,
            recommendation_confidence=decision_confidence,
            ai_explanation=explanation,
            generated_at=(verification.last_verified_at if verification else ""),
        )


class SafeTenderSummaryEnhancer:
    """Accept wording from AI only; all deterministic data remains immutable."""

    def enhance(self, summary: TenderSummary, explanation: str) -> TenderSummary:
        clean = explanation.strip()
        if not clean:
            return summary
        return TenderSummary(
            registry_key=summary.registry_key,
            source=TenderSummarySource.AI_ENHANCED,
            headline=summary.headline,
            facts=summary.facts,
            risks=summary.risks,
            stop_factors=summary.stop_factors,
            missing_information=summary.missing_information,
            company_profile=summary.company_profile,
            financial_summary=summary.financial_summary,
            recommendation=summary.recommendation,
            recommendation_confidence=summary.recommendation_confidence,
            ai_explanation=clean,
            generated_at=summary.generated_at,
        )


def _strings(value: object) -> tuple[str, ...]:
    return tuple(str(item) for item in value) if isinstance(value, (list, tuple)) else ()


def _profile_summary(profile: CompanyCapabilityProfile | None) -> str:
    if profile is None or not profile.is_configured:
        return "Company profile is not confirmed or incomplete."
    return f"{profile.company_name}: confirmed profile; missing sections: {', '.join(profile.missing_sections) or 'none'}."


def _financial_summary(estimate: CommercialEstimateResult | None) -> str:
    if estimate is None:
        return "Commercial estimate has not been prepared."
    return f"Status: {estimate.status.value}; profit: {estimate.profit if estimate.profit is not None else 'not calculated'}; margin: {estimate.margin_percent if estimate.margin_percent is not None else 'not calculated'}."


__all__ = [
    "DeterministicTenderSummaryGenerator",
    "SafeTenderSummaryEnhancer",
    "TenderSummary",
    "TenderSummaryFact",
    "TenderSummarySource",
]
