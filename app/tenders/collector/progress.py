"""Progress events shared by the collector core and Qt interface."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import inspect
import logging

from app.tenders.collector.models import NormalizedTender
from app.tenders.collector.search_errors import (
    SearchErrorCategory,
    safe_provider_display_name,
)

_LOGGER = logging.getLogger(__name__)


class CollectorProgressPhase(StrEnum):
    """Stable phases emitted by one collector run."""

    PREPARING = "preparing"
    PROVIDER_QUEUED = "provider_queued"
    PROVIDER_RUNNING = "provider_running"
    PROVIDER_COMPLETED = "provider_completed"
    SEARCH_TERMINAL = "search_terminal"
    NORMALIZING = "normalizing"
    DEDUPLICATING = "deduplicating"
    VERIFYING = "verifying"
    CHECKING_FRESHNESS = "checking_freshness"
    RANKING = "ranking"
    SAVING = "saving"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ParallelSearchRunState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"

    @property
    def terminal(self) -> bool:
        return self in {
            self.COMPLETED,
            self.PARTIAL,
            self.FAILED,
            self.TIMED_OUT,
            self.CANCELLED,
        }


class ProviderExecutionState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    SUCCESS = "success"
    EMPTY = "empty"
    NOT_CONFIGURED = "not_configured"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    CIRCUIT_OPEN = "circuit_open"

    @property
    def terminal(self) -> bool:
        return self not in {self.QUEUED, self.RUNNING, self.RETRY_WAIT}


@dataclass(frozen=True, slots=True)
class ProviderExecutionSnapshot:
    provider_id: str
    display_name: str
    state: ProviderExecutionState
    item_count: int = 0
    elapsed_ms: int = 0
    attempt_count: int = 1
    error_category: SearchErrorCategory = SearchErrorCategory.NONE
    error_code: str = ""
    error_message: str = ""
    retryable: bool = False
    http_status: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "display_name",
            safe_provider_display_name(self.display_name, provider_id=self.provider_id),
        )
        if not self.provider_id.strip() or not self.display_name.strip():
            raise ValueError("Provider snapshot identity is required")
        if self.item_count < 0 or self.elapsed_ms < 0 or self.attempt_count < 1:
            raise ValueError("Provider snapshot counters are invalid")
        if self.http_status is not None and not 100 <= self.http_status <= 599:
            raise ValueError("Provider snapshot HTTP status is invalid")

    @property
    def terminal(self) -> bool:
        return self.state.terminal


@dataclass(frozen=True, slots=True)
class ParallelSearchSnapshot:
    run_id: str
    revision: int
    state: ParallelSearchRunState
    providers: tuple[ProviderExecutionSnapshot, ...]
    started_at: str
    updated_at: str
    completed: int
    percent: int
    partial_items: tuple[NormalizedTender, ...] = ()

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValueError("Parallel search run_id is required")
        if self.revision < 0:
            raise ValueError("Parallel search revision must be non-negative")
        if not 0 <= self.percent <= 100:
            raise ValueError("Parallel search percent must be between 0 and 100")
        if len({item.provider_id for item in self.providers}) != len(self.providers):
            raise ValueError("Parallel search providers must be unique")
        exact_completed = sum(item.terminal for item in self.providers)
        if self.completed != exact_completed:
            raise ValueError("Parallel search completed count is not exact")
        if self.state.terminal != (self.percent == 100):
            raise ValueError("Only a terminal search snapshot may report 100 percent")
        for value in (self.started_at, self.updated_at):
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                raise ValueError("Parallel search timestamps must be timezone-aware")

    @property
    def total(self) -> int:
        return len(self.providers)

    @property
    def queued(self) -> int:
        return sum(item.state is ProviderExecutionState.QUEUED for item in self.providers)

    @property
    def running(self) -> int:
        return sum(
            item.state in {ProviderExecutionState.RUNNING, ProviderExecutionState.RETRY_WAIT}
            for item in self.providers
        )


@dataclass(frozen=True, slots=True)
class CollectorProgressEvent:
    """One immutable progress update.

    Provider fields are populated for provider-specific phases. Aggregate
    counters are populated as soon as they become known by the pipeline.
    """

    phase: CollectorProgressPhase
    message: str = ""
    provider_id: str = ""
    display_name: str = ""
    provider_status: str = ""
    item_count: int = 0
    elapsed_ms: int = 0
    total_providers: int = 0
    raw_count: int = 0
    merged_count: int = 0
    duplicate_count: int = 0
    new_count: int = 0
    changed_count: int = 0
    unchanged_count: int = 0
    stale_count: int = 0
    due_soon_count: int = 0
    expired_count: int = 0
    progress_percent: int | None = None
    snapshot: ParallelSearchSnapshot | None = None

    def __post_init__(self) -> None:
        if self.display_name:
            object.__setattr__(
                self,
                "display_name",
                safe_provider_display_name(self.display_name, provider_id=self.provider_id),
            )
        integer_fields = (
            self.item_count,
            self.elapsed_ms,
            self.total_providers,
            self.raw_count,
            self.merged_count,
            self.duplicate_count,
            self.new_count,
            self.changed_count,
            self.unchanged_count,
            self.stale_count,
            self.due_soon_count,
            self.expired_count,
        )
        if any(value < 0 for value in integer_fields):
            raise ValueError("Progress counters must be non-negative")
        if self.progress_percent is not None and not 0 <= self.progress_percent <= 100:
            raise ValueError("Progress percent must be between 0 and 100")


CollectorProgressCallback = Callable[
    [CollectorProgressEvent],
    Awaitable[None] | None,
]


class CollectorProgressDispatcher:
    """Deliver ordered progress without awaiting subscribers in provider work."""

    def __init__(
        self,
        callback: CollectorProgressCallback | None,
        *,
        max_queue_size: int = 64,
        shutdown_timeout_seconds: float = 0.2,
    ) -> None:
        if max_queue_size < 1:
            raise ValueError("max_queue_size must be positive")
        if shutdown_timeout_seconds <= 0:
            raise ValueError("shutdown_timeout_seconds must be positive")
        self._callback = callback
        self._queue: asyncio.Queue[CollectorProgressEvent | None] | None = None
        self._worker: asyncio.Task[None] | None = None
        self._max_queue_size = max_queue_size
        self._shutdown_timeout_seconds = shutdown_timeout_seconds
        self._closed = False

    async def publish(self, event: CollectorProgressEvent) -> None:
        if self._callback is None or self._closed:
            return
        if self._queue is None:
            self._queue = asyncio.Queue(maxsize=self._max_queue_size)
            self._worker = asyncio.create_task(self._deliver())
        if self._queue.full():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except asyncio.QueueEmpty:
                pass
        self._queue.put_nowait(event)
        await asyncio.sleep(0)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._queue is None or self._worker is None:
            return
        if self._queue.full():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except asyncio.QueueEmpty:
                pass
        self._queue.put_nowait(None)
        try:
            await asyncio.wait_for(
                self._worker,
                timeout=self._shutdown_timeout_seconds,
            )
        except TimeoutError:
            self._worker.cancel()
            await asyncio.gather(self._worker, return_exceptions=True)

    async def _deliver(self) -> None:
        if self._queue is None:
            return
        while True:
            event = await self._queue.get()
            try:
                if event is None:
                    return
                await emit_collector_progress(self._callback, event)
            finally:
                self._queue.task_done()


async def emit_collector_progress(
    callback: CollectorProgressCallback | None,
    event: CollectorProgressEvent,
) -> None:
    """Invoke a callback without letting UI failures break collection."""

    if callback is None:
        return
    try:
        result = callback(event)
        if inspect.isawaitable(result):
            await result
    except Exception:
        _LOGGER.warning(
            "Collector progress callback failed safely during %s",
            event.phase.value,
        )


__all__ = [
    "CollectorProgressCallback",
    "CollectorProgressDispatcher",
    "CollectorProgressEvent",
    "CollectorProgressPhase",
    "ParallelSearchRunState",
    "ParallelSearchSnapshot",
    "ProviderExecutionSnapshot",
    "ProviderExecutionState",
    "SearchErrorCategory",
    "emit_collector_progress",
]
