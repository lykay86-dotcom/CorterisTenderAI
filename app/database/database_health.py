"""Диагностика и обслуживание локальной SQLite-базы."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Engine, text

from .schema_inspector import SchemaInspector


@dataclass(frozen=True, slots=True)
class DatabaseHealthReport:
    integrity: str
    journal_mode: str
    foreign_keys: bool
    table_count: int
    database_size: int

    @property
    def healthy(self) -> bool:
        return self.integrity.lower() == "ok" and self.foreign_keys


class DatabaseHealthService:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def check(self) -> DatabaseHealthReport:
        with self.engine.connect() as connection:
            integrity = str(connection.scalar(text("PRAGMA integrity_check")) or "unknown")
            journal_mode = str(connection.scalar(text("PRAGMA journal_mode")) or "unknown")
            foreign_keys = int(connection.scalar(text("PRAGMA foreign_keys")) or 0) == 1
        database = self.engine.url.database
        size = Path(database).stat().st_size if database and Path(database).exists() else 0
        return DatabaseHealthReport(
            integrity=integrity,
            journal_mode=journal_mode,
            foreign_keys=foreign_keys,
            table_count=len(SchemaInspector(self.engine).table_names()),
            database_size=size,
        )

    def optimize(self) -> None:
        if not self.engine.dialect.name.startswith("sqlite"):
            return
        with self.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            connection.execute(text("PRAGMA optimize"))
            connection.execute(text("ANALYZE"))
            connection.execute(text("VACUUM"))
