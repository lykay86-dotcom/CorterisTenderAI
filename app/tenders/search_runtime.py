"""Composition root for the tender-search subsystem."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.tenders.collector.participation_score_service import (
        CorterisParticipationScoreService,
    )
    from app.tenders.participation_decision_service import (
        ParticipationDecisionService,
    )
    from app.tenders.full_analysis import TenderFullAnalysisService
    from app.tenders.collector.aggregator_discovery import (
        AggregatorDiscoveryRepository,
    )
from app.tenders.corteris_search import CorterisTenderSearchService
from app.tenders.corteris_filter import (
    CorterisTenderClassifier,
    CorterisTenderFilter,
)
from app.tenders.matching_catalog import MatchingCatalogRepository
from app.tenders.commercial_estimator import CommercialEstimateRepository
from app.tenders.document_storage import (
    TenderDocumentDownloadService,
    TenderDocumentStore,
)
from app.tenders.document_text_extractor import (
    TenderDocumentTextService,
)
from app.tenders.requirement_analysis import (
    TenderAnalysisRepository,
    TenderRequirementAnalysisService,
)
from app.tenders.http_client import HttpTransport
from app.tenders.provider_factory import create_default_provider_registry
from app.tenders.provider_registry import TenderProviderRegistry
from app.tenders.search_engine import TenderSearchEngine
from app.tenders.search_profile_repository import (
    TenderSearchProfileRepository,
)
from app.tenders.search_profile_runner import TenderSearchProfileRunner
from app.tenders.tender_registry import TenderRegistryRepository


@dataclass(frozen=True, slots=True)
class TenderSearchRuntime:
    """Ready-to-use tender-search services sharing one configuration."""

    data_directory: Path
    repository: TenderSearchProfileRepository
    registry: TenderProviderRegistry
    engine: TenderSearchEngine
    search_service: CorterisTenderSearchService
    runner: TenderSearchProfileRunner
    tender_registry: TenderRegistryRepository | None = None
    document_store: TenderDocumentStore | None = None
    document_service: TenderDocumentDownloadService | None = None
    text_extraction_service: TenderDocumentTextService | None = None
    requirement_analysis_service: (
        TenderRequirementAnalysisService | None
    ) = None
    participation_score_service: (
        CorterisParticipationScoreService | None
    ) = None
    participation_decision_service: "ParticipationDecisionService | None" = None
    full_analysis_service: "TenderFullAnalysisService | None" = None
    matching_catalog_repository: MatchingCatalogRepository | None = None
    commercial_estimate_repository: CommercialEstimateRepository | None = None
    aggregator_discovery_repository: "AggregatorDiscoveryRepository | None" = None


def create_tender_search_runtime(
    data_directory: str | Path,
    *,
    http_transport: HttpTransport | None = None,
    max_workers: int = 6,
    timeout_seconds: float = 60.0,
) -> TenderSearchRuntime:
    """Build the production tender-search graph without network activity.

    Network requests are made only when ``runner.run(...)`` is called.
    """

    data_path = Path(data_directory).expanduser()
    data_path.mkdir(parents=True, exist_ok=True)

    repository = TenderSearchProfileRepository(
        data_path / "search_profiles.json"
    )
    repository.initialize()

    registry = create_default_provider_registry(
        http_transport=http_transport
    )
    engine = TenderSearchEngine(
        registry,
        max_workers=max_workers,
        timeout_seconds=timeout_seconds,
    )
    tender_registry = TenderRegistryRepository(
        data_path / "tender_registry.sqlite3"
    )
    tender_registry.initialize()
    matching_catalog_repository = MatchingCatalogRepository(
        data_path / "tender_registry.sqlite3"
    )
    matching_catalog_repository.initialize()
    search_service = CorterisTenderSearchService(
        engine,
        CorterisTenderFilter(
            CorterisTenderClassifier(
                matching_catalog_repository.load_profile()
            )
        ),
    )
    runner = TenderSearchProfileRunner(
        repository,
        search_service,
        tender_registry,
    )
    document_store = TenderDocumentStore(
        data_path / "tender_documents"
    )
    document_store.initialize()
    document_service = TenderDocumentDownloadService(
        registry,
        document_store,
        http_transport=http_transport,
    )
    text_extraction_service = TenderDocumentTextService(
        document_store,
        data_path / "tender_text",
    )
    text_extraction_service.initialize()
    analysis_repository = TenderAnalysisRepository(
        data_path / "tender_analysis.sqlite3"
    )
    analysis_repository.initialize()
    requirement_analysis_service = (
        TenderRequirementAnalysisService(
            text_extraction_service,
            analysis_repository,
        )
    )
    from app.tenders.collector.participation_score_service import (
        CorterisParticipationScoreService,
    )
    from app.tenders.collector.store import CollectorStateRepository
    from app.tenders.collector.company_capability import (
        CompanyCapabilityProfileRepository,
    )

    collector_state_repository = CollectorStateRepository(
        data_path / "tender_registry.sqlite3"
    )
    collector_state_repository.initialize()
    commercial_estimate_repository = CommercialEstimateRepository(
        data_path / "tender_registry.sqlite3"
    )
    commercial_estimate_repository.initialize()
    from app.tenders.collector.aggregator_discovery import (
        AggregatorDiscoveryRepository,
    )
    aggregator_discovery_repository = AggregatorDiscoveryRepository(
        data_path / "tender_registry.sqlite3"
    )
    aggregator_discovery_repository.initialize()
    participation_score_service = CorterisParticipationScoreService(
        tender_registry,
        collector_state_repository,
        text_service=text_extraction_service,
        requirement_analysis_service=requirement_analysis_service,
        capability_repository=CompanyCapabilityProfileRepository(
            data_path / "company_capability_profile.json"
        ),
        matching_catalog_repository=matching_catalog_repository,
    )
    from app.tenders.participation_decision_service import (
        ParticipationDecisionService,
    )
    participation_decision_service = ParticipationDecisionService(
        participation_score_service,
        collector_state_repository,
        commercial_estimate_repository,
    )
    from app.tenders.full_analysis import TenderFullAnalysisService
    from app.tenders.legacy_analysis_bridge import LegacyAnalysisBridge
    from app.tenders.safe_archive import SafeArchiveExtractor

    full_analysis_service = TenderFullAnalysisService(
        tender_registry,
        document_service,
        document_store,
        text_extraction_service,
        requirement_analysis_service,
        participation_score_service,
        archive_extractor=SafeArchiveExtractor(),
        legacy_bridge=LegacyAnalysisBridge(),
        commercial_estimate_repository=commercial_estimate_repository,
        summary_repository=collector_state_repository,
    )

    return TenderSearchRuntime(
        data_directory=data_path,
        repository=repository,
        registry=registry,
        engine=engine,
        search_service=search_service,
        runner=runner,
        tender_registry=tender_registry,
        document_store=document_store,
        document_service=document_service,
        text_extraction_service=text_extraction_service,
        requirement_analysis_service=(
            requirement_analysis_service
        ),
        participation_score_service=(
            participation_score_service
        ),
        participation_decision_service=participation_decision_service,
        full_analysis_service=full_analysis_service,
        matching_catalog_repository=matching_catalog_repository,
        commercial_estimate_repository=commercial_estimate_repository,
        aggregator_discovery_repository=aggregator_discovery_repository,
    )


__all__ = [
    "TenderSearchRuntime",
    "create_tender_search_runtime",
]
