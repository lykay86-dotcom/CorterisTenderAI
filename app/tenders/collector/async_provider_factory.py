"""Composition helpers for native asynchronous collector providers."""

from __future__ import annotations

from pathlib import Path

from app.tenders.collector.async_engine import AsyncProviderSearchEngine
from app.tenders.collector.collector_service import CollectorService
from app.tenders.collector.network_runtime import CollectorNetworkRuntime
from app.tenders.collector.store import CollectorStateRepository
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
):
    """Return only providers that are genuinely implemented.

    Commercial placeholders are intentionally excluded until credentials and
    a verified integration contract are available.
    """

    return (
        AsyncEisTenderProvider(
            network_runtime.http_client,
            network_settings=network_runtime.settings.get("eis"),
            checkpoint_repository=repository,
        ),
        AsyncMosSupplierTenderProvider(
            network_runtime.http_client,
            config=(
                mos_supplier_config
                or MosSupplierApiConfig.from_environment()
            ),
            network_settings=network_runtime.settings.get(
                "mos_supplier"
            ),
            checkpoint_repository=repository,
        ),
    )


def create_default_collector_service(
    data_directory: str | Path,
    network_runtime: CollectorNetworkRuntime,
    *,
    provider_timeout_seconds: float = 90.0,
    mos_supplier_config: MosSupplierApiConfig | None = None,
) -> CollectorService:
    """Build the first production collector pipeline without network I/O."""

    data_path = Path(data_directory).expanduser()
    data_path.mkdir(parents=True, exist_ok=True)
    repository = CollectorStateRepository(
        data_path / "tender_registry.sqlite3"
    )
    repository.initialize()
    providers = create_default_async_providers(
        network_runtime,
        repository=repository,
        mos_supplier_config=mos_supplier_config,
    )
    engine = AsyncProviderSearchEngine(
        providers,
        health_monitor=network_runtime.health_monitor,
        provider_timeout_seconds=provider_timeout_seconds,
    )
    return CollectorService(engine, repository)


__all__ = [
    "create_default_async_providers",
    "create_default_collector_service",
]
