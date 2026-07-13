"""RM-108 deterministic, offline tender summary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.tenders.models import UnifiedTender
from app.tenders.requirement_analysis import TenderRequirementAnalysis


class TenderSummarySource(StrEnum):
    DETERMINISTIC = "deterministic"
    AI_ENHANCED = "ai_enhanced"


@dataclass(frozen=True, slots=True)
class TenderSummaryFact:
    label: str
    value: str
    source: str


@dataclass(frozen=True, slots=True)
class TenderSummary:
    registry_key: str
    source: TenderSummarySource
    headline: str
    facts: tuple[TenderSummaryFact, ...]
    risks: tuple[str, ...]
    missing_information: tuple[str, ...]
    generated_at: str


class DeterministicTenderSummaryGenerator:
    """Build a fact-only summary; it never invents or changes decisions."""

    def generate(
        self,
        registry_key: str,
        tender: UnifiedTender,
        analysis: TenderRequirementAnalysis | None = None,
    ) -> TenderSummary:
        facts = [
            TenderSummaryFact("Предмет", tender.title or "Не указан", "Карточка закупки"),
            TenderSummaryFact("Заказчик", tender.customer.name or "Не указан", "Карточка закупки"),
            TenderSummaryFact("НМЦК", str(tender.price.amount) if tender.price else "Не указана", "Карточка закупки"),
            TenderSummaryFact("Срок подачи", tender.application_deadline.isoformat() if tender.application_deadline else "Не указан", "Карточка закупки"),
        ]
        risks: tuple[str, ...] = ()
        missing: list[str] = []
        if not tender.documents:
            missing.append("Документация закупки")
        if analysis is not None:
            risks = tuple(item.title for item in analysis.findings if item.severity.value in {"warning", "critical"})
        return TenderSummary(
            registry_key=registry_key,
            source=TenderSummarySource.DETERMINISTIC,
            headline=tender.title or "Тендер без указанного предмета",
            facts=tuple(facts),
            risks=risks,
            missing_information=tuple(missing),
            generated_at="",
        )


__all__ = ["DeterministicTenderSummaryGenerator", "TenderSummary", "TenderSummaryFact", "TenderSummarySource"]
