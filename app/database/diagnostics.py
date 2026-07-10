"""Сводная диагностика базы данных для интерфейса и техподдержки."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, text

from .backup_manager import BackupManager
from .migration import CURRENT_SCHEMA_VERSION
from .schema_inspector import SchemaInspector


@dataclass(frozen=True, slots=True)
class DiagnosticsReport:
    healthy: bool
    integrity: str
    journal_mode: str
    foreign_keys: bool
    schema_version: int
    expected_schema_version: int
    database_path: str
    database_size: int
    table_count: int
    index_count: int
    total_rows: int
    table_rows: dict[str, int] = field(default_factory=dict)
    latest_backup: str | None = None
    latest_backup_valid: bool | None = None
    issues: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class DiagnosticsService:
    def __init__(self, engine: Engine, backup_manager: BackupManager | None = None) -> None:
        self.engine = engine
        self.backup_manager = backup_manager

    def collect(self) -> DiagnosticsReport:
        inspector = SchemaInspector(self.engine)
        tables = sorted(inspector.table_names())
        table_rows: dict[str, int] = {}
        index_count = 0
        issues: list[str] = []

        for table in tables:
            try:
                table_rows[table] = inspector.row_count(table)
                index_count += len(inspector.index_names(table))
            except Exception as exc:
                issues.append(f"Не удалось прочитать таблицу {table}: {exc}")

        with self.engine.connect() as connection:
            integrity = str(connection.scalar(text("PRAGMA integrity_check")) or "unknown")
            journal_mode = str(connection.scalar(text("PRAGMA journal_mode")) or "unknown")
            foreign_keys = int(connection.scalar(text("PRAGMA foreign_keys")) or 0) == 1
            schema_version = 0
            if "schema_version" in tables:
                schema_version = int(connection.scalar(text("SELECT version FROM schema_version WHERE id=1")) or 0)

        if integrity.lower() != "ok":
            issues.append(f"Нарушение целостности SQLite: {integrity}")
        if not foreign_keys:
            issues.append("Контроль внешних ключей отключён")
        if journal_mode.lower() != "wal":
            issues.append(f"Режим журнала отличается от WAL: {journal_mode}")
        if schema_version != CURRENT_SCHEMA_VERSION:
            issues.append(
                f"Версия схемы {schema_version}, ожидается {CURRENT_SCHEMA_VERSION}"
            )

        database = self.engine.url.database
        database_path = Path(database).resolve() if database else Path()
        latest_backup: str | None = None
        latest_backup_valid: bool | None = None
        if self.backup_manager:
            records = self.backup_manager.list()
            if records:
                latest_backup = str(records[0].path)
                latest_backup_valid = self.backup_manager.verify(records[0].path)
                if not latest_backup_valid:
                    issues.append("Последняя резервная копия повреждена")

        return DiagnosticsReport(
            healthy=not issues,
            integrity=integrity,
            journal_mode=journal_mode,
            foreign_keys=foreign_keys,
            schema_version=schema_version,
            expected_schema_version=CURRENT_SCHEMA_VERSION,
            database_path=str(database_path),
            database_size=database_path.stat().st_size if database_path.exists() else 0,
            table_count=len(tables),
            index_count=index_count,
            total_rows=sum(table_rows.values()),
            table_rows=table_rows,
            latest_backup=latest_backup,
            latest_backup_valid=latest_backup_valid,
            issues=tuple(issues),
        )
