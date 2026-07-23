from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlalchemy import text

from app.database.backup_manager import BackupManager
from app.database.diagnostics import DiagnosticsService
from app.database.maintenance import DatabaseMaintenanceService
from app.database.migration import CURRENT_SCHEMA_VERSION
from app.database.seed import seed_default_data
from app.database.session import get_engine, init_database, reset_database_state


def _init(tmp_path: Path):
    reset_database_state()
    database = tmp_path / "reliable.db"
    backups = tmp_path / "backups"
    init_database(database, backup_dir=backups)
    return database, backups


def test_backup_metadata_rotation_and_verification(tmp_path):
    database, backups = _init(tmp_path)
    seed_default_data()
    manager = BackupManager(database, backups, keep_last=2)
    for i in range(3):
        manager.create(reason=f"test{i}")
    current = manager.list()
    assert len(current) == 2
    assert all(manager.verify(record.path) for record in current)
    assert all(item.path.with_suffix(".json").exists() for item in current)
    reset_database_state()


def test_restore_replaces_database_and_creates_safety_copy(tmp_path):
    database, backups = _init(tmp_path)
    manager = BackupManager(database, backups)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE restore_probe(value TEXT)")
        connection.execute("INSERT INTO restore_probe VALUES ('original')")
        connection.commit()
    backup = manager.create(reason="known_good")
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE restore_probe SET value='changed'")
        connection.commit()
    get_engine().dispose()
    manager.restore(backup.path)
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT value FROM restore_probe").fetchone()[0] == "original"
    assert any("before_restore" in item.path.name for item in manager.list())
    reset_database_state()


def test_diagnostics_are_healthy_and_include_counts(tmp_path):
    database, backups = _init(tmp_path)
    seed_default_data()
    manager = BackupManager(database, backups)
    manager.create(reason="diagnostic")
    report = DiagnosticsService(get_engine(), manager).collect()
    assert report.healthy
    assert report.schema_version == report.expected_schema_version == CURRENT_SCHEMA_VERSION
    assert report.table_count >= 7
    assert report.table_rows["companies"] == 1
    assert report.latest_backup_valid is True
    reset_database_state()


def test_maintenance_backup_export_and_optimize(tmp_path):
    database, backups = _init(tmp_path)
    service = DatabaseMaintenanceService(get_engine(), BackupManager(database, backups))
    record = service.create_backup("maintenance")
    assert record.path.exists()
    output = service.export_database(tmp_path / "export" / "copy.db")
    assert output.exists()
    service.optimize()
    assert service.diagnostics().integrity.lower() == "ok"
    reset_database_state()


def test_migration_history_is_written(tmp_path):
    database, _ = _init(tmp_path)
    with get_engine().connect() as connection:
        count = int(connection.scalar(text("SELECT COUNT(*) FROM migration_history")) or 0)
        status = connection.scalar(
            text("SELECT status FROM migration_history ORDER BY id DESC LIMIT 1")
        )
    assert count >= 1
    assert status == "success"
    reset_database_state()
