from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.tenders.collector.async_engine import (
    AsyncProviderSearchEngine,
    AsyncProviderSearchStatus,
)
from app.tenders.collector.async_provider import AsyncTenderProvider
from app.tenders.collector.cancellation import CollectorCancellationToken
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


class FakeProvider(AsyncTenderProvider):
    connection_mode = "fixture"
    parser_version = "test-1"

    def __init__(self, provider_id: str, behavior: str) -> None:
        self.behavior = behavior
        self.descriptor = ProviderDescriptor(
            id=provider_id,
            display_name=provider_id,
            source=TenderSource.CUSTOM,
            homepage_url="https://example.org/",
            capabilities=ProviderCapabilities(
                search=True,
                tender_details=True,
                documents=True,
            ),
            implementation_status="fixture",
        )

    async def search(self, query, *, cancellation_token=None):
        del query
        if self.behavior == "fail":
            raise RuntimeError("provider failed")
        if self.behavior == "slow":
            while True:
                if cancellation_token is not None:
                    cancellation_token.throw_if_cancelled()
                await asyncio.sleep(0.01)
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


def test_engine_keeps_success_when_another_provider_fails() -> None:
    async def scenario() -> None:
        engine = AsyncProviderSearchEngine(
            (
                FakeProvider("good", "success"),
                FakeProvider("bad", "fail"),
            ),
            provider_timeout_seconds=1,
        )
        result = await engine.search(TenderSearchQuery())
        statuses = {outcome.provider_id: outcome.status for outcome in result.outcomes}
        assert statuses["good"] == AsyncProviderSearchStatus.SUCCESS
        assert statuses["bad"] == AsyncProviderSearchStatus.FAILED
        assert len(result.raw_items) == 1
        assert result.has_partial_failures

    asyncio.run(scenario())


def test_engine_cancels_active_collection() -> None:
    async def scenario() -> None:
        token = CollectorCancellationToken()
        engine = AsyncProviderSearchEngine(
            (FakeProvider("slow", "slow"),),
            provider_timeout_seconds=5,
        )
        task = asyncio.create_task(
            engine.search(
                TenderSearchQuery(),
                cancellation_token=token,
            )
        )
        await asyncio.sleep(0.03)
        token.cancel("Остановлено из интерфейса")
        result = await asyncio.wait_for(task, timeout=0.5)
        assert result.cancelled
        assert result.outcomes[0].status == (AsyncProviderSearchStatus.CANCELLED)

    asyncio.run(scenario())
