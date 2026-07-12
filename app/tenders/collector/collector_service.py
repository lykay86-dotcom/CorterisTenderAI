"""End-to-end collection orchestration: providers -> merge -> persistence."""

from __future__ import annotations

from typing import Sequence

from app.tenders.collector.async_engine import AsyncProviderSearchEngine
from app.tenders.collector.cancellation import CollectorCancellationToken
from app.tenders.collector.deduplicator import TenderDeduplicator
from app.tenders.collector.models import (
    CollectionRunStatus,
    CollectorRunResult,
)
from app.tenders.collector.normalizer import TenderNormalizer
from app.tenders.collector.progress import (
    CollectorProgressCallback,
    CollectorProgressEvent,
    CollectorProgressPhase,
    emit_collector_progress,
)
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
        progress_callback: CollectorProgressCallback | None = None,
    ) -> CollectorRunResult:
        requested = tuple(provider_ids or ())
        await emit_collector_progress(
            progress_callback,
            CollectorProgressEvent(
                phase=CollectorProgressPhase.PREPARING,
                total_providers=len(requested),
                message="Подготовка запуска коллектора…",
            ),
        )
        run_id = self.repository.start_run(
            query,
            provider_ids=requested,
        )
        try:
            if progress_callback is None:
                batch = await self.engine.search(
                    query,
                    provider_ids=provider_ids,
                    cancellation_token=cancellation_token,
                )
            else:
                batch = await self.engine.search(
                    query,
                    provider_ids=provider_ids,
                    cancellation_token=cancellation_token,
                    progress_callback=progress_callback,
                )

            await emit_collector_progress(
                progress_callback,
                CollectorProgressEvent(
                    phase=CollectorProgressPhase.NORMALIZING,
                    total_providers=len(batch.outcomes),
                    raw_count=len(batch.raw_items),
                    message=(
                        "Нормализация данных, полученных от источников…"
                    ),
                ),
            )
            normalized = self.normalizer.normalize_many(batch.raw_items)

            await emit_collector_progress(
                progress_callback,
                CollectorProgressEvent(
                    phase=CollectorProgressPhase.DEDUPLICATING,
                    total_providers=len(batch.outcomes),
                    raw_count=len(normalized),
                    message="Поиск и объединение дублей…",
                ),
            )
            deduplicated = self.deduplicator.deduplicate(normalized)

            await emit_collector_progress(
                progress_callback,
                CollectorProgressEvent(
                    phase=CollectorProgressPhase.SAVING,
                    total_providers=len(batch.outcomes),
                    raw_count=deduplicated.raw_count,
                    merged_count=deduplicated.merged_count,
                    duplicate_count=deduplicated.duplicate_count,
                    message="Сохранение результатов в локальный реестр…",
                ),
            )
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
            result = CollectorRunResult(
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
            final_phase = (
                CollectorProgressPhase.CANCELLED
                if status == CollectionRunStatus.CANCELLED
                else CollectorProgressPhase.COMPLETED
            )
            await emit_collector_progress(
                progress_callback,
                CollectorProgressEvent(
                    phase=final_phase,
                    total_providers=len(batch.outcomes),
                    raw_count=deduplicated.raw_count,
                    merged_count=persistence.merged_count,
                    duplicate_count=persistence.duplicate_count,
                    new_count=persistence.new_count,
                    changed_count=persistence.changed_count,
                    unchanged_count=persistence.unchanged_count,
                    message=(
                        "Сбор остановлен. Полученные данные сохранены."
                        if final_phase == CollectorProgressPhase.CANCELLED
                        else "Сбор тендеров завершён."
                    ),
                ),
            )
            return result
        except Exception as exc:
            self.repository.complete_run(
                run_id,
                status=CollectionRunStatus.FAILED,
                error=exc,
            )
            await emit_collector_progress(
                progress_callback,
                CollectorProgressEvent(
                    phase=CollectorProgressPhase.FAILED,
                    message=f"{type(exc).__name__}: {exc}",
                ),
            )
            raise


def _status_for_batch(batch: object) -> CollectionRunStatus:
    if bool(getattr(batch, "cancelled", False)):
        return CollectionRunStatus.CANCELLED
    if bool(getattr(batch, "has_partial_failures", False)):
        return CollectionRunStatus.PARTIAL
    return CollectionRunStatus.COMPLETED


__all__ = ["CollectorService"]
