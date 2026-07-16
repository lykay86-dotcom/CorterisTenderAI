"""Composition helpers for native asynchronous collector providers."""

from __future__ import annotations

from pathlib import Path

from app.tenders.business_profile import BusinessCapabilityProjection
from app.tenders.collector.async_engine import AsyncProviderSearchEngine
from app.tenders.collector.collector_service import CollectorService
from app.tenders.collector.company_capability import (
    CompanyCapabilityProfileRepository,
)
from app.tenders.collector.network_runtime import CollectorNetworkRuntime
from app.tenders.collector.participation_score import (
    CorterisCompanyProfile,
    CorterisParticipationRanker,
)
from app.tenders.collector.stop_factor import StopFactorEngine
from app.tenders.matching_catalog import MatchingCatalogRepository
from app.tenders.corteris_filter import CorterisTenderClassifier
from app.tenders.collector.provider_settings import (
    ProviderEnablementRepository,
)
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.providers.commercial_adapter import (
    create_commercial_access_providers,
)
from app.tenders.providers.commercial_catalog import (
    CommercialProviderCatalog,
    create_commercial_provider_catalog,
)
from app.tenders.providers.eis_async import AsyncEisTenderProvider
from app.tenders.providers.mos_supplier_api import (
    AsyncMosSupplierTenderProvider,
    MosSupplierApiConfig,
)


def create_default_async_providers(
    network_runtime: CollectorNetworkRuntime,
    *,
    repository: CollectorStateRepository | None = None,
    mos_supplier_config: MosSupplierApiConfig | None = None,
    include_commercial_catalog: bool = False,
    commercial_catalog: CommercialProviderCatalog | None = None,
    provider_settings_repository: (ProviderEnablementRepository | None) = None,
    include_disabled: bool = False,
):
    """Return implemented providers and optional visible access adapters.

    Commercial adapters are excluded by default. When explicitly requested,
    only providers enabled by the user are added, and they remain honest
    ``not_configured`` adapters until a real API contract is verified.
    """

    providers = [
        AsyncEisTenderProvider(
            network_runtime.http_client,
            network_settings=network_runtime.settings.get("eis"),
            checkpoint_repository=repository,
        ),
        AsyncMosSupplierTenderProvider(
            network_runtime.http_client,
            config=(mos_supplier_config or MosSupplierApiConfig.from_environment()),
            network_settings=network_runtime.settings.get("mos_supplier"),
            checkpoint_repository=repository,
        ),
    ]
    if include_commercial_catalog:
        catalog = commercial_catalog or create_commercial_provider_catalog()
        providers.extend(
            create_commercial_access_providers(
                catalog.resolve_all(),
                enabled_only=(provider_settings_repository is None and not include_disabled),
            )
        )

    if provider_settings_repository is not None:
        providers = [
            provider
            for provider in providers
            if (include_disabled or provider_settings_repository.is_enabled(provider.descriptor))
        ]
    return tuple(providers)


def create_default_collector_service(
    data_directory: str | Path,
    network_runtime: CollectorNetworkRuntime,
    *,
    provider_timeout_seconds: float = 90.0,
    mos_supplier_config: MosSupplierApiConfig | None = None,
    include_commercial_catalog: bool = False,
    commercial_catalog: CommercialProviderCatalog | None = None,
    provider_settings_repository: (ProviderEnablementRepository | None) = None,
) -> CollectorService:
    """Build the first production collector pipeline without network I/O."""

    data_path = Path(data_directory).expanduser()
    data_path.mkdir(parents=True, exist_ok=True)
    repository = CollectorStateRepository(data_path / "tender_registry.sqlite3")
    repository.initialize()
    source_settings = provider_settings_repository or ProviderEnablementRepository(
        data_path / "collector_provider_settings.json"
    )
    providers = create_default_async_providers(
        network_runtime,
        repository=repository,
        mos_supplier_config=mos_supplier_config,
        include_commercial_catalog=include_commercial_catalog,
        commercial_catalog=commercial_catalog,
        provider_settings_repository=source_settings,
    )
    engine = AsyncProviderSearchEngine(
        providers,
        health_monitor=network_runtime.health_monitor,
        provider_timeout_seconds=provider_timeout_seconds,
    )
    capability = CompanyCapabilityProfileRepository(
        data_path / "company_capability_profile.json"
    ).load()
    business_profile = BusinessCapabilityProjection.from_capability(capability)
    matching_profile = MatchingCatalogRepository(
        data_path / "tender_registry.sqlite3"
    ).load_profile()
    return CollectorService(
        engine,
        repository,
        ranker=CorterisParticipationRanker(
            CorterisCompanyProfile.from_business_profile(business_profile),
            classifier=CorterisTenderClassifier(matching_profile),
        ),
        stop_factor_engine=StopFactorEngine(business_profile),
    )


__all__ = [
    "create_default_async_providers",
    "create_default_collector_service",
]
