"""Expected RM-140 safe typed error boundary."""

from __future__ import annotations

import asyncio
from contextlib import closing
from dataclasses import replace
import sqlite3

from app.tenders.collector.async_engine import AsyncProviderSearchEngine
from app.tenders.collector.health_monitor import ProviderHealthMonitor
from app.tenders.collector.models import CollectionRunStatus
from app.tenders.collector.progress import (
    CollectorProgressEvent,
    CollectorProgressPhase,
    emit_collector_progress,
)
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.provider_base import TenderSearchQuery, TenderSearchResult
from tests.test_collector_async_engine import FakeProvider


SECRET = "RM140_SECRET_SENTINEL"
UNSAFE_URL = (
    "https://user:RM140_SECRET_SENTINEL@example.test/path?token=RM140_SECRET_SENTINEL#private"
)


class RM140_SECRET_SENTINEL(RuntimeError):
    pass


def _unsafe_error() -> BaseException:
    try:
        raise ValueError(f"nested {SECRET} {UNSAFE_URL}")
    except ValueError as cause:
        error = RM140_SECRET_SENTINEL(f"body={SECRET}; url={UNSAFE_URL}")
        error.__cause__ = cause
        return error


def test_health_monitor_discards_unknown_exception_type_text_and_nested_secret() -> None:
    snapshot = ProviderHealthMonitor().register_failure("unsafe", _unsafe_error())
    rendered = repr(snapshot)

    assert SECRET not in rendered
    assert "example.test" not in rendered
    assert snapshot.last_error_type == "provider_internal_error"
    assert snapshot.last_error_message == ("Источник завершил поиск с безопасно скрытой ошибкой.")


def test_async_outcome_uses_stable_code_in_compatibility_error_type() -> None:
    async def scenario():
        return await AsyncProviderSearchEngine((FakeProvider("unsafe", "fail"),)).search(
            TenderSearchQuery()
        )

    outcome = asyncio.run(scenario()).outcomes[0]

    assert outcome.error_type == outcome.error_code == "provider_internal_error"
    assert len(outcome.error_message) <= 300


def test_provider_metadata_and_warnings_are_sanitized_before_public_batch() -> None:
    class UnsafeMetadataProvider(FakeProvider):
        def __init__(self) -> None:
            super().__init__("unsafe-metadata", "success")
            self.descriptor = replace(self.descriptor, display_name=UNSAFE_URL)

        async def search(self, query, *, cancellation_token=None):
            result = await super().search(query, cancellation_token=cancellation_token)
            return TenderSearchResult(
                provider_id=result.provider_id,
                items=result.items,
                warnings=(f"Authorization: Bearer {SECRET}; {UNSAFE_URL}",),
            )

    result = asyncio.run(
        AsyncProviderSearchEngine((UnsafeMetadataProvider(),)).search(TenderSearchQuery())
    )

    rendered = repr(result)
    assert SECRET not in rendered
    assert "example.test" not in rendered
    assert result.outcomes[0].display_name == "UNSAFE-METADATA"
    assert result.results[0].warnings == ("Предупреждение источника безопасно скрыто.",)


def test_progress_callback_exception_does_not_reach_log(caplog) -> None:
    async def callback(event: CollectorProgressEvent) -> None:
        del event
        raise RM140_SECRET_SENTINEL(f"{SECRET}: {UNSAFE_URL}")

    asyncio.run(
        emit_collector_progress(
            callback,
            CollectorProgressEvent(phase=CollectorProgressPhase.PROVIDER_RUNNING),
        )
    )

    assert SECRET not in caplog.text
    assert "example.test" not in caplog.text


def test_unknown_error_sentinel_never_reaches_collector_history(tmp_path) -> None:
    monitor = ProviderHealthMonitor()
    monitor.register_failure("unsafe", _unsafe_error())
    repository = CollectorStateRepository(tmp_path / "registry.sqlite3")
    run_id = repository.start_run(TenderSearchQuery(), provider_ids=("unsafe",))
    snapshot = monitor.snapshot("unsafe")

    class Outcome:
        provider_id = "unsafe"
        display_name = "Unsafe"
        status = "failed"
        item_count = 0
        elapsed_ms = 1
        warnings = ()
        successful = False
        error_code = snapshot.last_error_type
        error_message = snapshot.last_error_message

    repository.complete_run(
        run_id,
        status=CollectionRunStatus.FAILED,
        provider_outcomes=(Outcome(),),
        error_code=snapshot.last_error_type,
        error_message=snapshot.last_error_message,
    )

    with closing(sqlite3.connect(repository.path)) as connection:
        rendered = "\n".join(
            str(value)
            for table in ("collector_runs", "collector_run_providers")
            for row in connection.execute(f"SELECT * FROM {table}")
            for value in row
        )
    assert SECRET not in rendered
    assert "example.test" not in rendered
