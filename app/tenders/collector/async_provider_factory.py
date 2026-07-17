"""Composition helpers for native asynchronous collector providers."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from app.tenders.business_profile import BusinessCapabilityProjection
from app.tenders.collector.async_engine import AsyncProviderSearchEngine
from app.tenders.collector.async_provider import AsyncTenderProvider
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
    ProviderSettingsLoadStatus,
    ProviderSettingsMutationError,
    ProviderSettingsSnapshot,
    create_provider_settings_snapshot,
)
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.collector.manual_adapter import (
    AdapterCompileResult,
    ManualAdapterDependencies,
    ManualAdapterSpec,
    compile_manual_adapter,
)
from app.tenders.collector.manual_provider_registration import ManualProviderRegistration
from app.tenders.providers.commercial_adapter import (
    create_commercial_access_providers,
)
from app.tenders.providers.commercial_catalog import (
    CommercialProviderCatalog,
    CommercialProviderUserSettings,
    create_commercial_provider_catalog,
    default_commercial_provider_definitions,
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
    provider_settings_snapshot: ProviderSettingsSnapshot | None = None,
    environment: Mapping[str, str] | None = None,
    include_disabled: bool = False,
) -> tuple[AsyncTenderProvider, ...]:
    """Return implemented providers and optional visible access adapters.

    Commercial adapters are excluded by default. When explicitly requested,
    only providers enabled by the user are added, and they remain honest
    ``not_configured`` adapters until a real API contract is verified.
    """

    if provider_settings_snapshot is not None and provider_settings_snapshot.status in {
        ProviderSettingsLoadStatus.CORRUPT,
        ProviderSettingsLoadStatus.UNSUPPORTED_FUTURE,
    }:
        raise ProviderSettingsMutationError(
            f"Provider settings are unavailable: {provider_settings_snapshot.status.value}"
        )

    providers: list[AsyncTenderProvider] = [
        AsyncEisTenderProvider(
            network_runtime.http_client,
            network_settings=network_runtime.settings.get("eis"),
            checkpoint_repository=repository,
        ),
        AsyncMosSupplierTenderProvider(
            network_runtime.http_client,
            config=(mos_supplier_config or MosSupplierApiConfig.from_environment(environment)),
            network_settings=network_runtime.settings.get("mos_supplier"),
            checkpoint_repository=repository,
        ),
    ]
    if include_commercial_catalog:
        catalog = commercial_catalog
        if catalog is None:
            user_settings = None
            if provider_settings_snapshot is not None:
                user_settings = {
                    definition.provider_id: CommercialProviderUserSettings(
                        enabled=bool(
                            provider_settings_snapshot.get(definition.provider_id).enabled
                        ),
                        access_confirmed=(
                            provider_settings_snapshot.get(
                                definition.provider_id
                            ).configuration.access_confirmed
                        ),
                        api_base_url=(
                            provider_settings_snapshot.get(
                                definition.provider_id
                            ).configuration.api_base_url
                        ),
                    )
                    for definition in default_commercial_provider_definitions()
                }
            catalog = create_commercial_provider_catalog(
                environment=environment,
                user_settings=user_settings,
            )
        providers.extend(
            create_commercial_access_providers(
                catalog.resolve_all(),
                enabled_only=(provider_settings_repository is None and not include_disabled),
            )
        )

    if provider_settings_snapshot is not None:
        providers = [
            provider
            for provider in providers
            if (include_disabled or provider_settings_snapshot.get(provider.descriptor.id).enabled)
        ]
    elif provider_settings_repository is not None:
        providers = [
            provider
            for provider in providers
            if (include_disabled or provider_settings_repository.is_enabled(provider.descriptor))
        ]
    return tuple(providers)


def build_manual_async_provider(
    registration: ManualProviderRegistration,
    spec: ManualAdapterSpec,
    *,
    dependencies: ManualAdapterDependencies | None = None,
) -> AdapterCompileResult:
    """Compile one scoped manual provider without I/O or runtime admission."""

    return compile_manual_adapter(registration, spec, dependencies=dependencies)


def create_default_collector_service(
    data_directory: str | Path,
    network_runtime: CollectorNetworkRuntime,
    *,
    provider_timeout_seconds: float = 90.0,
    mos_supplier_config: MosSupplierApiConfig | None = None,
    include_commercial_catalog: bool = False,
    commercial_catalog: CommercialProviderCatalog | None = None,
    provider_settings_repository: (ProviderEnablementRepository | None) = None,
    provider_settings_snapshot: ProviderSettingsSnapshot | None = None,
    environment: Mapping[str, str] | None = None,
) -> CollectorService:
    """Build the first production collector pipeline without network I/O."""

    data_path = Path(data_directory).expanduser()
    data_path.mkdir(parents=True, exist_ok=True)
    repository = CollectorStateRepository(data_path / "tender_registry.sqlite3")
    repository.initialize()
    source_settings = provider_settings_repository or ProviderEnablementRepository(
        data_path / "collector_provider_settings.json",
        legacy_settings_path=(data_path / "commercial_provider_settings.json"),
    )
    settings_snapshot = provider_settings_snapshot or create_provider_settings_snapshot(
        source_settings,
        environment=environment,
    )
    providers = create_default_async_providers(
        network_runtime,
        repository=repository,
        mos_supplier_config=mos_supplier_config,
        include_commercial_catalog=include_commercial_catalog,
        commercial_catalog=commercial_catalog,
        provider_settings_repository=source_settings,
        provider_settings_snapshot=settings_snapshot,
        environment=environment,
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
    "build_manual_async_provider",
    "create_default_async_providers",
    "create_default_collector_service",
]
