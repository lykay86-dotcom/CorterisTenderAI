"""CollectorService freshness-stage integration tests."""

from __future__ import annotations

import asyncio

from app.tenders.collector.async_engine import (
    AsyncProviderBatchResult,
    AsyncProviderSearchOutcome,
    AsyncProviderSearchStatus,
)
from app.tenders.collector.collector_service import CollectorService
from app.tenders.collector.freshness import TenderFreshnessService
from app.tenders.collector.progress import CollectorProgressPhase
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.models import TenderSource
from app.tenders.provider_base import TenderSearchQuery, TenderSearchResult
from tests.collector_c3_helpers import make_tender


class Engine:
    async def search(
        self,
        query,
        *,
        provider_ids=None,
        cancellation_token=None,
        progress_callback=None,
    ):
        del query, provider_ids, cancellation_token, progress_callback
        tender = make_tender(
            source=TenderSource.EIS,
            external_id="freshness-service",
            deadline_day=14,
        )
        return AsyncProviderBatchResult(
            results=(
                TenderSearchResult(provider_id="eis", items=(tender,)),
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
            started_at="2026-07-12T13:00:00+00:00",
            completed_at="2026-07-12T13:00:01+00:00",
            elapsed_ms=1000,
        )


def test_service_checks_freshness_before_ranking(tmp_path) -> None:
    async def scenario() -> None:
        events = []
        repository = CollectorStateRepository(
            tmp_path / "tender_registry.sqlite3"
        )
        service = CollectorService(
            Engine(),
            repository,
            freshness_service=TenderFreshnessService(
                user_timezone="UTC"
            ),
        )
        result = await service.collect(
            TenderSearchQuery(keywords=("видеонаблюдение",)),
            progress_callback=events.append,
        )

        phases = [event.phase for event in events]
        assert phases.index(
            CollectorProgressPhase.VERIFYING
        ) < phases.index(
            CollectorProgressPhase.CHECKING_FRESHNESS
        ) < phases.index(CollectorProgressPhase.RANKING)
        assert result.metadata["due_soon_count"] == 1
        key = result.deduplication.items[0].canonical_key
        state = repository.get_freshness_state(key)
        assert state is not None
        assert state.recheck_interval_minutes == 180

    asyncio.run(scenario())
