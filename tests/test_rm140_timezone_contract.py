"""Expected RM-140 aware-time and legacy-unknown contract."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.tenders.collector.models import CollectionRunStatus
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.provider_base import TenderSearchQuery
from app.tenders.tender_registry import _iso_timestamp


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
