"""End-to-end collection orchestration: providers -> merge -> persistence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.tenders.collector.async_engine import AsyncProviderSearchEngine
from app.tenders.collector.cancellation import CollectorCancellationToken
from app.tenders.collector.deduplicator import TenderDeduplicator
from app.tenders.collector.models import (
    CollectionPersistenceSummary,
    CollectionRunStatus,
    CollectorRunResult,
    DeduplicationResult,
)
from app.tenders.collector.normalizer import TenderNormalizer
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.provider_base import TenderSearchQuery


class CollectorService:
    """Fault-isolated collector pipeline backed by persistent run history."""

    def __init__(
        self,
        engine: AsyncProviderSearchEngine,
        repository: CollectorStateRepository,
        *,
        normalizer: TenderNormalizer | None = None,
        deduplicator: TenderDeduplicator | None = None,
    ) -> None:
        self.engine = engine
        self.repository = repository
        self.normalizer = normalizer or TenderNormalizer()
        self.deduplicator = deduplicator or TenderDeduplicator(
            self.normalizer
        )

    async def collect(
        self,
        query: TenderSearchQuery,
        *,
        provider_ids: Sequence[str] | None = None,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> CollectorRunResult:
        requested = tuple(provider_ids or ())
        run_id = self.repository.start_run(
            query,
            provider_ids=requested,
        )
        try:
            batch = await self.engine.search(
                query,
                provider_ids=provider_ids,
                cancellation_token=cancellation_token,
            )
            normalized = self.normalizer.normalize_many(batch.raw_items)
            deduplicated = self.deduplicator.deduplicate(normalized)
            persistence = self.repository.save_batch(
                run_id,
                deduplicated,
                observed_at=batch.completed_at,
            )
            status = _status_for_batch(batch)
            self.repository.complete_run(
                run_id,
                status=status,
                provider_outcomes=batch.outcomes,
                completed_at=batch.completed_at,
                elapsed_ms=batch.elapsed_ms,
            )
            warnings = tuple(
                warning
                for outcome in batch.outcomes
                for warning in outcome.warnings
            )
            return CollectorRunResult(
                run_id=run_id,
                status=status,
                batch_result=batch,
                deduplication=deduplicated,
                persistence=persistence,
                warnings=warnings,
                metadata={
                    "partial_failures": batch.has_partial_failures,
                    "cancelled": batch.cancelled,
                },
            )
        except Exception as exc:
            self.repository.complete_run(
                run_id,
                status=CollectionRunStatus.FAILED,
                error=exc,
            )
            raise


def _status_for_batch(batch: object) -> CollectionRunStatus:
    if bool(getattr(batch, "cancelled", False)):
        return CollectionRunStatus.CANCELLED
    if bool(getattr(batch, "has_partial_failures", False)):
        return CollectionRunStatus.PARTIAL
    return CollectionRunStatus.COMPLETED


__all__ = ["CollectorService"]
