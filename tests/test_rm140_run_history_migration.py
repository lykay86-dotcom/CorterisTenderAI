"""RM-140 no-migration and single production history-writer contract."""

from __future__ import annotations

import asyncio
from contextlib import closing
from hashlib import sha256
import json
import sqlite3

from app.tenders.collector.collector_service import CollectorService
from app.tenders.collector.schema import COLLECTOR_SCHEMA_VERSION
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.provider_base import TenderSearchQuery
from app.tenders.tender_registry import TenderRegistryRepository
from tests.test_collector_service import FakeEngine, _batch
from tests.test_tender_registry import _evaluated_tender, _run


def _digest(connection: sqlite3.Connection, table: str) -> str:
    rows = connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def test_initialization_preserves_legacy_rows_links_and_unknown_timestamp(tmp_path) -> None:
    path = tmp_path / "tender_registry.sqlite3"
    legacy = TenderRegistryRepository(path)
    legacy.record_profile_run(_run(_evaluated_tender()), run_id="legacy-run")

    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(
            "UPDATE tender_search_runs SET executed_at=? WHERE run_id=?",
            ("2026-07-18T12:00:00", "legacy-run"),
        )
        before = {
            table: (
                connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],
                _digest(connection, table),
            )
            for table in (
                "tender_records",
                "tender_search_runs",
                "tender_search_run_items",
            )
        }

    CollectorStateRepository(path).initialize()
    legacy.initialize()

    with closing(sqlite3.connect(path)) as connection:
        after = {
            table: (
                connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],
                _digest(connection, table),
            )
            for table in (
                "tender_records",
                "tender_search_runs",
                "tender_search_run_items",
            )
        }
        versions = dict(
            connection.execute(
                "SELECT key, value FROM tender_registry_meta "
                "WHERE key IN ('schema_version', 'collector_schema_version')"
            )
        )

    assert after == before
    assert versions == {
        "schema_version": str(TenderRegistryRepository.SCHEMA_VERSION),
        "collector_schema_version": str(COLLECTOR_SCHEMA_VERSION),
    }
    assert legacy.run_item_count("legacy-run") == 1
    assert legacy.list_search_runs()[0].timezone_status == "unknown"
    assert not tuple(tmp_path.glob("*.bak*"))


def test_saved_profile_context_is_written_only_to_collector_history(tmp_path) -> None:
    path = tmp_path / "tender_registry.sqlite3"
    repository = CollectorStateRepository(path)
    query = TenderSearchQuery(
        keywords=("СКУД",),
        extra={
            "corteris_run_context": {
                "schema_version": 1,
                "origin": "saved_profile",
                "profile_id": "all-corteris",
                "profile_name": "Все тендеры КОРТЕРИС",
            }
        },
    )

    result = asyncio.run(
        CollectorService(FakeEngine(_batch()), repository).collect(
            query,
            provider_ids=("eis", "mirror"),
        )
    )

    with closing(sqlite3.connect(path)) as connection:
        collector_rows = connection.execute(
            "SELECT run_id, query_json FROM collector_runs"
        ).fetchall()
        legacy_count = connection.execute("SELECT COUNT(*) FROM tender_search_runs").fetchone()[0]

    assert collector_rows[0][0] == result.run_id
    assert json.loads(collector_rows[0][1])["extra"]["corteris_run_context"] == {
        "schema_version": 1,
        "origin": "saved_profile",
        "profile_id": "all-corteris",
        "profile_name": "Все тендеры КОРТЕРИС",
    }
    assert legacy_count == 0
