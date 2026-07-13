"""SQLite persistence tests for collector freshness state."""

from __future__ import annotations

import sqlite3

from app.tenders.collector.deduplicator import TenderDeduplicator
from app.tenders.collector.freshness import TenderFreshnessService
from app.tenders.collector.schema import COLLECTOR_SCHEMA_VERSION
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.collector.verification import TenderVerificationService
from app.tenders.provider_base import TenderSearchQuery
from tests.collector_c3_helpers import make_tender


def _save(
    repository,
    *,
    deadline_day: int,
    run_id: str,
    now: str,
    procurement_number: str = "0373100000126000001",
):
    repository.start_run(TenderSearchQuery(), run_id=run_id)
    verification = TenderVerificationService().verify(
        TenderDeduplicator().deduplicate(
            (
                make_tender(
                    deadline_day=deadline_day,
                    procurement_number=procurement_number,
                    external_id=run_id,
                ),
            )
        ),
        observed_at=now,
    )
    freshness = TenderFreshnessService(
        user_timezone="UTC"
    ).evaluate(verification, now=now)
    summary = repository.save_batch(
        run_id,
        verification.deduplication,
        verification=verification,
        freshness=freshness,
    )
    return verification, freshness, summary


def test_current_schema_contains_freshness_state(tmp_path) -> None:
    path = tmp_path / "tender_registry.sqlite3"
    repository = CollectorStateRepository(path)
    repository.initialize()
    repository.initialize()

    with sqlite3.connect(path) as connection:
        version = int(
            connection.execute(
                """
                SELECT value FROM tender_registry_meta
                WHERE key='collector_schema_version'
                """
            ).fetchone()[0]
        )
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }

    assert version == COLLECTOR_SCHEMA_VERSION == 12
    assert "collector_tender_freshness_state" in tables
    assert "collector_participation_decisions" in tables


def test_freshness_state_is_persisted_and_loaded(tmp_path) -> None:
    repository = CollectorStateRepository(
        tmp_path / "tender_registry.sqlite3"
    )
    verification, freshness, summary = _save(
        repository,
        deadline_day=14,
        run_id="fresh-1",
        now="2026-07-12T13:00:00+00:00",
    )
    key = verification.deduplication.items[0].canonical_key

    loaded = repository.get_freshness_state(
        key,
        now="2026-07-12T13:00:00+00:00",
    )
    listed = repository.list_freshness_states(
        (key,),
        now="2026-07-12T13:00:00+00:00",
    )

    assert loaded is not None
    assert loaded.deadline_utc == "2026-07-14T12:00:00+00:00"
    assert loaded.verification_due_at == "2026-07-12T16:00:00+00:00"
    assert loaded == listed[key]
    assert summary.due_soon_count == freshness.due_soon_count == 1
    assert summary.reverification_due_count == 0

    stale = repository.get_freshness_state(
        key,
        now="2026-07-12T16:01:00+00:00",
    )
    assert stale is not None
    assert stale.is_stale
    assert stale.status.value == "stale"


def test_due_reverification_excludes_expired_tenders(tmp_path) -> None:
    repository = CollectorStateRepository(
        tmp_path / "tender_registry.sqlite3"
    )
    _, _, _ = _save(
        repository,
        deadline_day=14,
        run_id="fresh-1",
        now="2026-07-12T13:00:00+00:00",
        procurement_number="0373100000126000001",
    )
    _, _, _ = _save(
        repository,
        deadline_day=11,
        run_id="fresh-2",
        now="2026-07-12T13:00:00+00:00",
        procurement_number="0373100000126000002",
    )

    due = repository.list_due_reverification(
        now="2026-07-12T16:01:00+00:00"
    )

    assert len(due) == 1
    assert not due[0].deadline_expired
