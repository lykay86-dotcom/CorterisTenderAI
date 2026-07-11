from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from app.tenders.collector.eis_checkpoint import (
    EisCheckpointCoordinator,
    EisCheckpointPolicy,
)
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.provider_base import TenderSearchQuery, TenderSearchResult


def _repository(tmp_path: Path) -> CollectorStateRepository:
    repository = CollectorStateRepository(
        tmp_path / "tender_registry.sqlite3"
    )
    repository.initialize()
    return repository


def test_checkpoint_applies_sliding_window(tmp_path) -> None:
    repository = _repository(tmp_path)
    coordinator = EisCheckpointCoordinator(
        repository,
        policy=EisCheckpointPolicy(overlap_days=7),
    )
    query = TenderSearchQuery(
        keywords=("СКУД",),
        laws=("44-ФЗ",),
    )
    prepared = coordinator.prepare(query)
    coordinator.mark_success(
        prepared,
        TenderSearchResult(provider_id="eis", items=()),
        completed_at=datetime(
            2026,
            7,
            12,
            12,
            0,
            tzinfo=timezone.utc,
        ),
    )

    second = coordinator.prepare(query)

    assert second.incremental_applied
    assert second.query.date_from is not None
    assert second.query.date_from.isoformat() == "2026-07-05"
    assert second.checkpoint is not None
    assert any("скользящее окно" in item for item in second.warnings)


def test_explicit_date_from_is_not_overridden(tmp_path) -> None:
    from datetime import date

    repository = _repository(tmp_path)
    coordinator = EisCheckpointCoordinator(repository)
    base = TenderSearchQuery(keywords=("ОПС",))
    first = coordinator.prepare(base)
    coordinator.mark_success(
        first,
        TenderSearchResult(provider_id="eis", items=()),
        completed_at=datetime(
            2026,
            7,
            12,
            tzinfo=timezone.utc,
        ),
    )

    explicit = TenderSearchQuery(
        keywords=("ОПС",),
        date_from=date(2026, 1, 1),
    )
    prepared = coordinator.prepare(explicit)

    assert not prepared.incremental_applied
    assert prepared.query.date_from == date(2026, 1, 1)


def test_checkpoint_scope_ignores_page_and_date_range() -> None:
    from datetime import date

    first = TenderSearchQuery(
        keywords=("камеры",),
        page=1,
        page_size=10,
        date_from=date(2026, 7, 1),
    )
    second = TenderSearchQuery(
        keywords=("камеры",),
        page=7,
        page_size=100,
        date_from=date(2026, 7, 10),
    )

    assert EisCheckpointCoordinator.scope_key(first) == (
        EisCheckpointCoordinator.scope_key(second)
    )
