"""End-to-end collection orchestration: providers -> merge -> persistence."""

from __future__ import annotations

from typing import Sequence

from app.tenders.collector.async_engine import AsyncProviderSearchEngine, CollectorRunBudget
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
    ParticipationScoringContext,
)
from app.tenders.collector.progress import (
    CollectorProgressCallback,
    CollectorProgressEvent,
    CollectorProgressPhase,
    emit_collector_progress,
)
from app.tenders.collector.search_errors import classify_search_error
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.collector.stop_factor import (
    StopFactorEngine,
    StopFactorStatus,
)
from app.tenders.collector.aggregator_discovery import (
    AggregatorDiscoveryCapacityError,
    AggregatorDiscoveryRepository,
    is_aggregator_discovery,
)
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
        stop_factor_engine: StopFactorEngine | None = None,
        aggregator_discovery_repository: AggregatorDiscoveryRepository | None = None,
    ) -> None:
        self.engine = engine
        self.repository = repository
        if (
            isinstance(engine, AsyncProviderSearchEngine)
            and engine.accepted_page_repository is None
        ):
            engine.accepted_page_repository = repository
        engine_normalizer = getattr(engine, "normalizer", None)
        self.normalizer = normalizer or engine_normalizer or TenderNormalizer()
        engine_deduplicator = getattr(engine, "deduplicator", None)
        self.deduplicator = (
            deduplicator or engine_deduplicator or TenderDeduplicator(self.normalizer)
        )
        self.ranker = ranker or CorterisParticipationRanker()
        self.verifier = verifier or TenderVerificationService(
            normalizer=self.normalizer,
            history_loader=self.repository.get_verification_history,
        )
        self.freshness_service = freshness_service or TenderFreshnessService()
        self.stop_factor_engine = stop_factor_engine
        self.aggregator_discovery_repository = (
            aggregator_discovery_repository or AggregatorDiscoveryRepository(self.repository.path)
        )

    async def collect(
        self,
        query: TenderSearchQuery,
        *,
        provider_ids: Sequence[str] | None = None,
        cancellation_token: CollectorCancellationToken | None = None,
        progress_callback: CollectorProgressCallback | None = None,
        run_budget: CollectorRunBudget | None = None,
    ) -> CollectorRunResult:
        requested = tuple(provider_ids or ())
        await emit_collector_progress(
            progress_callback,
            CollectorProgressEvent(
                phase=CollectorProgressPhase.PREPARING,
                total_providers=len(requested),
                progress_percent=3,
                message="Подготовка запуска коллектора…",
            ),
        )
        run_id = self.repository.start_run(
            query,
            provider_ids=requested,
        )
        try:
            engine_kwargs: dict[str, object] = {
                "provider_ids": provider_ids,
                "cancellation_token": cancellation_token,
            }
            if isinstance(self.engine, AsyncProviderSearchEngine):
                engine_kwargs["run_id"] = run_id
                engine_kwargs["run_budget"] = run_budget
            if progress_callback is None:
                batch = await self.engine.search(
                    query,
                    **engine_kwargs,
                )
            else:
                engine_kwargs["progress_callback"] = progress_callback
                batch = await self.engine.search(
                    query,
                    **engine_kwargs,
                )

            await emit_collector_progress(
                progress_callback,
                CollectorProgressEvent(
                    phase=CollectorProgressPhase.NORMALIZING,
                    total_providers=len(batch.outcomes),
                    progress_percent=76,
                    raw_count=len(batch.raw_items),
                    message=("Нормализация данных, полученных от источников…"),
                ),
            )
            discovery_items = tuple(
                item for item in batch.raw_items if is_aggregator_discovery(item)
            )
            authoritative_items = tuple(
                item for item in batch.raw_items if not is_aggregator_discovery(item)
            )
            discovery_records = []
            discovery_rejected_count = 0
            for item in discovery_items:
                try:
                    discovery_records.append(
                        self.aggregator_discovery_repository.enqueue(
                            item,
                            discovered_at=batch.completed_at,
                        )
                    )
                except AggregatorDiscoveryCapacityError:
                    discovery_rejected_count += 1
            normalized = (
                self.normalizer.normalize_many(authoritative_items)
                if batch.deduplication is None
                else ()
            )

            await emit_collector_progress(
                progress_callback,
                CollectorProgressEvent(
                    phase=CollectorProgressPhase.DEDUPLICATING,
                    total_providers=len(batch.outcomes),
                    progress_percent=80,
                    raw_count=(
                        len(normalized)
                        if batch.deduplication is None
                        else batch.deduplication.raw_count
                    ),
                    message="Поиск и объединение дублей…",
                ),
            )
            deduplicated = batch.deduplication or self.deduplicator.deduplicate(normalized)

            await emit_collector_progress(
                progress_callback,
                CollectorProgressEvent(
                    phase=CollectorProgressPhase.VERIFYING,
                    total_providers=len(batch.outcomes),
                    progress_percent=86,
                    raw_count=deduplicated.raw_count,
                    merged_count=deduplicated.merged_count,
                    duplicate_count=deduplicated.duplicate_count,
                    message=("Проверка критичных полей и происхождения данных…"),
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
                    progress_percent=89,
                    raw_count=verified_deduplication.raw_count,
                    merged_count=verified_deduplication.merged_count,
                    duplicate_count=(verified_deduplication.duplicate_count),
                    message=("Нормализация сроков и расчёт повторной проверки…"),
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
                    progress_percent=92,
                    raw_count=verified_deduplication.raw_count,
                    merged_count=verified_deduplication.merged_count,
                    duplicate_count=(verified_deduplication.duplicate_count),
                    message="Расчёт объяснимого рейтинга Кортерис…",
                ),
            )
            stop_assessments = (
                {
                    item.canonical_key: self.stop_factor_engine.evaluate(
                        item.canonical_key,
                        item.tender,
                        now=None,
                    )
                    for item in verified_deduplication.items
                }
                if self.stop_factor_engine is not None
                else {}
            )
            rankings = {
                item.canonical_key: self.ranker.score(
                    item.tender,
                    ParticipationScoringContext(
                        stop_factor_assessment=stop_assessments.get(item.canonical_key)
                    ),
                )
                for item in verified_deduplication.items
            }

            await emit_collector_progress(
                progress_callback,
                CollectorProgressEvent(
                    phase=CollectorProgressPhase.SAVING,
                    total_providers=len(batch.outcomes),
                    progress_percent=95,
                    raw_count=verified_deduplication.raw_count,
                    merged_count=verified_deduplication.merged_count,
                    duplicate_count=(verified_deduplication.duplicate_count),
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
            warnings = tuple(warning for outcome in batch.outcomes for warning in outcome.warnings)
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
                    "verification_run_id": (persistence.verification_run_id),
                    "verified_field_count": (persistence.verified_field_count),
                    "field_conflict_count": (persistence.conflict_count),
                    "unresolved_field_conflict_count": (persistence.unresolved_conflict_count),
                    "verification_incomplete_count": (persistence.verification_incomplete_count),
                    "stale_count": persistence.stale_count,
                    "due_soon_count": persistence.due_soon_count,
                    "expired_count": persistence.expired_count,
                    "reverification_due_count": (persistence.reverification_due_count),
                    "ranked_count": persistence.ranked_count,
                    "recommended_count": persistence.recommended_count,
                    "manual_review_count": persistence.manual_review_count,
                    "possible_count": persistence.possible_count,
                    "not_recommended_count": (persistence.not_recommended_count),
                    "high_score_count": sum(score.total_score >= 80 for score in rankings.values()),
                    "aggregator_discovery_count": len(discovery_records),
                    "aggregator_discovery_rejected_count": discovery_rejected_count,
                    "official_verification_queue_count": len(
                        self.aggregator_discovery_repository.list_pending(limit=1000)
                    ),
                    "stop_factor_blocked_count": sum(
                        item.status == StopFactorStatus.BLOCKED_BY_REQUIREMENT
                        for item in stop_assessments.values()
                    ),
                    "stop_factor_data_insufficient_count": sum(
                        item.status == StopFactorStatus.DATA_INSUFFICIENT
                        for item in stop_assessments.values()
                    ),
                    "stop_factor_conditional_count": sum(
                        item.status == StopFactorStatus.CONDITIONAL
                        for item in stop_assessments.values()
                    ),
                },
            )
            final_phase = (
                CollectorProgressPhase.CANCELLED
                if status == CollectionRunStatus.CANCELLED
                else CollectorProgressPhase.FAILED
                if status in {CollectionRunStatus.FAILED, CollectionRunStatus.TIMED_OUT}
                else CollectorProgressPhase.COMPLETED
            )
            await emit_collector_progress(
                progress_callback,
                CollectorProgressEvent(
                    phase=final_phase,
                    total_providers=len(batch.outcomes),
                    progress_percent=100,
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
            failure = classify_search_error(exc)
            self.repository.complete_run(
                run_id,
                status=CollectionRunStatus.FAILED,
                error_code=failure.code,
                error_message=failure.message,
            )
            await emit_collector_progress(
                progress_callback,
                CollectorProgressEvent(
                    phase=CollectorProgressPhase.FAILED,
                    progress_percent=100,
                    message=failure.message,
                ),
            )
            raise


def _status_for_batch(batch: object) -> CollectionRunStatus:
    if bool(getattr(batch, "cancelled", False)):
        return CollectionRunStatus.CANCELLED
    if bool(getattr(batch, "timed_out", False)):
        return CollectionRunStatus.TIMED_OUT
    outcomes = tuple(getattr(batch, "outcomes", ()))
    successful = sum(bool(getattr(outcome, "successful", False)) for outcome in outcomes)
    if successful == 0:
        return CollectionRunStatus.FAILED
    if any(not bool(getattr(outcome, "successful", False)) for outcome in outcomes):
        return CollectionRunStatus.PARTIAL
    return CollectionRunStatus.COMPLETED


__all__ = ["CollectorService"]
