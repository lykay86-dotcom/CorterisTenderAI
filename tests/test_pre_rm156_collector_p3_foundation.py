"""Focused contracts for the PRE-RM-156 P3 shared Collector foundation."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any

import pytest

from app.tenders.collector import async_provider as page_contract
from app.tenders.collector.async_engine import (
    AsyncProviderSearchEngine,
    AsyncProviderSearchStatus,
    CollectorRunBudget,
)
from app.tenders.collector.async_provider import AsyncTenderProvider
from app.tenders.collector.cancellation import CollectorCancellationToken
from app.tenders.collector.checkpoint import CollectorCheckpoint
from app.tenders.collector.models import CollectionRunStatus
from app.tenders.collector.schema import COLLECTOR_SCHEMA_VERSION, CollectorSchemaMigrator
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
from tests.collector_c3_helpers import make_tender


class _LegacyOnePageProvider(AsyncTenderProvider):
    connection_mode = "fixture"
    contract_version = "contract-v1"
    parser_version = "parser-v1"

    def __init__(self, provider_id: str = "fixture") -> None:
        self.search_calls = 0
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
        return TenderSearchResult(
            provider_id=self.descriptor.id,
            items=(make_tender(source=TenderSource.CUSTOM, external_id="one"),),
            page=1,
        )

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


def test_default_page_adapter_preserves_legacy_provider() -> None:
    async def scenario() -> None:
        provider = _LegacyOnePageProvider()
        query = TenderSearchQuery(keywords=("camera",))
        pages = tuple(
            [
                page
                async for page in provider.iter_search_pages(
                    query,
                    cancellation_token=CollectorCancellationToken(),
                )
            ]
        )

        assert provider.search_calls == 1
        assert len(pages) == 1
        assert isinstance(pages[0], page_contract.ProviderCollectionPage)
        assert pages[0].provider_id == "fixture"
        assert pages[0].terminal
        assert pages[0].next_cursor == ""
        assert pages[0].query_fingerprint == page_contract.build_query_fingerprint(provider, query)
        assert tuple(item.external_id for item in pages[0].items) == ("one",)

    asyncio.run(scenario())


def test_query_fingerprint_excludes_navigation_and_secret_values() -> None:
    provider = _LegacyOnePageProvider()
    first = TenderSearchQuery(
        keywords=("camera",),
        page=1,
        extra={"category": "video", "api_key": "first-secret"},
    )
    navigated = TenderSearchQuery(
        keywords=("camera",),
        page=9,
        extra={"category": "video", "api_key": "second-secret"},
    )
    changed = TenderSearchQuery(
        keywords=("camera",),
        page=9,
        extra={"category": "network", "api_key": "second-secret"},
    )

    assert page_contract.build_query_fingerprint(
        provider, first
    ) == page_contract.build_query_fingerprint(provider, navigated)
    assert page_contract.build_query_fingerprint(
        provider, changed
    ) != page_contract.build_query_fingerprint(provider, navigated)
    assert "secret" not in page_contract.build_query_fingerprint(provider, first)


def test_engine_enforces_page_budget_without_requesting_unbounded_pages() -> None:
    class ManyPagesProvider(_LegacyOnePageProvider):
        def __init__(self) -> None:
            super().__init__()
            self.requested_pages = 0

        async def iter_search_pages(self, query, *, resume=None, cancellation_token=None):
            del query, resume
            for page_number in range(1, 6):
                self.requested_pages += 1
                if cancellation_token is not None:
                    cancellation_token.throw_if_cancelled()
                yield page_contract.ProviderCollectionPage(
                    provider_id=self.descriptor.id,
                    contract_version=self.contract_version,
                    parser_version=self.parser_version,
                    query_fingerprint="f" * 64,
                    page_identity=f"page-{page_number}",
                    page_number=page_number,
                    items=(
                        make_tender(
                            source=TenderSource.CUSTOM,
                            external_id=f"item-{page_number}",
                        ),
                    ),
                    next_cursor=f"cursor-{page_number + 1}",
                    terminal=False,
                    artifacts=(),
                )

    async def scenario() -> None:
        provider = ManyPagesProvider()
        result = await AsyncProviderSearchEngine(
            (provider,),
            max_pages_per_provider=2,
        ).search(TenderSearchQuery())

        assert result.outcomes[0].status is AsyncProviderSearchStatus.FAILED
        assert result.outcomes[0].error_code == "provider_page_budget_exceeded"
        assert tuple(item.external_id for item in result.raw_items) == ("item-1", "item-2")
        assert provider.requested_pages == 2

    asyncio.run(scenario())


def test_interactive_and_scheduled_run_budgets_are_separate_and_hard_bounded() -> None:
    assert CollectorRunBudget.interactive() == CollectorRunBudget(20, 10_000, 180.0)
    assert CollectorRunBudget.scheduled() == CollectorRunBudget(200, 100_000, 900.0)
    with pytest.raises(ValueError, match="between 1 and 200"):
        CollectorRunBudget(201, 100_000, 900.0)
    with pytest.raises(ValueError, match="between 1 and 100000"):
        CollectorRunBudget(200, 100_001, 900.0)
    with pytest.raises(ValueError, match="between 0 and 900"):
        CollectorRunBudget(200, 100_000, 901.0)

    class TwentyOnePageProvider(_LegacyOnePageProvider):
        async def iter_search_pages(self, query, *, resume=None, cancellation_token=None):
            del query, resume
            for page_number in range(1, 22):
                yield page_contract.ProviderCollectionPage(
                    provider_id=self.descriptor.id,
                    contract_version=self.contract_version,
                    parser_version=self.parser_version,
                    query_fingerprint="f" * 64,
                    page_identity=f"page-{page_number}",
                    page_number=page_number,
                    items=(),
                    next_cursor="" if page_number == 21 else f"cursor-{page_number + 1}",
                    terminal=page_number == 21,
                    artifacts=(),
                )

    async def scenario() -> None:
        interactive = await AsyncProviderSearchEngine((TwentyOnePageProvider(),)).search(
            TenderSearchQuery(),
            run_budget=CollectorRunBudget.interactive(),
        )
        scheduled = await AsyncProviderSearchEngine((TwentyOnePageProvider(),)).search(
            TenderSearchQuery(),
            run_budget=CollectorRunBudget.scheduled(),
        )
        assert interactive.outcomes[0].error_code == "provider_page_budget_exceeded"
        assert interactive.outcomes[0].page_count == 20
        assert scheduled.outcomes[0].status is AsyncProviderSearchStatus.EMPTY
        assert scheduled.outcomes[0].page_count == 21

    asyncio.run(scenario())


def test_engine_commits_each_page_before_requesting_the_next(tmp_path: Path) -> None:
    repository = CollectorStateRepository(tmp_path / "registry.sqlite3")
    run_id = repository.start_run(TenderSearchQuery(), provider_ids=("fixture",))

    class DurablePagesProvider(_LegacyOnePageProvider):
        async def iter_search_pages(self, query, *, resume=None, cancellation_token=None):
            del query, resume
            for page_number in (1, 2):
                if page_number == 2:
                    checkpoint = repository.get_checkpoint("fixture", scope_key="f" * 64)
                    assert checkpoint is not None
                    assert checkpoint.accepted_page_count == 1
                yield page_contract.ProviderCollectionPage(
                    provider_id="fixture",
                    contract_version=self.contract_version,
                    parser_version=self.parser_version,
                    query_fingerprint="f" * 64,
                    page_identity=f"page-{page_number}",
                    page_number=page_number,
                    items=(
                        make_tender(
                            source=TenderSource.CUSTOM,
                            external_id=f"durable-{page_number}",
                        ),
                    ),
                    next_cursor="page-2" if page_number == 1 else "",
                    terminal=page_number == 2,
                    artifacts=(),
                )

    async def scenario() -> None:
        result = await AsyncProviderSearchEngine(
            (DurablePagesProvider(),),
            accepted_page_repository=repository,
        ).search(TenderSearchQuery(), run_id=run_id)
        assert result.outcomes[0].status is AsyncProviderSearchStatus.SUCCESS
        assert result.outcomes[0].page_count == 2
        assert result.outcomes[0].artifact_count == 0

    asyncio.run(scenario())
    checkpoint = repository.get_checkpoint("fixture", scope_key="f" * 64)
    assert checkpoint is not None
    assert checkpoint.accepted_page_count == 2
    assert checkpoint.accepted_item_count == 2
    with repository._connect() as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM collector_accepted_pages WHERE run_id=?",
                (run_id,),
            ).fetchone()[0]
            == 2
        )


def test_engine_resume_preserves_cumulative_checkpoint_counters(tmp_path: Path) -> None:
    repository = CollectorStateRepository(tmp_path / "registry.sqlite3")
    query = TenderSearchQuery(keywords=("resume",))

    class ResumableProvider(_LegacyOnePageProvider):
        async def iter_search_pages(self, query, *, resume=None, cancellation_token=None):
            fingerprint = page_contract.build_query_fingerprint(self, query)
            page_number = 1 if resume is None else 2
            assert resume is None or resume.cursor == "page-2"
            yield page_contract.ProviderCollectionPage(
                provider_id="fixture",
                contract_version=self.contract_version,
                parser_version=self.parser_version,
                query_fingerprint=fingerprint,
                page_identity=f"page-{page_number}",
                page_number=page_number,
                items=(
                    make_tender(
                        source=TenderSource.CUSTOM,
                        external_id=f"resume-{page_number}",
                    ),
                ),
                next_cursor="page-2" if page_number == 1 else "",
                terminal=page_number == 2,
                artifacts=(),
            )
            if page_number == 1 and cancellation_token is not None:
                cancellation_token.cancel("resume fixture pause")
                cancellation_token.throw_if_cancelled()

    async def scenario() -> None:
        provider = ResumableProvider()
        first_run = repository.start_run(query, provider_ids=("fixture",))
        first = await AsyncProviderSearchEngine(
            (provider,), accepted_page_repository=repository
        ).search(query, run_id=first_run)
        assert first.cancelled or first.outcomes[0].status is AsyncProviderSearchStatus.CANCELLED

        second_run = repository.start_run(
            query,
            provider_ids=("fixture",),
            acquire_lease=False,
        )
        second = await AsyncProviderSearchEngine(
            (provider,), accepted_page_repository=repository
        ).search(query, run_id=second_run)
        assert second.outcomes[0].status is AsyncProviderSearchStatus.SUCCESS

    asyncio.run(scenario())
    fingerprint = page_contract.build_query_fingerprint(ResumableProvider(), query)
    checkpoint = repository.get_checkpoint("fixture", scope_key=fingerprint)
    assert checkpoint is not None
    assert checkpoint.accepted_page_count == 2
    assert checkpoint.accepted_item_count == 2
    assert checkpoint.last_accepted_page_id == "page-2"


def test_raw_artifact_store_deduplicates_content_and_sanitizes_url(tmp_path: Path) -> None:
    from app.tenders.collector.artifacts import RawArtifactStore

    store = RawArtifactStore(tmp_path / "artifacts")
    first = store.put(
        b'{"ok": true}',
        provider_id="fixture",
        request_method="GET",
        request_url="https://user:password@example.test/api?api_key=secret#fragment",
        status_code=200,
        media_type="application/json",
        encoding="utf-8",
        query_fingerprint="f" * 64,
        page_identity="page-1",
        contract_version="contract-v1",
        parser_version="parser-v1",
    )
    second = store.put(
        b'{"ok": true}',
        provider_id="fixture",
        request_method="GET",
        request_url="https://example.test/api?token=another-secret",
        status_code=200,
        media_type="application/json",
        encoding="utf-8",
        query_fingerprint="f" * 64,
        page_identity="page-2",
        contract_version="contract-v1",
        parser_version="parser-v1",
    )

    assert first.content_sha256 == second.content_sha256
    assert first.storage_path == second.storage_path
    assert Path(first.storage_path).read_bytes() == b'{"ok": true}'
    assert tuple(path for path in (tmp_path / "artifacts").rglob("*.artifact")) == (
        Path(first.storage_path),
    )
    assert first.request_url == "https://example.test/api"
    assert "secret" not in repr(first).casefold()
    assert "password" not in repr(first).casefold()


def _accepted_page(provider_id: str = "fixture") -> Any:
    return page_contract.ProviderCollectionPage(
        provider_id=provider_id,
        contract_version="contract-v1",
        parser_version="parser-v1",
        query_fingerprint="f" * 64,
        page_identity="page-1",
        page_number=1,
        items=(make_tender(source=TenderSource.CUSTOM, external_id="accepted"),),
        next_cursor="page-2",
        terminal=False,
        artifacts=(),
    )


def _accepted_checkpoint(provider_id: str = "fixture") -> CollectorCheckpoint:
    return CollectorCheckpoint(
        provider_id=provider_id,
        scope_key="f" * 64,
        cursor="page-2",
        contract_version="contract-v1",
        parser_version="parser-v1",
        query_fingerprint="f" * 64,
        last_accepted_page_id="page-1",
        accepted_page_count=1,
        accepted_item_count=1,
        replay_generation=0,
    )


def test_page_receipt_and_checkpoint_commit_atomically_and_replay_idempotently(
    tmp_path: Path,
) -> None:
    repository = CollectorStateRepository(tmp_path / "registry.sqlite3")
    run_id = repository.start_run(TenderSearchQuery(), provider_ids=("fixture",))
    page = _accepted_page()
    checkpoint = _accepted_checkpoint()

    first = repository.save_accepted_page(run_id, page, checkpoint=checkpoint)
    replay = repository.save_accepted_page(run_id, page, checkpoint=checkpoint)

    assert first == replay
    assert repository.get_checkpoint("fixture", scope_key="f" * 64) == first.checkpoint
    with repository._connect() as connection:
        receipt_count = connection.execute(
            "SELECT COUNT(*) FROM collector_accepted_pages WHERE run_id=?",
            (run_id,),
        ).fetchone()[0]
    assert receipt_count == 1


def test_page_commit_rolls_back_checkpoint_when_receipt_is_invalid(tmp_path: Path) -> None:
    repository = CollectorStateRepository(tmp_path / "registry.sqlite3")
    run_id = repository.start_run(TenderSearchQuery(), provider_ids=("fixture",))
    invalid_checkpoint = _accepted_checkpoint(provider_id="other")

    with pytest.raises(ValueError, match="provider identity"):
        repository.save_accepted_page(
            run_id,
            _accepted_page(),
            checkpoint=invalid_checkpoint,
        )

    assert repository.get_checkpoint("fixture", scope_key="f" * 64) is None
    with repository._connect() as connection:
        receipt_count = connection.execute(
            "SELECT COUNT(*) FROM collector_accepted_pages WHERE run_id=?",
            (run_id,),
        ).fetchone()[0]
    assert receipt_count == 0


def test_run_lease_is_released_only_by_terminal_completion(tmp_path: Path) -> None:
    repository = CollectorStateRepository(tmp_path / "registry.sqlite3")
    first = repository.start_run(TenderSearchQuery(), provider_ids=("fixture",))

    with pytest.raises(RuntimeError, match="collector run already active"):
        repository.start_run(TenderSearchQuery(), provider_ids=("fixture",))

    repository.complete_run(first, status=CollectionRunStatus.COMPLETED)
    second = repository.start_run(TenderSearchQuery(), provider_ids=("fixture",))
    assert second != first


def test_schema_14_to_15_backup_is_verified_and_current_is_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "registry.sqlite3"
    initialize_collector_database(database)
    assert COLLECTOR_SCHEMA_VERSION == 15
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE tender_registry_meta SET value='14' WHERE key='collector_schema_version'"
        )

    with sqlite3.connect(database) as connection:
        inventory = CollectorSchemaMigrator().inspect(connection)
        assert inventory.current_version == 14
        assert inventory.target_version == 15
        assert inventory.requires_migration
        assert inventory.requires_backup
        CollectorSchemaMigrator().migrate(connection)

    backups = tuple((tmp_path / "backups").glob("*.sqlite3"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as backup:
        assert backup.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        version = backup.execute(
            "SELECT value FROM tender_registry_meta WHERE key='collector_schema_version'"
        ).fetchone()[0]
    assert version == "14"

    restored = CollectorSchemaMigrator.restore_verified_backup(
        backups[0],
        tmp_path / "restored.sqlite3",
    )
    with sqlite3.connect(restored) as connection:
        restored_version = connection.execute(
            "SELECT value FROM tender_registry_meta WHERE key='collector_schema_version'"
        ).fetchone()[0]
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert restored_version == "14"

    with sqlite3.connect(database) as connection:
        CollectorSchemaMigrator().migrate(connection)
    assert tuple((tmp_path / "backups").glob("*.sqlite3")) == backups
