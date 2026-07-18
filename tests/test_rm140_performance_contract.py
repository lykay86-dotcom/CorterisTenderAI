"""Deterministic RM-140 volume, concurrency, progress and cleanup bounds."""

from __future__ import annotations

import asyncio

import pytest

from app.tenders.collector.async_engine import AsyncProviderSearchEngine
from app.tenders.collector.cancellation import CollectorCancellationToken
from app.tenders.collector.deduplicator import TenderDeduplicator
from app.tenders.collector.normalizer import TenderNormalizer
from app.tenders.collector.progress import (
    CollectorProgressDispatcher,
    CollectorProgressEvent,
    CollectorProgressPhase,
    ParallelSearchRunState,
)
from app.tenders.models import TenderSource
from app.tenders.provider_base import TenderSearchQuery
from tests.collector_c3_helpers import make_tender
from tests.test_collector_async_engine import FakeProvider


def _raw_items(raw_count: int):
    for index in range(raw_count):
        identity = index // 2
        source = TenderSource.EIS if index % 2 == 0 else TenderSource.CUSTOM
        yield make_tender(
            source=source,
            external_id=f"rm140-{index:05d}",
            procurement_number=f"RM140-{identity:05d}",
            title=f"RM-140 deterministic fixture {identity:05d}",
            customer_inn=f"77{identity:08d}",
            raw_metadata={"fixture": "rm140-baseline-v1"},
        )


@pytest.mark.parametrize("raw_count", (0, 100, 1_000, 10_000))
def test_normalize_and_deduplicate_counts_and_order_scale_linearly(raw_count: int) -> None:
    normalizer = TenderNormalizer()
    normalized = normalizer.normalize_many(_raw_items(raw_count))
    result = TenderDeduplicator(normalizer).deduplicate(normalized)
    expected_merged = raw_count // 2

    assert len(normalized) == raw_count
    assert result.raw_count == raw_count
    assert result.merged_count == expected_merged
    assert result.duplicate_count == raw_count - expected_merged
    assert tuple(item.canonical_key for item in result.items) == tuple(
        sorted(item.canonical_key for item in result.items)
    )
    assert len({item.canonical_key for item in result.items}) == expected_merged


def test_ten_provider_cancel_is_bounded_and_leaves_no_owned_tasks() -> None:
    async def scenario() -> None:
        tracker = {"active": 0, "peak": 0}

        class SlowProvider(FakeProvider):
            async def search(self, query, *, cancellation_token=None):
                del query
                tracker["active"] += 1
                tracker["peak"] = max(tracker["peak"], tracker["active"])
                try:
                    while True:
                        if cancellation_token is not None:
                            cancellation_token.throw_if_cancelled()
                        await asyncio.sleep(0.01)
                finally:
                    tracker["active"] -= 1

        providers = tuple(SlowProvider(f"slow-{index}", "slow") for index in range(10))
        token = CollectorCancellationToken()
        engine = AsyncProviderSearchEngine(
            providers,
            max_concurrent_providers=4,
            provider_timeout_seconds=5,
            overall_timeout_seconds=5,
        )
        search = asyncio.create_task(engine.search(TenderSearchQuery(), cancellation_token=token))
        await asyncio.sleep(0.04)
        token.cancel("rm140 deterministic cancellation")
        result = await asyncio.wait_for(search, timeout=1.0)
        await asyncio.sleep(0)

        current = asyncio.current_task()
        owned = tuple(
            task for task in asyncio.all_tasks() if task is not current and not task.done()
        )
        assert tracker == {"active": 0, "peak": 4}
        assert result.cancelled
        assert result.snapshot is not None
        assert result.snapshot.state is ParallelSearchRunState.CANCELLED
        assert owned == ()

    asyncio.run(scenario())


def test_progress_queue_and_shutdown_remain_bounded_with_slow_subscriber() -> None:
    async def scenario() -> None:
        release = asyncio.Event()

        async def slow_callback(event: CollectorProgressEvent) -> None:
            del event
            await release.wait()

        dispatcher = CollectorProgressDispatcher(
            slow_callback,
            max_queue_size=64,
            shutdown_timeout_seconds=0.05,
        )
        for revision in range(256):
            await dispatcher.publish(
                CollectorProgressEvent(
                    phase=CollectorProgressPhase.PROVIDER_RUNNING,
                    provider_id=f"provider-{revision}",
                )
            )

        assert dispatcher._queue is not None
        assert dispatcher._queue.qsize() <= 64
        await asyncio.wait_for(dispatcher.close(), timeout=1.0)
        assert dispatcher._worker is not None
        assert dispatcher._worker.done()

    asyncio.run(scenario())
