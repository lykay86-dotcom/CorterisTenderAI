"""Registry-based participation scoring using available local evidence."""

from __future__ import annotations

from app.tenders.business_profile import BusinessCapabilityProjection
from app.tenders.collector.participation_score import (
    CorterisCompanyProfile,
    CorterisParticipationRanker,
    CorterisParticipationScore,
    ParticipationScoringContext,
)
from app.tenders.collector.company_capability import (
    CompanyCapabilityProfileRepository,
)
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.collector.stop_factor import StopFactorEngine
from app.tenders.matching_catalog import MatchingCatalogRepository
from app.tenders.corteris_filter import CorterisTenderClassifier
from app.tenders.document_text_extractor import TenderDocumentTextService
from app.tenders.requirement_analysis import (
    TenderRequirementAnalysisService,
)
from app.tenders.tender_registry import TenderRegistryRepository


class CorterisParticipationScoreService:
    """Recalculate one registry tender and persist the latest score."""

    def __init__(
        self,
        tender_registry: TenderRegistryRepository,
        score_repository: CollectorStateRepository,
        *,
        text_service: TenderDocumentTextService | None = None,
        requirement_analysis_service: (TenderRequirementAnalysisService | None) = None,
        ranker: CorterisParticipationRanker | None = None,
        capability_repository: CompanyCapabilityProfileRepository | None = None,
        stop_factor_engine: StopFactorEngine | None = None,
        matching_catalog_repository: MatchingCatalogRepository | None = None,
        max_document_characters: int = 2_000_000,
    ) -> None:
        if max_document_characters < 1000:
            raise ValueError("max_document_characters must be at least 1000")
        self.tender_registry = tender_registry
        self.score_repository = score_repository
        self.text_service = text_service
        self.requirement_analysis_service = requirement_analysis_service
        self.ranker = ranker
        self.capability_repository = capability_repository
        self.stop_factor_engine = stop_factor_engine
        self.matching_catalog_repository = matching_catalog_repository
        self.max_document_characters = int(max_document_characters)

    def latest(
        self,
        registry_key: str,
    ) -> CorterisParticipationScore | None:
        return self.score_repository.get_latest_score(registry_key)

    def evaluate(
        self,
        registry_key: str,
        *,
        persist: bool = True,
    ) -> CorterisParticipationScore:
        normalized = registry_key.strip()
        if not normalized:
            raise ValueError("registry_key must not be empty")

        tender = self.tender_registry.get_tender(normalized)
        if tender is None:
            raise KeyError(f"Тендер не найден в реестре: {normalized}")

        texts: list[str] = []
        sources: list[str] = ["Карточка закупки"]
        if self.text_service is not None:
            latest_by_document = {}
            for result in self.text_service.list_results(normalized):
                if result.document_key not in latest_by_document:
                    latest_by_document[result.document_key] = result

            remaining = self.max_document_characters
            for result in latest_by_document.values():
                if not result.available_locally or remaining <= 0:
                    continue
                text = self.text_service.read_text(result)
                if not text:
                    continue
                excerpt = text[:remaining]
                texts.append(excerpt)
                remaining -= len(excerpt)
                source_name = (
                    result.source_path.name
                    if result.source_path is not None
                    else result.document_key
                )
                sources.append(source_name)

        analysis = (
            self.requirement_analysis_service.latest(normalized)
            if self.requirement_analysis_service is not None
            else None
        )
        if analysis is not None:
            sources.append("Структурированный анализ требований")

        ranker = self.ranker
        capability = (
            self.capability_repository.load() if self.capability_repository is not None else None
        )
        business_profile = (
            BusinessCapabilityProjection.from_capability(capability)
            if capability is not None
            else None
        )
        if ranker is None:
            ranker = (
                CorterisParticipationRanker(
                    CorterisCompanyProfile.from_business_profile(business_profile),
                    classifier=(
                        CorterisTenderClassifier(self.matching_catalog_repository.load_profile())
                        if self.matching_catalog_repository is not None
                        else None
                    ),
                )
                if business_profile is not None
                else CorterisParticipationRanker()
            )
        stop_engine = self.stop_factor_engine
        if stop_engine is None and business_profile is not None:
            stop_engine = StopFactorEngine(business_profile)
        stop_assessment = (
            stop_engine.evaluate(normalized, tender, analysis=analysis)
            if stop_engine is not None
            else None
        )
        score = ranker.score(
            tender,
            ParticipationScoringContext(
                document_texts=tuple(texts),
                requirement_analysis=analysis,
                evidence_sources=tuple(sources),
                stop_factor_assessment=stop_assessment,
            ),
        )
        if persist:
            self.score_repository.save_score(
                normalized,
                score,
                source="manual_recalculation",
            )
        return score


__all__ = ["CorterisParticipationScoreService"]
