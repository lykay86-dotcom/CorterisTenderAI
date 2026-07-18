"""Expected RM-140 aware-time and legacy-unknown contract."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from app.tenders.collector.async_engine import AsyncProviderSearchEngine
from app.tenders.collector.models import CollectionRunStatus
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.provider_base import TenderSearchQuery
from app.tenders.tender_registry import _iso_timestamp, legacy_timestamp_status


def test_collector_history_rejects_naive_started_at(tmp_path) -> None:
    repository = CollectorStateRepository(tmp_path / "registry.sqlite3")

    with pytest.raises(ValueError, match="timezone-aware"):
        repository.start_run(
            TenderSearchQuery(),
            started_at="2026-07-18T12:00:00",
        )


def test_collector_history_rejects_naive_completed_at(tmp_path) -> None:
    repository = CollectorStateRepository(tmp_path / "registry.sqlite3")
    run_id = repository.start_run(
        TenderSearchQuery(),
        started_at="2026-07-18T09:00:00+00:00",
    )

    with pytest.raises(ValueError, match="timezone-aware"):
        repository.complete_run(
            run_id,
            status=CollectionRunStatus.COMPLETED,
            completed_at="2026-07-18T12:00:00",
        )


def test_legacy_writer_does_not_silently_declare_naive_datetime_utc() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _iso_timestamp(datetime(2026, 7, 18, 12, 0))

    assert _iso_timestamp(datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)).endswith("+00:00")


def test_legacy_reader_classifies_naive_time_as_unknown_without_guessing() -> None:
    assert legacy_timestamp_status("2026-07-18T12:00:00") == "unknown"
    assert legacy_timestamp_status("2026-07-18T12:00:00+03:00") == "explicit"
    assert legacy_timestamp_status("not-a-time") == "invalid"


def test_elapsed_uses_injected_monotonic_clock_and_never_becomes_negative() -> None:
    values = iter((100.0, 90.0))
    engine = AsyncProviderSearchEngine(
        (),
        monotonic_clock=lambda: next(values),
        utcnow=lambda: datetime(2026, 7, 18, 12, tzinfo=timezone.utc),
    )

    result = asyncio.run(engine.search(TenderSearchQuery()))

    assert result.elapsed_ms == 0
    assert result.started_at == "2026-07-18T12:00:00+00:00"
    assert result.completed_at == "2026-07-18T12:00:00+00:00"


def test_injected_wall_clock_must_be_timezone_aware() -> None:
    engine = AsyncProviderSearchEngine(
        (),
        utcnow=lambda: datetime(2026, 7, 18, 12),
    )

    with pytest.raises(ValueError, match="timezone-aware"):
        asyncio.run(engine.search(TenderSearchQuery()))
