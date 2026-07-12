"""Progress events shared by the collector core and Qt interface."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
import inspect
import logging

_LOGGER = logging.getLogger(__name__)


class CollectorProgressPhase(StrEnum):
    """Stable phases emitted by one collector run."""

    PREPARING = "preparing"
    PROVIDER_QUEUED = "provider_queued"
    PROVIDER_RUNNING = "provider_running"
    PROVIDER_COMPLETED = "provider_completed"
    NORMALIZING = "normalizing"
    DEDUPLICATING = "deduplicating"
    VERIFYING = "verifying"
    CHECKING_FRESHNESS = "checking_freshness"
    RANKING = "ranking"
    SAVING = "saving"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


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

    def __post_init__(self) -> None:
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


CollectorProgressCallback = Callable[
    [CollectorProgressEvent],
    Awaitable[None] | None,
]


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
        _LOGGER.exception(
            "Collector progress callback failed during %s",
            event.phase.value,
        )


__all__ = [
    "CollectorProgressCallback",
    "CollectorProgressEvent",
    "CollectorProgressPhase",
    "emit_collector_progress",
]
