from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from app.tenders.collector.schema import (
    COLLECTOR_SCHEMA_VERSION,
    CollectorSchemaMigrator,
)
from app.tenders.collector_database import initialize_collector_database


def test_newer_collector_schema_is_never_downgraded(tmp_path) -> None:
    database = tmp_path / "registry.sqlite3"
    initialize_collector_database(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE tender_registry_meta SET value=? WHERE key='collector_schema_version'",
            (str(COLLECTOR_SCHEMA_VERSION + 1),),
        )

    with sqlite3.connect(database) as connection, pytest.raises(
        RuntimeError,
        match="newer",
    ):
        CollectorSchemaMigrator().migrate(connection)

    with sqlite3.connect(database) as connection:
        version = connection.execute(
            "SELECT value FROM tender_registry_meta WHERE key='collector_schema_version'"
        ).fetchone()[0]
    assert int(version) == COLLECTOR_SCHEMA_VERSION + 1


def test_specialized_repositories_do_not_own_collector_ddl() -> None:
    root = Path(__file__).resolve().parents[1]
    repository_files = (
        root / "app/tenders/collector/aggregator_discovery.py",
        root / "app/tenders/collector/vertical_source_verification.py",
        root / "app/tenders/matching_catalog.py",
        root / "app/tenders/commercial_estimator.py",
    )

    for path in repository_files:
        assert "CREATE TABLE IF NOT EXISTS collector_" not in path.read_text(
            encoding="utf-8"
        )
