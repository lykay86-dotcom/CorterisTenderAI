"""End-to-end collection orchestration: providers -> merge -> persistence."""

from __future__ import annotations

from typing import Sequence

from app.tenders.collector.async_engine import AsyncProviderSearchEngine
from app.tenders.collector.cancellation import CollectorCancellationToken
from app.tenders.collector.deduplicator import TenderDeduplicator
from app.tenders.collector.freshness import TenderFreshnessService
from app.tenders.collector.models import (
    CollectionRunStatus,
    CollectorRunResult,
)
from app.tenders.collector.normalizer import TenderNormalizer
from app.tenders.collector.participation_score import (
    CorterisParticipationRanker,
)
from app.tenders.collector.progress import (
    CollectorProgressCallback,
    CollectorProgressEvent,
    CollectorProgressPhase,
    emit_collector_progress,
)
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.collector.verification import (
    TenderVerificationService,
)
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
        ranker: CorterisParticipationRanker | None = None,
        verifier: TenderVerificationService | None = None,
        freshness_service: TenderFreshnessService | None = None,
    ) -> None:
        self.engine = engine
        self.repository = repository
        self.normalizer = normalizer or TenderNormalizer()
        self.deduplicator = deduplicator or TenderDeduplicator(
            self.normalizer
        )
        self.ranker = ranker or CorterisParticipationRanker()
        self.verifier = verifier or TenderVerificationService(
            normalizer=self.normalizer,
            history_loader=self.repository.get_verification_history,
        )
        self.freshness_service = (
            freshness_service or TenderFreshnessService()
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
                    phase=CollectorProgressPhase.VERIFYING,
                    total_providers=len(batch.outcomes),
                    raw_count=deduplicated.raw_count,
                    merged_count=deduplicated.merged_count,
                    duplicate_count=deduplicated.duplicate_count,
                    message=(
                        "Проверка критичных полей и происхождения данных…"
                    ),
                ),
            )
            verification = self.verifier.verify(
                deduplicated,
                observed_at=batch.completed_at,
            )
            verified_deduplication = verification.deduplication

            await emit_collector_progress(
                progress_callback,
                CollectorProgressEvent(
                    phase=CollectorProgressPhase.CHECKING_FRESHNESS,
                    total_providers=len(batch.outcomes),
                    raw_count=verified_deduplication.raw_count,
                    merged_count=verified_deduplication.merged_count,
                    duplicate_count=(
                        verified_deduplication.duplicate_count
                    ),
                    message=(
                        "Нормализация сроков и расчёт повторной проверки…"
                    ),
                ),
            )
            freshness = self.freshness_service.evaluate(
                verification,
                now=batch.completed_at,
            )

            await emit_collector_progress(
                progress_callback,
                CollectorProgressEvent(
                    phase=CollectorProgressPhase.RANKING,
                    total_providers=len(batch.outcomes),
                    raw_count=verified_deduplication.raw_count,
                    merged_count=verified_deduplication.merged_count,
                    duplicate_count=(
                        verified_deduplication.duplicate_count
                    ),
                    message="Расчёт объяснимого рейтинга Кортерис…",
                ),
            )
            rankings = {
                item.canonical_key: self.ranker.score(item.tender)
                for item in verified_deduplication.items
            }

            await emit_collector_progress(
                progress_callback,
                CollectorProgressEvent(
                    phase=CollectorProgressPhase.SAVING,
                    total_providers=len(batch.outcomes),
                    raw_count=verified_deduplication.raw_count,
                    merged_count=verified_deduplication.merged_count,
                    duplicate_count=(
                        verified_deduplication.duplicate_count
                    ),
                    message="Сохранение результатов в локальный реестр…",
                ),
            )
            persistence = self.repository.save_batch(
                run_id,
                verified_deduplication,
                observed_at=batch.completed_at,
                rankings=rankings,
                verification=verification,
                freshness=freshness,
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
                deduplication=verified_deduplication,
                persistence=persistence,
                warnings=warnings,
                metadata={
                    "partial_failures": batch.has_partial_failures,
                    "cancelled": batch.cancelled,
                    "verification_run_id": (
                        persistence.verification_run_id
                    ),
                    "verified_field_count": (
                        persistence.verified_field_count
                    ),
                    "field_conflict_count": (
                        persistence.conflict_count
                    ),
                    "unresolved_field_conflict_count": (
                        persistence.unresolved_conflict_count
                    ),
                    "verification_incomplete_count": (
                        persistence.verification_incomplete_count
                    ),
                    "stale_count": persistence.stale_count,
                    "due_soon_count": persistence.due_soon_count,
                    "expired_count": persistence.expired_count,
                    "reverification_due_count": (
                        persistence.reverification_due_count
                    ),
                    "ranked_count": persistence.ranked_count,
                    "recommended_count": persistence.recommended_count,
                    "manual_review_count": persistence.manual_review_count,
                    "possible_count": persistence.possible_count,
                    "not_recommended_count": (
                        persistence.not_recommended_count
                    ),
                    "high_score_count": sum(
                        score.total_score >= 80
                        for score in rankings.values()
                    ),
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
                    raw_count=verified_deduplication.raw_count,
                    merged_count=persistence.merged_count,
                    duplicate_count=persistence.duplicate_count,
                    new_count=persistence.new_count,
                    changed_count=persistence.changed_count,
                    unchanged_count=persistence.unchanged_count,
                    stale_count=persistence.stale_count,
                    due_soon_count=persistence.due_soon_count,
                    expired_count=persistence.expired_count,
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
