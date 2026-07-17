"""Expected RM-138 lifecycle, safety, cancellation and partial-result contract."""

from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from time import perf_counter

import pytest

from app.tenders.collector.async_engine import AsyncProviderSearchEngine
from app.tenders.collector.async_provider import AsyncTenderProvider
from app.tenders.collector.cancellation import CollectorCancellationToken
from app.tenders.collector.progress import (
    CollectorProgressEvent,
    ParallelSearchRunState,
    ParallelSearchSnapshot,
    ProviderExecutionSnapshot,
    ProviderExecutionState,
    SearchErrorCategory,
)
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


class _ContractProvider(AsyncTenderProvider):
    connection_mode = "fixture"
    parser_version = "rm-138-contract"

    def __init__(
        self,
        provider_id: str,
        *,
        priority: int = 10,
        delay: float = 0,
        fail: BaseException | None = None,
        ignore_task_cancel: bool = False,
        procurement_number: str = "",
    ) -> None:
        self.delay = delay
        self.fail = fail
        self.ignore_task_cancel = ignore_task_cancel
        self.procurement_number = procurement_number or f"N-{provider_id}"
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
        del query
        try:
            await asyncio.sleep(self.delay)
        except asyncio.CancelledError:
            if not self.ignore_task_cancel:
                raise
        if self.fail is not None:
            raise self.fail
        tender = UnifiedTender(
            source=TenderSource.CUSTOM,
            external_id=self.descriptor.id,
            procurement_number=self.procurement_number,
            title="Монтаж системы видеонаблюдения",
            customer=TenderCustomer(name="Заказчик"),
            source_url=f"https://example.org/{self.descriptor.id}",
            status=TenderStatus.PUBLISHED,
            raw_metadata={"provider_id": self.descriptor.id},
        )
        return TenderSearchResult(provider_id=self.descriptor.id, items=(tender,))

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


def _snapshots(events: list[CollectorProgressEvent]) -> list[ParallelSearchSnapshot]:
    return [event.snapshot for event in events if event.snapshot is not None]


def test_snapshot_is_immutable_and_validates_exact_counters() -> None:
    provider = ProviderExecutionSnapshot(
        provider_id="eis",
        display_name="ЕИС",
        state=ProviderExecutionState.RUNNING,
    )
    snapshot = ParallelSearchSnapshot(
        run_id="run-1",
        revision=2,
        state=ParallelSearchRunState.RUNNING,
        providers=(provider,),
        started_at="2026-07-18T10:00:00+00:00",
        updated_at="2026-07-18T10:00:01+00:00",
        completed=0,
        percent=25,
    )

    assert snapshot.total == 1
    assert snapshot.running == 1
    with pytest.raises(FrozenInstanceError):
        snapshot.revision = 3  # type: ignore[misc]
    with pytest.raises(ValueError, match="completed"):
        ParallelSearchSnapshot(
            run_id="run-1",
            revision=3,
            state=ParallelSearchRunState.RUNNING,
            providers=(provider,),
            started_at="2026-07-18T10:00:00+00:00",
            updated_at="2026-07-18T10:00:01+00:00",
            completed=1,
            percent=50,
        )


def test_engine_publishes_monotonic_authoritative_snapshots() -> None:
    async def scenario() -> None:
        events: list[CollectorProgressEvent] = []
        engine = AsyncProviderSearchEngine(
            (
                _ContractProvider("second", priority=20, delay=0.01),
                _ContractProvider("first", priority=10, delay=0.02),
            ),
            max_concurrent_providers=1,
        )

        await engine.search(TenderSearchQuery(), progress_callback=events.append)

        snapshots = _snapshots(events)
        assert snapshots
        assert [item.revision for item in snapshots] == list(
            range(snapshots[0].revision, snapshots[-1].revision + 1)
        )
        assert all(tuple(p.provider_id for p in item.providers) == ("first", "second") for item in snapshots)
        assert all(item.completed == sum(p.terminal for p in item.providers) for item in snapshots)
        assert max(item.running for item in snapshots) == 1
        assert [item.percent for item in snapshots] == sorted(item.percent for item in snapshots)
        assert snapshots[-1].state == ParallelSearchRunState.COMPLETED
        assert snapshots[-1].percent == 100

    asyncio.run(scenario())


def test_overall_deadline_is_terminal_and_retains_no_late_result() -> None:
    async def scenario() -> None:
        events: list[CollectorProgressEvent] = []
        engine = AsyncProviderSearchEngine(
            (_ContractProvider("slow", delay=1),),
            provider_timeout_seconds=2,
            overall_timeout_seconds=0.03,
        )
        started = perf_counter()

        result = await engine.search(TenderSearchQuery(), progress_callback=events.append)

        assert perf_counter() - started < 0.5
        assert result.timed_out
        assert result.raw_items == ()
        assert _snapshots(events)[-1].state == ParallelSearchRunState.TIMED_OUT

    asyncio.run(scenario())


def test_public_failure_is_typed_and_does_not_leak_exception_text() -> None:
    async def scenario() -> None:
        secret = "token=super-secret"
        engine = AsyncProviderSearchEngine(
            (_ContractProvider("bad", fail=RuntimeError(f"{secret} https://private/path?q=x")),)
        )

        result = await engine.search(TenderSearchQuery())
        outcome = result.outcomes[0]

        assert outcome.error_category == SearchErrorCategory.INTERNAL
        assert outcome.error_code == "provider_internal_error"
        assert secret not in outcome.error_message
        assert "private" not in outcome.error_message

    asyncio.run(scenario())


def test_cancellation_discards_result_from_provider_that_suppresses_task_cancel() -> None:
    async def scenario() -> None:
        token = CollectorCancellationToken()
        engine = AsyncProviderSearchEngine(
            (_ContractProvider("late", delay=5, ignore_task_cancel=True),),
            provider_timeout_seconds=10,
        )
        task = asyncio.create_task(
            engine.search(TenderSearchQuery(), cancellation_token=token)
        )
        await asyncio.sleep(0.03)
        assert token.cancel("cancelled by contract test")
        assert not token.cancel("second cancellation")

        result = await asyncio.wait_for(task, timeout=0.5)

        assert result.cancelled
        assert result.raw_items == ()

    asyncio.run(scenario())


def test_partial_canonical_result_is_schedule_independent() -> None:
    async def run(delays: tuple[float, float]):
        events: list[CollectorProgressEvent] = []
        engine = AsyncProviderSearchEngine(
            (
                _ContractProvider(
                    "alpha",
                    priority=10,
                    delay=delays[0],
                    procurement_number="COMMON-1",
                ),
                _ContractProvider(
                    "beta",
                    priority=20,
                    delay=delays[1],
                    procurement_number="COMMON-1",
                ),
            )
        )
        batch = await engine.search(TenderSearchQuery(), progress_callback=events.append)
        return batch, _snapshots(events)

    first, first_snapshots = asyncio.run(run((0.03, 0.01)))
    second, second_snapshots = asyncio.run(run((0.01, 0.03)))

    first_keys = tuple(item.canonical_key for item in first.deduplication.items)
    second_keys = tuple(item.canonical_key for item in second.deduplication.items)
    assert first_keys == second_keys
    assert len(first_keys) == 1
    assert tuple(item.canonical_key for item in first_snapshots[-1].partial_items) == first_keys
    assert tuple(item.canonical_key for item in second_snapshots[-1].partial_items) == second_keys


def test_slow_progress_subscriber_does_not_serialize_provider_execution() -> None:
    async def scenario() -> None:
        async def slow_callback(_event: CollectorProgressEvent) -> None:
            await asyncio.sleep(0.2)

        engine = AsyncProviderSearchEngine(
            (_ContractProvider("fast", delay=0.01),),
            progress_shutdown_timeout_seconds=0.05,
        )
        started = perf_counter()

        await engine.search(TenderSearchQuery(), progress_callback=slow_callback)

        assert perf_counter() - started < 0.18

    asyncio.run(scenario())
