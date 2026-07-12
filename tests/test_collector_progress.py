"""Progress and cancellation tests for asynchronous provider execution."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.tenders.collector.async_engine import (
    AsyncProviderSearchEngine,
    AsyncProviderSearchStatus,
)
from app.tenders.collector.async_provider import AsyncTenderProvider
from app.tenders.collector.cancellation import CollectorCancellationToken
from app.tenders.collector.progress import CollectorProgressPhase
from app.tenders.models import (
    TenderCustomer,
    TenderSource,
    TenderStatus,
    UnifiedTender,
)
from app.tenders.provider_base import (
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderHealth,
    ProviderHealthStatus,
    TenderSearchQuery,
    TenderSearchResult,
)


class ProgressProvider(AsyncTenderProvider):
    connection_mode = "fixture"
    parser_version = "c8-test"

    def __init__(
        self,
        provider_id: str,
        *,
        delay: float = 0,
        fail: bool = False,
    ) -> None:
        self.delay = delay
        self.fail = fail
        self.descriptor = ProviderDescriptor(
            id=provider_id,
            display_name=provider_id.upper(),
            source=TenderSource.CUSTOM,
            homepage_url="https://example.org/",
            capabilities=ProviderCapabilities(search=True),
            implementation_status="fixture",
        )

    async def search(self, query, *, cancellation_token=None):
        del query
        remaining = self.delay
        while remaining > 0:
            if cancellation_token is not None:
                cancellation_token.throw_if_cancelled()
            interval = min(0.01, remaining)
            await asyncio.sleep(interval)
            remaining -= interval
        if self.fail:
            raise RuntimeError("fixture failure")
        tender = UnifiedTender(
            source=TenderSource.CUSTOM,
            external_id=self.descriptor.id,
            procurement_number=f"N-{self.descriptor.id}",
            title="Монтаж видеонаблюдения",
            customer=TenderCustomer(name="Заказчик"),
            source_url="https://example.org/tender",
            status=TenderStatus.PUBLISHED,
        )
        return TenderSearchResult(
            provider_id=self.descriptor.id,
            items=(tender,),
        )

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


def test_engine_emits_provider_progress_without_affecting_results() -> None:
    async def scenario() -> None:
        events = []
        engine = AsyncProviderSearchEngine(
            (
                ProgressProvider("good"),
                ProgressProvider("bad", fail=True),
            ),
            provider_timeout_seconds=1,
        )

        result = await engine.search(
            TenderSearchQuery(keywords=("СКУД",)),
            progress_callback=events.append,
        )

        queued = {
            event.provider_id
            for event in events
            if event.phase == CollectorProgressPhase.PROVIDER_QUEUED
        }
        running = {
            event.provider_id
            for event in events
            if event.phase == CollectorProgressPhase.PROVIDER_RUNNING
        }
        completed = {
            event.provider_id: event.provider_status
            for event in events
            if event.phase == CollectorProgressPhase.PROVIDER_COMPLETED
        }

        assert queued == {"good", "bad"}
        assert running == {"good", "bad"}
        assert completed == {
            "good": AsyncProviderSearchStatus.SUCCESS.value,
            "bad": AsyncProviderSearchStatus.FAILED.value,
        }
        assert len(result.raw_items) == 1

    asyncio.run(scenario())


def test_cancellation_keeps_provider_results_already_completed() -> None:
    async def scenario() -> None:
        token = CollectorCancellationToken()
        engine = AsyncProviderSearchEngine(
            (
                ProgressProvider("fast", delay=0.01),
                ProgressProvider("slow", delay=5),
            ),
            provider_timeout_seconds=10,
        )
        task = asyncio.create_task(
            engine.search(
                TenderSearchQuery(),
                cancellation_token=token,
            )
        )
        await asyncio.sleep(0.08)
        token.cancel("Остановлено тестом")
        result = await asyncio.wait_for(task, timeout=1)
        outcomes = {
            outcome.provider_id: outcome.status
            for outcome in result.outcomes
        }

        assert result.cancelled
        assert outcomes["fast"] == AsyncProviderSearchStatus.SUCCESS
        assert outcomes["slow"] == AsyncProviderSearchStatus.CANCELLED
        assert len(result.raw_items) == 1

    asyncio.run(scenario())
