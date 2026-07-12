"""CollectorService integration for verification before ranking."""

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
        eis = make_tender(
            source=TenderSource.EIS,
            external_id="eis-service",
            amount="1500000.00",
        )
        aggregator = make_tender(
            source=TenderSource.CUSTOM,
            external_id="agg-service",
            amount="2300000.00",
            raw_metadata={"aggregator": True},
        )
        return AsyncProviderBatchResult(
            results=(
                TenderSearchResult(
                    provider_id="eis",
                    items=(eis,),
                ),
                TenderSearchResult(
                    provider_id="aggregator",
                    items=(aggregator,),
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
                AsyncProviderSearchOutcome(
                    provider_id="aggregator",
                    display_name="Агрегатор",
                    status=AsyncProviderSearchStatus.SUCCESS,
                    elapsed_ms=10,
                    item_count=1,
                ),
            ),
            started_at="2026-07-12T10:00:00+00:00",
            completed_at="2026-07-12T10:00:01+00:00",
            elapsed_ms=1000,
        )


def test_service_verifies_before_ranking_and_persistence(tmp_path) -> None:
    async def scenario():
        events = []
        repository = CollectorStateRepository(
            tmp_path / "tender_registry.sqlite3"
        )
        result = await CollectorService(
            Engine(),
            repository,
        ).collect(
            TenderSearchQuery(keywords=("видеонаблюдение",)),
            progress_callback=events.append,
        )

        phases = [event.phase for event in events]
        assert phases.index(
            CollectorProgressPhase.VERIFYING
        ) < phases.index(CollectorProgressPhase.RANKING)
        assert result.persistence.verification_run_id
        assert result.metadata["field_conflict_count"] >= 1
        tender = result.deduplication.items[0].tender
        assert str(tender.price.amount) == "1500000.00"
        state = repository.get_verification_state(
            result.deduplication.items[0].canonical_key
        )
        assert state is not None

    asyncio.run(scenario())
