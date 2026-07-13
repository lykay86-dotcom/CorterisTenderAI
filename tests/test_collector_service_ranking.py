"""Automatic ranking integration in CollectorService."""

from __future__ import annotations

import asyncio

from app.tenders.collector.async_engine import (
    AsyncProviderBatchResult,
    AsyncProviderSearchOutcome,
    AsyncProviderSearchStatus,
)
from app.tenders.collector.collector_service import CollectorService
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.provider_base import TenderSearchQuery, TenderSearchResult
from tests.collector_c3_helpers import make_tender


class Engine:
    async def search(
        self,
        query,
        *,
        provider_ids=None,
        cancellation_token=None,
    ):
        del query, provider_ids, cancellation_token
        tender = make_tender(deadline_day=30)
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
                    elapsed_ms=10,
                    item_count=1,
                ),
            ),
            started_at="2026-07-12T10:00:00+00:00",
            completed_at="2026-07-12T10:00:01+00:00",
            elapsed_ms=1000,
        )


def test_collector_automatically_scores_saved_tenders(tmp_path) -> None:
    async def scenario() -> None:
        repository = CollectorStateRepository(tmp_path / "tender_registry.sqlite3")
        result = await CollectorService(
            Engine(),
            repository,
        ).collect(TenderSearchQuery(keywords=("видеонаблюдение",)))

        assert result.persistence.ranked_count == 1
        assert result.metadata["ranked_count"] == 1
        scores = repository.list_run_scores(result.run_id)
        assert len(scores) == 1
        assert scores[0].total_score > 0

    asyncio.run(scenario())
