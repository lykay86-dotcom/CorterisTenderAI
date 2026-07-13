"""Integration tests for collector SQLite migration and persistence."""

from __future__ import annotations

import sqlite3

from app.tenders.collector.checkpoint import CollectorCheckpoint
from app.tenders.collector.deduplicator import TenderDeduplicator
from app.tenders.collector.models import CollectionRunStatus
from app.tenders.collector.schema import COLLECTOR_SCHEMA_VERSION
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.provider_base import TenderSearchQuery
from app.tenders.tender_registry import TenderRegistryRepository
from tests.collector_c3_helpers import make_document, make_tender


def _run_and_save(repository, tender, run_id: str):
    repository.start_run(
        TenderSearchQuery(keywords=("видеонаблюдение",)),
        provider_ids=("eis",),
        run_id=run_id,
        started_at="2026-07-12T10:00:00+00:00",
    )
    result = TenderDeduplicator().deduplicate((tender,))
    summary = repository.save_batch(
        run_id,
        result,
        observed_at="2026-07-12T10:01:00+00:00",
    )
    repository.complete_run(
        run_id,
        status=CollectionRunStatus.COMPLETED,
        completed_at="2026-07-12T10:02:00+00:00",
        elapsed_ms=1200,
    )
    return result, summary


def test_schema_migration_is_idempotent(tmp_path) -> None:
    path = tmp_path / "tender_registry.sqlite3"
    repository = CollectorStateRepository(path)

    repository.initialize()
    repository.initialize()

    with sqlite3.connect(path) as connection:
        version = connection.execute(
            """
            SELECT value FROM tender_registry_meta
            WHERE key = 'collector_schema_version'
            """
        ).fetchone()[0]
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert int(version) == COLLECTOR_SCHEMA_VERSION
    assert {
        "collector_runs",
        "collector_tender_aliases",
        "collector_tender_sources",
        "collector_tender_versions",
        "collector_tender_changes",
        "collector_checkpoints",
    } <= tables


def test_new_unchanged_and_changed_observations_are_recorded(
    tmp_path,
) -> None:
    path = tmp_path / "tender_registry.sqlite3"
    repository = CollectorStateRepository(path)
    first = make_tender(documents=(make_document("tz"),))

    _, saved_first = _run_and_save(repository, first, "run-1")
    _, saved_second = _run_and_save(repository, first, "run-2")
    changed = make_tender(
        amount="1750000.00",
        deadline_day=25,
        documents=(
            make_document("tz"),
            make_document("contract", name="Контракт.pdf"),
        ),
    )
    dedupe, saved_third = _run_and_save(
        repository,
        changed,
        "run-3",
    )

    assert saved_first.new_count == 1
    assert saved_second.unchanged_count == 1
    assert saved_third.changed_count == 1
    assert saved_third.change_count >= 3
    registry_key = dedupe.items[0].canonical_key
    changes = repository.list_changes(registry_key)
    assert any(change.field_name == "price" for change in changes)
    assert len(repository.list_sources(registry_key)) == 1

    registry = TenderRegistryRepository(path)
    record = registry.get_record(registry_key)
    assert record is not None
    assert str(record.price_amount) == "1750000.00"
    assert record.seen_count == 3


def test_collector_updates_preserve_user_registry_state(tmp_path) -> None:
    path = tmp_path / "tender_registry.sqlite3"
    repository = CollectorStateRepository(path)
    dedupe, _ = _run_and_save(repository, make_tender(), "run-1")
    key = dedupe.items[0].canonical_key

    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            UPDATE tender_records
            SET archived=1,
                last_relevance_score=88,
                last_relevance_grade='recommended',
                last_accepted=1
            WHERE registry_key=?
            """,
            (key,),
        )
        connection.commit()

    _run_and_save(
        repository,
        make_tender(amount="1600000.00"),
        "run-2",
    )
    record = TenderRegistryRepository(path).get_record(key)

    assert record is not None
    assert record.archived
    assert record.relevance_score == 88
    assert record.last_accepted


def test_checkpoint_roundtrip(tmp_path) -> None:
    repository = CollectorStateRepository(tmp_path / "tender_registry.sqlite3")

    stored = repository.save_checkpoint(
        CollectorCheckpoint(
            provider_id="EIS",
            scope_key="daily",
            cursor="page:7",
            watermark="2026-07-12T10:00:00+00:00",
            state={"last_number": "0373"},
        ),
        updated_at="2026-07-12T11:00:00+00:00",
    )
    loaded = repository.get_checkpoint("eis", scope_key="daily")

    assert loaded == stored
    assert loaded.state["last_number"] == "0373"


def test_collector_reuses_legacy_registry_key_for_short_number(
    tmp_path,
) -> None:
    path = tmp_path / "tender_registry.sqlite3"
    repository = CollectorStateRepository(path)
    repository.initialize()
    tender = make_tender(
        external_id="mos-ext-1",
        procurement_number="mos-77",
    )

    from app.tenders.collector.codec import stable_json, tender_to_payload

    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            INSERT INTO tender_records(
                registry_key, procurement_number, identity_key, source,
                external_id, title, customer_name, customer_inn,
                status, procedure_type, source_url, payload_json,
                first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "procurement:mos-77",
                tender.procurement_number,
                tender.identity_key,
                tender.source.value,
                tender.external_id,
                tender.title,
                tender.customer.name,
                tender.customer.inn,
                tender.status.value,
                tender.procedure_type.value,
                tender.source_url,
                stable_json(tender_to_payload(tender)),
                "2026-07-10T10:00:00+00:00",
                "2026-07-10T10:00:00+00:00",
            ),
        )
        connection.commit()

    _, summary = _run_and_save(repository, tender, "legacy-run")

    assert summary.new_count == 0
    assert summary.unchanged_count == 1
    with sqlite3.connect(path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM tender_records").fetchone()[0]
        alias_key = connection.execute(
            """
            SELECT registry_key FROM collector_tender_aliases
            WHERE alias_key = ?
            """,
            ("source:eis:mos-ext-1",),
        ).fetchone()[0]
    assert count == 1
    assert alias_key == "procurement:mos-77"
