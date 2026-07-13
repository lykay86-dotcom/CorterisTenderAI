"""Операции обслуживания локальной базы данных."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, text

from .backup_manager import BackupManager, BackupRecord
from .diagnostics import DiagnosticsReport, DiagnosticsService


class DatabaseMaintenanceService:
    def __init__(self, engine: Engine, backup_manager: BackupManager) -> None:
        self.engine = engine
        self.backups = backup_manager

    def diagnostics(self) -> DiagnosticsReport:
        return DiagnosticsService(self.engine, self.backups).collect()

    def create_backup(self, reason: str = "manual") -> BackupRecord:
        self.engine.dispose()
        return self.backups.create(reason=reason)

    def restore(self, backup_path: Path) -> Path:
        self.engine.dispose()
        return self.backups.restore(backup_path)

    def optimize(self) -> None:
        if self.engine.dialect.name != "sqlite":
            return
        with self.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            connection.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
            connection.execute(text("PRAGMA optimize"))
            connection.execute(text("ANALYZE"))
            connection.execute(text("VACUUM"))

    def export_database(self, destination: Path) -> Path:
        self.engine.dispose()
        return self.backups.export_copy(destination)
