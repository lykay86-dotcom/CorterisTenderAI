"""RM-140 characterization of search ownership before stabilization."""

from __future__ import annotations

import asyncio
from contextlib import closing
from datetime import datetime
import inspect
import socket
import sqlite3
from threading import Event

from app.tenders import TenderSearchEngine
from app.tenders.collector.async_engine import (
    AsyncProviderSearchEngine,
    AsyncProviderSearchStatus,
)
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.models import TenderSource
from app.tenders.provider_base import TenderSearchQuery
from app.tenders.provider_registry import TenderProviderRegistry
from app.tenders.search_runtime import create_tender_search_runtime
from app.tenders.tender_registry import TenderRegistryRepository
from app.ui.modern_main_window import ModernMainWindow
from app.ui.tender_search_ui_controller import TenderSearchUiController
from tests.tender_search_helpers import FakeProvider, descriptor
from tests.test_collector_async_engine import FakeProvider as AsyncFakeProvider


class _BlockingProvider(FakeProvider):
    def __init__(self) -> None:
        super().__init__(
            descriptor=descriptor("blocking", TenderSource.CUSTOM, priority=10)
        )
        self.entered = Event()
        self.release = Event()
        self.finished = Event()

    def search(self, query):
        self.entered.set()
        try:
            self.release.wait(timeout=2)
            return super().search(query)
        finally:
            self.finished.set()


def test_public_sync_api_and_deterministic_selection_are_compatible() -> None:
    assert TenderSearchEngine.__module__ == "app.tenders.search_engine"
    assert tuple(inspect.signature(TenderSearchEngine).parameters) == (
        "registry",
        "max_workers",
        "timeout_seconds",
        "normalizer",
    )
    providers = (
        FakeProvider(descriptor("third", TenderSource.CUSTOM, priority=30)),
        FakeProvider(descriptor("first", TenderSource.EIS, priority=10)),
        FakeProvider(descriptor("second", TenderSource.RTS_TENDER, priority=20)),
    )

    result = TenderSearchEngine(TenderProviderRegistry(providers)).search(
        TenderSearchQuery(),
        parallel=False,
    )

    assert tuple(item.provider_id for item in result.outcomes) == (
        "first",
        "second",
        "third",
    )


def test_sync_timeout_returns_while_started_provider_may_still_finish() -> None:
    provider = _BlockingProvider()
    engine = TenderSearchEngine(
        TenderProviderRegistry((provider,)),
        timeout_seconds=0.02,
    )
    try:
        result = engine.search(TenderSearchQuery(), parallel=True)

        assert provider.entered.is_set()
        assert result.outcomes[0].status.value == "timed_out"
        assert not provider.finished.is_set()
    finally:
        provider.release.set()
        assert provider.finished.wait(timeout=1)


def test_baseline_composition_is_offline_but_builds_both_search_owners(
    tmp_path,
    monkeypatch,
) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("network is forbidden during composition")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)

    runtime = create_tender_search_runtime(tmp_path)

    assert runtime.engine is not None
    assert runtime.runner.search_service is runtime.search_service
    controller_source = inspect.getsource(TenderSearchUiController)
    assert "self.runtime.runner" in controller_source
    assert "self.collector_session" in controller_source


def test_current_manual_and_scheduled_runs_share_collector_admission() -> None:
    controller_source = inspect.getsource(TenderSearchUiController)

    assert "def try_start_collector" in controller_source
    assert "def _try_start_collector_query" in controller_source
    assert "self._collector_worker is not None" in controller_source
    assert "start_collector=self.try_start_collector" in controller_source


def test_current_shell_close_sequence_names_only_dashboard_owner() -> None:
    source = inspect.getsource(ModernMainWindow.closeEvent)

    assert "dashboard_controller.shutdown" in source
    assert "tender_search" not in source


def test_current_history_schemas_keep_distinct_run_families_and_links(tmp_path) -> None:
    path = tmp_path / "tender_registry.sqlite3"
    TenderRegistryRepository(path).initialize()
    CollectorStateRepository(path).initialize()

    with closing(sqlite3.connect(path)) as connection:
        collector_version = connection.execute(
            "SELECT value FROM tender_registry_meta "
            "WHERE key='collector_schema_version'"
        ).fetchone()[0]
        registry_version = connection.execute(
            "SELECT value FROM tender_registry_meta WHERE key='schema_version'"
        ).fetchone()[0]
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        legacy_fks = {
            (str(row[2]), str(row[3]), str(row[4]))
            for row in connection.execute("PRAGMA foreign_key_list(tender_search_run_items)")
        }
        collector_fks = {
            (str(row[2]), str(row[3]), str(row[4]))
            for row in connection.execute("PRAGMA foreign_key_list(collector_run_items)")
        }

    assert registry_version == "1"
    assert collector_version == "14"
    assert {"tender_search_runs", "collector_runs"} <= tables
    assert ("tender_search_runs", "run_id", "run_id") in legacy_fks
    assert ("tender_records", "registry_key", "registry_key") in legacy_fks
    assert ("collector_runs", "run_id", "run_id") in collector_fks
    assert ("tender_records", "registry_key", "registry_key") in collector_fks


def test_async_owner_publishes_aware_time_and_safe_unknown_failure() -> None:
    async def scenario() -> None:
        result = await AsyncProviderSearchEngine(
            (AsyncFakeProvider("unsafe", "fail"),)
        ).search(TenderSearchQuery())

        assert datetime.fromisoformat(result.started_at).utcoffset() is not None
        assert datetime.fromisoformat(result.completed_at).utcoffset() is not None
        outcome = result.outcomes[0]
        assert outcome.status is AsyncProviderSearchStatus.FAILED
        assert outcome.error_code == "provider_internal_error"
        assert outcome.error_message == (
            "Источник завершил поиск с безопасно скрытой ошибкой."
        )
        assert "provider failed" not in outcome.error_message

    asyncio.run(scenario())
