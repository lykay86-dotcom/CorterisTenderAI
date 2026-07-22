"""One-shot collector session with deterministic network cleanup."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol

from app.tenders.collector.async_provider_factory import (
    create_default_collector_service,
)
from app.tenders.collector.async_engine import CollectorRunBudget
from app.tenders.collector.cancellation import CollectorCancellationToken
from app.tenders.collector.health_monitor import ProviderHealthMonitor
from app.tenders.collector.models import CollectorRunResult
from app.tenders.collector.network_runtime import (
    CollectorNetworkRuntime,
    create_collector_network_runtime,
)
from app.tenders.collector.progress import CollectorProgressCallback
from app.tenders.collector.provider_control import CollectorProviderManager
from app.tenders.collector.source_monitoring import hydrate_health_monitor
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.collector.provider_settings import (
    ProviderEnablementRepository,
    ProviderSettingsLoadStatus,
    ProviderSettingsMutationError,
    ProviderSettingsSnapshot,
)
from app.tenders.provider_base import TenderSearchQuery


class _CollectorServiceLike(Protocol):
    async def collect(
        self,
        query: TenderSearchQuery,
        *,
        provider_ids: Sequence[str] | None = None,
        cancellation_token: CollectorCancellationToken | None = None,
        progress_callback: CollectorProgressCallback | None = None,
        run_budget: CollectorRunBudget | None = None,
    ) -> CollectorRunResult: ...


RuntimeFactory = Callable[[], CollectorNetworkRuntime]
ServiceFactory = Callable[..., _CollectorServiceLike]
SettingsSnapshotFactory = Callable[[], ProviderSettingsSnapshot]


class CollectorRunSession:
    """Create a fresh HTTP runtime per run and always close it."""

    def __init__(
        self,
        data_directory: str | Path,
        *,
        runtime_factory: RuntimeFactory = create_collector_network_runtime,
        service_factory: ServiceFactory = create_default_collector_service,
        include_commercial_catalog: bool = True,
        provider_settings_snapshot_factory: SettingsSnapshotFactory | None = None,
    ) -> None:
        self.data_directory = Path(data_directory).expanduser()
        self.runtime_factory = runtime_factory
        self.service_factory = service_factory
        self.include_commercial_catalog = bool(include_commercial_catalog)
        self.provider_settings_repository = ProviderEnablementRepository(
            self.data_directory / "collector_provider_settings.json",
            legacy_settings_path=(self.data_directory / "commercial_provider_settings.json"),
        )
        self.provider_settings_snapshot_factory = (
            provider_settings_snapshot_factory
            if provider_settings_snapshot_factory is not None
            else lambda: CollectorProviderManager(self.data_directory).settings_snapshot()
        )

    async def run(
        self,
        query: TenderSearchQuery,
        *,
        provider_ids: Sequence[str] | None = None,
        cancellation_token: CollectorCancellationToken | None = None,
        progress_callback: CollectorProgressCallback | None = None,
        run_budget: CollectorRunBudget | None = None,
    ) -> CollectorRunResult:
        settings_snapshot = self.provider_settings_snapshot_factory()
        if settings_snapshot.status in {
            ProviderSettingsLoadStatus.CORRUPT,
            ProviderSettingsLoadStatus.UNSUPPORTED_FUTURE,
        }:
            raise ProviderSettingsMutationError(
                f"Provider settings are unavailable: {settings_snapshot.status.value}"
            )
        if provider_ids is not None:
            provider_ids = settings_snapshot.assert_runnable_provider_ids(tuple(provider_ids))
        runtime = self.runtime_factory()
        try:
            monitor = getattr(runtime, "health_monitor", None)
            if isinstance(monitor, ProviderHealthMonitor):
                history = CollectorStateRepository(
                    self.data_directory / "tender_registry.sqlite3"
                ).list_provider_outcomes(limit=1000)
                hydrate_health_monitor(monitor, history)
            service = self.service_factory(
                self.data_directory,
                runtime,
                include_commercial_catalog=(self.include_commercial_catalog),
                provider_settings_snapshot=settings_snapshot,
            )
            return await service.collect(
                query,
                provider_ids=provider_ids,
                cancellation_token=cancellation_token,
                progress_callback=progress_callback,
                run_budget=run_budget,
            )
        finally:
            await runtime.aclose()


__all__ = ["CollectorRunSession"]
