"""Pipeline progress tests for CollectorService."""

from __future__ import annotations

import asyncio

from app.tenders.collector.async_engine import (
    AsyncProviderBatchResult,
    AsyncProviderSearchOutcome,
    AsyncProviderSearchStatus,
)
from app.tenders.collector.collector_service import CollectorService
from app.tenders.collector.progress import CollectorProgressPhase
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.models import TenderSource
from app.tenders.provider_base import TenderSearchQuery, TenderSearchResult
from tests.collector_c3_helpers import make_tender


class ProgressEngine:
    def __init__(self, batch) -> None:
        self.batch = batch

    async def search(
        self,
        query,
        *,
        provider_ids=None,
        cancellation_token=None,
        progress_callback=None,
    ):
        del query, provider_ids, cancellation_token
        return self.batch


def _batch() -> AsyncProviderBatchResult:
    tender = make_tender(
        source=TenderSource.EIS,
        external_id="eis-progress",
    )
    return AsyncProviderBatchResult(
        results=(
            TenderSearchResult(
                provider_id="eis",
                items=(tender,),
            ),
        ),
        outcomes=(
            AsyncProviderSearchOutcome(
                provider_id="eis",
                display_name="ЕИС",
                status=AsyncProviderSearchStatus.SUCCESS,
                elapsed_ms=100,
                item_count=1,
            ),
        ),
        started_at="2026-07-12T10:00:00+00:00",
        completed_at="2026-07-12T10:00:01+00:00",
        elapsed_ms=1000,
    )


def test_service_emits_pipeline_stages_and_saves_result(tmp_path) -> None:
    async def scenario() -> None:
        events = []
        repository = CollectorStateRepository(tmp_path / "tender_registry.sqlite3")
        service = CollectorService(
            ProgressEngine(_batch()),
            repository,
        )

        result = await service.collect(
            TenderSearchQuery(keywords=("видеонаблюдение",)),
            provider_ids=("eis",),
            progress_callback=events.append,
        )

        phases = [event.phase for event in events]
        assert phases == [
            CollectorProgressPhase.PREPARING,
            CollectorProgressPhase.NORMALIZING,
            CollectorProgressPhase.DEDUPLICATING,
            CollectorProgressPhase.VERIFYING,
            CollectorProgressPhase.CHECKING_FRESHNESS,
            CollectorProgressPhase.RANKING,
            CollectorProgressPhase.SAVING,
            CollectorProgressPhase.COMPLETED,
        ]
        assert result.persistence.new_count == 1
        assert events[-1].new_count == 1
        assert events[-1].merged_count == 1
        assert repository.get_run(result.run_id) is not None

    asyncio.run(scenario())
