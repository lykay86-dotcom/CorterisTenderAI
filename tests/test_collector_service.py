"""Tests for end-to-end collector orchestration."""

from __future__ import annotations

import asyncio

from app.tenders.collector.async_engine import (
    AsyncProviderBatchResult,
    AsyncProviderSearchOutcome,
    AsyncProviderSearchStatus,
)
from app.tenders.collector.collector_service import CollectorService
from app.tenders.collector.models import CollectionRunStatus
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.models import TenderSource
from app.tenders.provider_base import TenderSearchQuery, TenderSearchResult
from tests.collector_c3_helpers import make_tender


class FakeEngine:
    def __init__(self, batch) -> None:
        self.batch = batch

    async def search(self, query, *, provider_ids=None, cancellation_token=None):
        del query, provider_ids, cancellation_token
        return self.batch


class FailingEngine:
    async def search(self, query, *, provider_ids=None, cancellation_token=None):
        del query, provider_ids, cancellation_token
        raise RuntimeError("collector failed")


def _batch() -> AsyncProviderBatchResult:
    first = make_tender(
        source=TenderSource.EIS,
        external_id="eis-1",
        raw_metadata={"eis_number": "0373100000126000001"},
    )
    duplicate = make_tender(
        source=TenderSource.CUSTOM,
        external_id="mirror-1",
        procurement_number="mirror-1",
        raw_metadata={"eis_number": "0373100000126000001"},
    )
    return AsyncProviderBatchResult(
        results=(
            TenderSearchResult(
                provider_id="eis",
                items=(first,),
            ),
            TenderSearchResult(
                provider_id="mirror",
                items=(duplicate,),
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
            AsyncProviderSearchOutcome(
                provider_id="mirror",
                display_name="Зеркало",
                status=AsyncProviderSearchStatus.FAILED,
                elapsed_ms=50,
                error_type="TimeoutError",
                error_message="timeout",
            ),
        ),
        started_at="2026-07-12T10:00:00+00:00",
        completed_at="2026-07-12T10:00:01+00:00",
        elapsed_ms=1000,
    )


def test_service_persists_partial_batch_without_losing_results(
    tmp_path,
) -> None:
    async def scenario() -> None:
        repository = CollectorStateRepository(tmp_path / "tender_registry.sqlite3")
        service = CollectorService(FakeEngine(_batch()), repository)

        result = await service.collect(
            TenderSearchQuery(keywords=("СКУД",)),
            provider_ids=("eis", "mirror"),
        )

        assert result.status == CollectionRunStatus.PARTIAL
        assert result.deduplication.raw_count == 2
        assert result.deduplication.merged_count == 1
        assert result.persistence.new_count == 1
        run = repository.get_run(result.run_id)
        assert run is not None
        assert run.status == CollectionRunStatus.PARTIAL
        assert run.provider_count == 2
        assert run.successful_provider_count == 1
        assert run.failed_provider_count == 1

    asyncio.run(scenario())


def test_service_marks_run_failed_on_pipeline_exception(tmp_path) -> None:
    async def scenario() -> None:
        repository = CollectorStateRepository(tmp_path / "tender_registry.sqlite3")
        service = CollectorService(FailingEngine(), repository)

        try:
            await service.collect(TenderSearchQuery(keywords=("ОПС",)))
        except RuntimeError:
            pass
        else:
            raise AssertionError("RuntimeError expected")

        with repository._connect() as connection:
            row = connection.execute("SELECT * FROM collector_runs").fetchone()
        assert row is not None
        assert row["status"] == CollectionRunStatus.FAILED.value
        assert row["error_type"] == "provider_internal_error"
        assert row["error_message"] == "Источник завершил поиск с безопасно скрытой ошибкой."
        assert "collector failed" not in row["error_message"]

    asyncio.run(scenario())
