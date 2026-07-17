"""RM-138 characterization of the accepted search boundaries."""

from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
import inspect

import pytest

from app.tenders.collector.async_engine import (
    AsyncProviderSearchEngine,
    AsyncProviderSearchStatus,
)
from app.tenders.collector.async_provider import AsyncTenderProvider
from app.tenders.collector.progress import (
    CollectorProgressEvent,
    CollectorProgressPhase,
)
from app.tenders.models import TenderSource
from app.tenders.provider_base import (
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderHealth,
    ProviderHealthStatus,
    TenderSearchQuery,
    TenderSearchResult,
)
from app.tenders.search_engine import TenderSearchEngine


class _TrackingProvider(AsyncTenderProvider):
    connection_mode = "fixture"
    parser_version = "rm-138-characterization"

    def __init__(
        self,
        provider_id: str,
        *,
        priority: int,
        tracker: dict[str, int],
        fail: bool = False,
    ) -> None:
        self.tracker = tracker
        self.fail = fail
        self.calls = 0
        self.descriptor = ProviderDescriptor(
            id=provider_id,
            display_name=provider_id.upper(),
            source=TenderSource.CUSTOM,
            homepage_url="https://example.org/",
            capabilities=ProviderCapabilities(search=True),
            priority=priority,
            implementation_status="fixture",
        )

    async def search(self, query, *, cancellation_token=None):
        del query, cancellation_token
        self.calls += 1
        self.tracker["active"] += 1
        self.tracker["peak"] = max(self.tracker["peak"], self.tracker["active"])
        try:
            await asyncio.sleep(0.02)
            if self.fail:
                raise RuntimeError("characterized provider failure")
            return TenderSearchResult(provider_id=self.descriptor.id, items=())
        finally:
            self.tracker["active"] -= 1

    async def get_tender(self, external_id, *, cancellation_token=None):
        raise NotImplementedError

    async def list_documents(self, external_id, *, cancellation_token=None):
        return ()

    async def check_health(self, *, cancellation_token=None):
        return ProviderHealth(
            provider_id=self.descriptor.id,
            status=ProviderHealthStatus.AVAILABLE,
            checked_at=datetime.now(timezone.utc).isoformat(),
        )


def test_sync_tender_search_engine_public_signature_remains_compatible() -> None:
    constructor = inspect.signature(TenderSearchEngine)
    search = inspect.signature(TenderSearchEngine.search)

    assert tuple(constructor.parameters) == (
        "registry",
        "max_workers",
        "timeout_seconds",
        "normalizer",
    )
    assert tuple(search.parameters) == (
        "self",
        "query",
        "provider_ids",
        "include_disabled",
        "parallel",
    )


def test_production_coordinator_orders_providers_and_bounds_parallelism() -> None:
    async def scenario() -> None:
        tracker = {"active": 0, "peak": 0}
        providers = (
            _TrackingProvider("third", priority=30, tracker=tracker),
            _TrackingProvider("first", priority=10, tracker=tracker),
            _TrackingProvider("second", priority=20, tracker=tracker),
        )
        engine = AsyncProviderSearchEngine(providers, max_concurrent_providers=2)

        result = await engine.search(TenderSearchQuery())

        assert tuple(outcome.provider_id for outcome in result.outcomes) == (
            "first",
            "second",
            "third",
        )
        assert tracker["peak"] == 2

    asyncio.run(scenario())


def test_coordinator_invokes_failed_provider_once_without_adding_retry() -> None:
    async def scenario() -> None:
        tracker = {"active": 0, "peak": 0}
        provider = _TrackingProvider(
            "once",
            priority=10,
            tracker=tracker,
            fail=True,
        )
        result = await AsyncProviderSearchEngine((provider,)).search(TenderSearchQuery())

        assert provider.calls == 1
        assert result.outcomes[0].status == AsyncProviderSearchStatus.FAILED

    asyncio.run(scenario())


def test_existing_progress_event_is_immutable() -> None:
    event = CollectorProgressEvent(
        phase=CollectorProgressPhase.PROVIDER_QUEUED,
        provider_id="eis",
        total_providers=1,
    )

    with pytest.raises(FrozenInstanceError):
        event.provider_id = "changed"  # type: ignore[misc]
