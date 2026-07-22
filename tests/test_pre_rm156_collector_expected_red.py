"""P2 expected-red contracts for the PRE-RM-156 Collector foundation.

Strict xfails identify boundaries that are intentionally absent on the P1
baseline. Passing tests preserve protections that already exist. Run this file
with ``--runxfail`` to prove that every expected-red assertion fails for the
documented reason before implementation.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, fields
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import httpx
import pytest

from app.tenders.collector.aggregator_discovery import is_aggregator_discovery
from app.tenders.collector.async_engine import (
    AsyncProviderSearchEngine,
    AsyncProviderSearchStatus,
)
from app.tenders.collector.async_http import AsyncHttpStatusError
from app.tenders.collector.async_provider import AsyncTenderProvider
from app.tenders.collector.cancellation import CollectorCancellationToken
from app.tenders.collector.checkpoint import CollectorCheckpoint
from app.tenders.collector.collector_service import _status_for_batch
from app.tenders.collector.models import CollectionRunStatus
from app.tenders.collector.schema import CollectorSchemaMigrator
from app.tenders.collector.search_errors import classify_search_error
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.collector_database import initialize_collector_database
from app.tenders.models import TenderSource
from app.tenders.provider_base import (
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderHealth,
    ProviderHealthStatus,
    TenderSearchQuery,
    TenderSearchResult,
)
from app.tenders.providers.eis_async import AsyncEisTenderProvider
from tests.collector_c3_helpers import make_tender
from tests.test_collector_eis_async_provider import SEARCH_HTML, _client


def expected_red(contract_id: str):
    return pytest.mark.xfail(
        strict=True,
        reason=f"PRE-RM156 expected-red: {contract_id}",
    )


@dataclass(frozen=True, slots=True)
class ContractPage:
    provider_id: str
    items: tuple[object, ...]
    page_number: int
    next_cursor: str | None
    is_last: bool
    artifact_refs: tuple[object, ...] = ()
    warnings: tuple[str, ...] = ()


class PagedProvider(AsyncTenderProvider):
    connection_mode = "fixture"
    parser_version = "expected-red-v1"

    def __init__(
        self,
        provider_id: str,
        pages: tuple[ContractPage, ...],
        *,
        cancel_after_first: bool = False,
    ) -> None:
        self.pages = pages
        self.cancel_after_first = cancel_after_first
        self.search_calls = 0
        self.iterator_calls = 0
        self.descriptor = ProviderDescriptor(
            id=provider_id,
            display_name=provider_id,
            source=TenderSource.CUSTOM,
            homepage_url="https://example.test/",
            capabilities=ProviderCapabilities(search=True),
            implementation_status="fixture",
        )

    async def search(self, query, *, cancellation_token=None):
        del query, cancellation_token
        self.search_calls += 1
        first = self.pages[0]
        return TenderSearchResult(
            provider_id=self.descriptor.id,
            items=tuple(first.items),
            page=first.page_number,
            next_page_token=first.next_cursor or "",
        )

    async def iter_search_pages(self, query, *, resume=None, cancellation_token=None):
        del query, resume
        self.iterator_calls += 1
        for index, page in enumerate(self.pages):
            if cancellation_token is not None:
                cancellation_token.throw_if_cancelled()
            yield page
            if index == 0 and self.cancel_after_first and cancellation_token is not None:
                cancellation_token.cancel("expected-red cancellation between pages")

    async def get_tender(self, external_id, *, cancellation_token=None):
        del external_id, cancellation_token
        raise NotImplementedError

    async def list_documents(self, external_id, *, cancellation_token=None):
        del external_id, cancellation_token
        return ()

    async def check_health(self, *, cancellation_token=None):
        del cancellation_token
        return ProviderHealth(
            provider_id=self.descriptor.id,
            status=ProviderHealthStatus.AVAILABLE,
            checked_at=datetime.now(timezone.utc).isoformat(),
        )


def _page(provider_id: str, number: int, *, next_cursor: str | None, is_last: bool):
    tender = make_tender(
        source=TenderSource.CUSTOM,
        external_id=f"{provider_id}-{number}",
        procurement_number=f"P2-{provider_id}-{number}",
    )
    return ContractPage(
        provider_id=provider_id,
        items=(tender,),
        page_number=number,
        next_cursor=next_cursor,
        is_last=is_last,
    )


def test_engine_consumes_every_typed_provider_page() -> None:
    async def scenario() -> None:
        provider = PagedProvider(
            "paged",
            (
                _page("paged", 1, next_cursor="page-2", is_last=False),
                _page("paged", 2, next_cursor="page-3", is_last=False),
                _page("paged", 3, next_cursor=None, is_last=True),
            ),
        )
        result = await AsyncProviderSearchEngine((provider,)).search(TenderSearchQuery())

        assert provider.iterator_calls == 1
        assert provider.search_calls == 0
        assert tuple(item.external_id for item in result.raw_items) == (
            "paged-1",
            "paged-2",
            "paged-3",
        )

    asyncio.run(scenario())


def test_engine_rejects_repeated_cursor_without_unbounded_loop() -> None:
    async def scenario() -> None:
        provider = PagedProvider(
            "cycle",
            (
                _page("cycle", 1, next_cursor="same", is_last=False),
                _page("cycle", 2, next_cursor="same", is_last=False),
            ),
        )
        result = await asyncio.wait_for(
            AsyncProviderSearchEngine((provider,)).search(TenderSearchQuery()),
            timeout=1.0,
        )

        assert provider.iterator_calls == 1
        assert result.outcomes[0].status is AsyncProviderSearchStatus.FAILED
        assert result.outcomes[0].error_code == "provider_cursor_cycle"

    asyncio.run(scenario())


def test_cancellation_between_pages_drops_the_unaccepted_page() -> None:
    async def scenario() -> None:
        token = CollectorCancellationToken()
        provider = PagedProvider(
            "cancel-pages",
            (
                _page("cancel-pages", 1, next_cursor="page-2", is_last=False),
                _page("cancel-pages", 2, next_cursor=None, is_last=True),
            ),
            cancel_after_first=True,
        )
        result = await AsyncProviderSearchEngine((provider,)).search(
            TenderSearchQuery(),
            cancellation_token=token,
        )

        assert result.cancelled
        assert tuple(item.external_id for item in result.raw_items) == ("cancel-pages-1",)
        assert result.outcomes[0].status is AsyncProviderSearchStatus.CANCELLED

    asyncio.run(scenario())


@expected_red("C-CP-001")
def test_eis_search_does_not_advance_checkpoint_before_page_acceptance(tmp_path: Path) -> None:
    async def scenario() -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                content=SEARCH_HTML,
                headers={"content-type": "text/html; charset=utf-8"},
                request=request,
            )

        repository = CollectorStateRepository(tmp_path / "registry.sqlite3")
        repository.initialize()
        client, raw = _client(handler)
        provider = AsyncEisTenderProvider(client, checkpoint_repository=repository)
        query = TenderSearchQuery(extra={"incremental": False})

        await provider.search(query)
        checkpoint = repository.get_checkpoint(
            "eis",
            scope_key=provider.checkpoints.scope_key(query),
        )
        await raw.aclose()

        assert checkpoint is None

    asyncio.run(scenario())


def test_checkpoint_carries_typed_replay_and_commit_identity() -> None:
    names = {item.name for item in fields(CollectorCheckpoint)}

    assert {
        "contract_version",
        "parser_version",
        "query_fingerprint",
        "last_accepted_page_id",
        "accepted_page_count",
        "replay_generation",
    }.issubset(names)
    assert hasattr(CollectorStateRepository, "save_accepted_page")


def test_zero_success_batch_is_failed_not_partial() -> None:
    batch = SimpleNamespace(
        cancelled=False,
        timed_out=False,
        has_partial_failures=True,
        outcomes=(SimpleNamespace(successful=False, status=AsyncProviderSearchStatus.FAILED),),
    )

    assert _status_for_batch(batch) is CollectionRunStatus.FAILED


def test_overall_timeout_keeps_its_own_terminal_status() -> None:
    batch = SimpleNamespace(
        cancelled=False,
        timed_out=True,
        has_partial_failures=True,
        outcomes=(SimpleNamespace(successful=False, status=AsyncProviderSearchStatus.TIMED_OUT),),
    )

    assert _status_for_batch(batch).value == "timed_out"


def test_discovery_is_excluded_from_engine_partial_deduplication() -> None:
    async def scenario() -> None:
        discovery = make_tender(
            source=TenderSource.CUSTOM,
            external_id="discovery-only",
            raw_metadata={"aggregator": True, "discovery_only": True},
        )
        provider = PagedProvider(
            "discovery",
            (
                ContractPage(
                    provider_id="discovery",
                    items=(discovery,),
                    page_number=1,
                    next_cursor=None,
                    is_last=True,
                ),
            ),
        )
        result = await AsyncProviderSearchEngine((provider,)).search(TenderSearchQuery())

        assert is_aggregator_discovery(result.raw_items[0])
        assert result.deduplication is not None
        assert result.deduplication.raw_count == 0
        assert result.deduplication.items == ()
        assert result.snapshot is not None
        assert result.snapshot.partial_items == ()

    asyncio.run(scenario())


def test_completion_order_does_not_change_canonical_batch_order() -> None:
    class DelayedProvider(PagedProvider):
        def __init__(self, provider_id: str, delay: float) -> None:
            super().__init__(
                provider_id,
                (_page(provider_id, 1, next_cursor=None, is_last=True),),
            )
            self.delay = delay

        async def search(self, query, *, cancellation_token=None):
            await asyncio.sleep(self.delay)
            return await super().search(query, cancellation_token=cancellation_token)

    async def collect(delays: tuple[float, float]) -> tuple[str, ...]:
        engine = AsyncProviderSearchEngine(
            (
                DelayedProvider("alpha", delays[0]),
                DelayedProvider("beta", delays[1]),
            )
        )
        result = await engine.search(TenderSearchQuery())
        return tuple(item.canonical_key for item in result.deduplication.items)

    first = asyncio.run(collect((0.03, 0.0)))
    second = asyncio.run(collect((0.0, 0.03)))

    assert first == second == tuple(sorted(first))


def test_engine_rejects_duplicate_provider_identity_at_composition() -> None:
    first = PagedProvider("duplicate", (_page("duplicate", 1, next_cursor=None, is_last=True),))
    second = PagedProvider("duplicate", (_page("duplicate", 2, next_cursor=None, is_last=True),))

    with pytest.raises(ValueError, match="duplicate provider identity"):
        AsyncProviderSearchEngine((first, second))


def test_raw_artifact_owner_and_page_commit_contract_exist() -> None:
    artifact_module = importlib.util.find_spec("app.tenders.collector.artifacts")

    assert artifact_module is not None
    assert hasattr(CollectorStateRepository, "save_accepted_page")


def test_public_search_error_never_contains_secret_url_or_body() -> None:
    error = AsyncHttpStatusError(
        "Authorization: Bearer top-secret response body",
        url="https://provider.example/api?api_key=top-secret",
        provider_id="fixture",
        attempts=1,
        transient=False,
        status_code=401,
    )

    failure = classify_search_error(error)
    public = f"{failure.code} {failure.message} {failure.category.value}".casefold()

    assert "top-secret" not in public
    assert "api_key" not in public
    assert "authorization" not in public
    assert "://" not in public


def test_old_collector_schema_migration_creates_verified_backup(tmp_path: Path) -> None:
    database = tmp_path / "registry.sqlite3"
    initialize_collector_database(database)
    backup_directory = tmp_path / "backups"
    existing_backups = {path.resolve() for path in backup_directory.rglob("*") if path.is_file()}
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE tender_registry_meta SET value='13' WHERE key='collector_schema_version'"
        )

    with sqlite3.connect(database) as connection:
        CollectorSchemaMigrator().migrate(connection)

    new_backup_files = tuple(
        path
        for path in backup_directory.rglob("*")
        if path.is_file()
        and path.resolve() not in existing_backups
        and path.suffix.casefold() in {".db", ".sqlite", ".sqlite3"}
    )
    assert new_backup_files


def test_repository_rejects_overlapping_active_collector_runs(tmp_path: Path) -> None:
    repository = CollectorStateRepository(tmp_path / "registry.sqlite3")
    repository.initialize()
    repository.start_run(TenderSearchQuery(), provider_ids=("eis",))

    with pytest.raises(RuntimeError, match="collector run already active"):
        repository.start_run(TenderSearchQuery(), provider_ids=("eis",))
