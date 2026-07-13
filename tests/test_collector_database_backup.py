"""Verified SQLite backup contract for collector migrations."""

from __future__ import annotations

import sqlite3

from scripts.backup_collector_database import backup_database


def test_backup_uses_sqlite_backup_and_passes_quick_check(tmp_path) -> None:
    source = tmp_path / "tender_registry.sqlite3"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE sample(id INTEGER PRIMARY KEY, value TEXT)")
        connection.execute("INSERT INTO sample(value) VALUES ('saved')")

    backup = backup_database(source, tmp_path / "backup")

    assert backup is not None
    with sqlite3.connect(backup) as connection:
        assert connection.execute("SELECT value FROM sample").fetchone()[0] == "saved"
        assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"


def test_missing_database_is_a_safe_noop(tmp_path) -> None:
    assert (
        backup_database(
            tmp_path / "missing.sqlite3",
            tmp_path / "backup",
        )
        is None
    )
