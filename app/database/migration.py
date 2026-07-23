"""Версионированные миграции локальной базы без потери пользовательских данных."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Engine, text

from .backup_manager import BackupManager
from .base import Base
from .schema_inspector import SchemaInspector

CURRENT_SCHEMA_VERSION = 4
_UUID_NAMESPACE = uuid.UUID("e370a77b-dbf6-4b66-a86f-3b29172d184e")


@dataclass(frozen=True, slots=True)
class MigrationResult:
    previous_version: int
    current_version: int
    changed: bool
    backup_path: Path | None = None


class MigrationError(RuntimeError):
    """Ошибка обновления схемы базы данных."""


class MigrationManager:
    """Обновляет старые SQLite-схемы до текущей структуры ORM."""

    def __init__(self, engine: Engine, *, backup_dir: Path | None = None) -> None:
        self.engine = engine
        database = engine.url.database
        self.database_path = Path(database).resolve() if database else None
        self.backup_dir = backup_dir or (
            self.database_path.parent / "backups" if self.database_path else None
        )

    def _ensure_version_table(self) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS schema_version ("
                    "id INTEGER PRIMARY KEY CHECK (id = 1), "
                    "version INTEGER NOT NULL, "
                    "app_version VARCHAR(32), "
                    "updated_at DATETIME)"
                )
            )
            connection.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS migration_history ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "from_version INTEGER NOT NULL, "
                    "to_version INTEGER NOT NULL, "
                    "status VARCHAR(32) NOT NULL, "
                    "backup_path TEXT, "
                    "message TEXT, "
                    "applied_at DATETIME NOT NULL)"
                )
            )
            columns = (
                {
                    row[1]
                    for row in connection.exec_driver_sql(
                        "PRAGMA table_info(schema_version)"
                    ).fetchall()
                }
                if self.engine.dialect.name == "sqlite"
                else set()
            )
            if self.engine.dialect.name == "sqlite":
                if "app_version" not in columns:
                    connection.exec_driver_sql(
                        "ALTER TABLE schema_version ADD COLUMN app_version VARCHAR(32)"
                    )
                if "updated_at" not in columns:
                    connection.exec_driver_sql(
                        "ALTER TABLE schema_version ADD COLUMN updated_at DATETIME"
                    )
            exists = connection.scalar(text("SELECT COUNT(*) FROM schema_version WHERE id = 1"))
            if not exists:
                connection.execute(
                    text(
                        "INSERT INTO schema_version (id, version, app_version, updated_at) "
                        "VALUES (1, 0, '1.5.1', :updated_at)"
                    ),
                    {"updated_at": self._now()},
                )

    def current_version(self) -> int:
        self._ensure_version_table()
        with self.engine.connect() as connection:
            raw_version = connection.scalar(text("SELECT version FROM schema_version WHERE id = 1"))
        return self._coerce_version(raw_version)

    @staticmethod
    def _coerce_version(raw_version: object) -> int:
        if isinstance(raw_version, bool) or not isinstance(raw_version, (int, str)):
            raise MigrationError("Не удалось прочитать структуру базы данных")
        try:
            version = int(raw_version)
        except (TypeError, ValueError) as exc:
            raise MigrationError("Не удалось прочитать структуру базы данных") from exc
        if version < 0 or str(raw_version).strip() != str(version):
            raise MigrationError("Не удалось прочитать структуру базы данных")
        return version

    def _existing_version(self) -> int | None:
        inspector = SchemaInspector(self.engine)
        if not inspector.table_exists("schema_version"):
            return None
        with self.engine.connect() as connection:
            raw_version = connection.scalar(text("SELECT version FROM schema_version WHERE id = 1"))
        if raw_version is None:
            raise MigrationError("Не удалось прочитать структуру базы данных")
        return self._coerce_version(raw_version)

    def upgrade(self) -> MigrationResult:
        existing_version = self._existing_version()
        if existing_version is not None and existing_version > CURRENT_SCHEMA_VERSION:
            raise MigrationError(
                "Структура базы данных создана более новой версией приложения "
                f"({existing_version} > {CURRENT_SCHEMA_VERSION})"
            )
        self._ensure_version_table()
        previous = self.current_version()
        if previous > CURRENT_SCHEMA_VERSION:
            raise MigrationError(
                "Структура базы данных создана более новой версией приложения "
                f"({previous} > {CURRENT_SCHEMA_VERSION})"
            )
        inspector = SchemaInspector(self.engine)
        requires_legacy_rebuild = self._requires_legacy_rebuild(inspector)
        requires_audit_columns = self._requires_audit_columns(inspector)
        changed = (
            previous < CURRENT_SCHEMA_VERSION or requires_legacy_rebuild or requires_audit_columns
        )
        backup_path: Path | None = None

        if (
            changed
            and self.database_path
            and self.database_path.exists()
            and self.database_path.stat().st_size
        ):
            if self.backup_dir is None:
                raise MigrationError("Не определён каталог резервных копий")
            backup_path = (
                BackupManager(self.database_path, self.backup_dir).create(reason="migration").path
            )

        try:
            if self.engine.dialect.name == "sqlite":
                if requires_legacy_rebuild:
                    self._rebuild_legacy_tables()
                else:
                    self._add_missing_audit_columns()
            Base.metadata.create_all(self.engine)
            self._create_indexes()
            self._set_version(CURRENT_SCHEMA_VERSION)
            self._verify()
            if changed:
                self._record_history(
                    previous, CURRENT_SCHEMA_VERSION, "success", backup_path, "Migration completed"
                )
        except Exception as exc:
            try:
                self._record_history(
                    previous, CURRENT_SCHEMA_VERSION, "failed", backup_path, str(exc)
                )
            except Exception:
                pass
            if backup_path and self.database_path:
                try:
                    self.engine.dispose()
                    BackupManager(
                        self.database_path, self.backup_dir or backup_path.parent
                    ).restore(backup_path, create_safety_backup=False)
                except Exception:
                    pass
            raise MigrationError(
                f"Не удалось обновить структуру базы. Резервная копия: {backup_path or 'не создана'}"
            ) from exc

        return MigrationResult(previous, CURRENT_SCHEMA_VERSION, changed, backup_path)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _stable_uuid(table: str, old_id: object) -> str:
        return str(uuid.uuid5(_UUID_NAMESPACE, f"{table}:{old_id}"))

    @staticmethod
    def _requires_legacy_rebuild(inspector: SchemaInspector) -> bool:
        if not inspector.table_exists("tenders"):
            return False
        primary_type = inspector.primary_key_type("tenders") or ""
        return "INT" in primary_type

    @staticmethod
    def _requires_audit_columns(inspector: SchemaInspector) -> bool:
        required = {"created_at", "updated_at", "is_deleted", "deleted_at", "row_version"}
        for table in ("tenders", "documents", "analyses"):
            if inspector.table_exists(table) and not required <= set(inspector.columns(table)):
                return True
        return False

    def _record_history(
        self,
        from_version: int,
        to_version: int,
        status: str,
        backup_path: Path | None,
        message: str,
    ) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO migration_history "
                    "(from_version, to_version, status, backup_path, message, applied_at) "
                    "VALUES (:from_version, :to_version, :status, :backup_path, :message, :applied_at)"
                ),
                {
                    "from_version": from_version,
                    "to_version": to_version,
                    "status": status,
                    "backup_path": str(backup_path) if backup_path else None,
                    "message": message[:2000],
                    "applied_at": self._now(),
                },
            )

    def _set_version(self, version: int) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE schema_version SET version=:version, app_version='1.5.1', "
                    "updated_at=:updated_at WHERE id=1"
                ),
                {"version": version, "updated_at": self._now()},
            )

    def _add_missing_audit_columns(self) -> None:
        inspector = SchemaInspector(self.engine)
        definitions = {
            "created_at": "DATETIME",
            "updated_at": "DATETIME",
            "is_deleted": "BOOLEAN NOT NULL DEFAULT 0",
            "deleted_at": "DATETIME",
            "row_version": "INTEGER NOT NULL DEFAULT 1",
        }
        now = self._now()
        with self.engine.begin() as connection:
            for table in ("tenders", "documents", "analyses"):
                if not inspector.table_exists(table):
                    continue
                existing = set(inspector.columns(table))
                for name, ddl in definitions.items():
                    if name not in existing:
                        connection.exec_driver_sql(
                            f'ALTER TABLE "{table}" ADD COLUMN "{name}" {ddl}'
                        )
                connection.execute(
                    text(
                        f'UPDATE "{table}" SET created_at=COALESCE(created_at, :now), '
                        f"updated_at=COALESCE(updated_at, created_at, :now), "
                        "is_deleted=COALESCE(is_deleted, 0), row_version=COALESCE(row_version, 1)"
                    ),
                    {"now": now},
                )

    def _rebuild_legacy_tables(self) -> None:
        """Переводит старые INTEGER ID в UUID и сохраняет все связи."""
        if self.database_path is None:
            raise MigrationError("Для миграции SQLite не определён путь к базе")
        self.engine.dispose()
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute("BEGIN IMMEDIATE")
            now = self._now()

            tender_rows = connection.execute("SELECT * FROM tenders").fetchall()
            document_rows = (
                connection.execute("SELECT * FROM documents").fetchall()
                if self._sqlite_table_exists(connection, "documents")
                else []
            )
            analysis_rows = (
                connection.execute("SELECT * FROM analyses").fetchall()
                if self._sqlite_table_exists(connection, "analyses")
                else []
            )
            tender_ids = {row["id"]: self._stable_uuid("tenders", row["id"]) for row in tender_rows}

            for table in ("tenders_v2", "documents_v2", "analyses_v2"):
                connection.execute(f"DROP TABLE IF EXISTS {table}")
            self._create_v2_tables(connection)

            for row in tender_rows:
                data = dict(row)
                created = data.get("created_at") or now
                connection.execute(
                    "INSERT INTO tenders_v2 (id, number, title, source_url, platform, customer, region, law, nmck, deadline, source_dir, status, score, recommendation, created_at, updated_at, is_deleted, deleted_at, row_version) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, 1)",
                    (
                        tender_ids[row["id"]],
                        data.get("number", ""),
                        data.get("title", ""),
                        data.get("source_url", ""),
                        data.get("platform", "Ручной импорт"),
                        data.get("customer", ""),
                        data.get("region", ""),
                        data.get("law", "Не определён"),
                        data.get("nmck", 0),
                        data.get("deadline", ""),
                        data.get("source_dir", ""),
                        data.get("status", "Новый"),
                        data.get("score", 0),
                        data.get("recommendation", "Не анализировался"),
                        created,
                        created,
                    ),
                )

            for row in document_rows:
                data = dict(row)
                created = data.get("created_at") or now
                mapped_tender = tender_ids.get(row["tender_id"])
                if mapped_tender is None:
                    continue
                connection.execute(
                    "INSERT INTO documents_v2 (id, tender_id, name, path, kind, text, page_count, created_at, updated_at, is_deleted, deleted_at, row_version) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, 1)",
                    (
                        self._stable_uuid("documents", row["id"]),
                        mapped_tender,
                        data.get("name", ""),
                        data.get("path", ""),
                        data.get("kind", "Не определён"),
                        data.get("text", ""),
                        data.get("page_count", 0),
                        created,
                        created,
                    ),
                )

            for row in analysis_rows:
                data = dict(row)
                created = data.get("created_at") or now
                mapped_tender = tender_ids.get(row["tender_id"])
                if mapped_tender is None:
                    continue
                connection.execute(
                    "INSERT INTO analyses_v2 (id, tender_id, profile_score, legal_risk, competition_risk, technical_risk, financial_risk, estimate_total, estimated_profit, margin_percent, report, created_at, updated_at, is_deleted, deleted_at, row_version) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, 1)",
                    (
                        self._stable_uuid("analyses", row["id"]),
                        mapped_tender,
                        data.get("profile_score", 0),
                        data.get("legal_risk", 0),
                        data.get("competition_risk", 0),
                        data.get("technical_risk", 0),
                        data.get("financial_risk", 0),
                        data.get("estimate_total", 0),
                        data.get("estimated_profit", 0),
                        data.get("margin_percent", 0),
                        data.get("report", "{}"),
                        created,
                        created,
                    ),
                )

            for table in ("documents", "analyses", "tenders"):
                if self._sqlite_table_exists(connection, table):
                    connection.execute(f"DROP TABLE {table}")
            connection.execute("ALTER TABLE tenders_v2 RENAME TO tenders")
            connection.execute("ALTER TABLE documents_v2 RENAME TO documents")
            connection.execute("ALTER TABLE analyses_v2 RENAME TO analyses")
            connection.commit()
            connection.execute("PRAGMA foreign_keys=ON")
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _sqlite_table_exists(connection: sqlite3.Connection, table: str) -> bool:
        return (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            is not None
        )

    @staticmethod
    def _create_v2_tables(connection: sqlite3.Connection) -> None:
        connection.executescript("""
        CREATE TABLE tenders_v2 (
            id VARCHAR(36) PRIMARY KEY NOT NULL,
            number VARCHAR(100) DEFAULT '', title VARCHAR(500) NOT NULL,
            source_url TEXT DEFAULT '', platform VARCHAR(200) DEFAULT 'Ручной импорт',
            customer VARCHAR(500) DEFAULT '', region VARCHAR(200) DEFAULT '', law VARCHAR(50) DEFAULT 'Не определён',
            nmck NUMERIC(18,2) DEFAULT 0, deadline VARCHAR(50) DEFAULT '', source_dir TEXT DEFAULT '',
            status VARCHAR(50) DEFAULT 'Новый', score INTEGER DEFAULT 0,
            recommendation VARCHAR(250) DEFAULT 'Не анализировался',
            created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL,
            is_deleted BOOLEAN NOT NULL DEFAULT 0, deleted_at DATETIME, row_version INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE documents_v2 (
            id VARCHAR(36) PRIMARY KEY NOT NULL,
            tender_id VARCHAR(36) NOT NULL REFERENCES tenders_v2(id) ON DELETE CASCADE,
            name VARCHAR(500) NOT NULL, path TEXT NOT NULL, kind VARCHAR(100) DEFAULT 'Не определён',
            text TEXT DEFAULT '', page_count INTEGER DEFAULT 0,
            created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL,
            is_deleted BOOLEAN NOT NULL DEFAULT 0, deleted_at DATETIME, row_version INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE analyses_v2 (
            id VARCHAR(36) PRIMARY KEY NOT NULL,
            tender_id VARCHAR(36) NOT NULL REFERENCES tenders_v2(id) ON DELETE CASCADE,
            profile_score INTEGER DEFAULT 0, legal_risk INTEGER DEFAULT 0, competition_risk INTEGER DEFAULT 0,
            technical_risk INTEGER DEFAULT 0, financial_risk INTEGER DEFAULT 0,
            estimate_total NUMERIC(18,2) DEFAULT 0, estimated_profit NUMERIC(18,2) DEFAULT 0,
            margin_percent NUMERIC(7,2) DEFAULT 0, report JSON DEFAULT '{}',
            created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL,
            is_deleted BOOLEAN NOT NULL DEFAULT 0, deleted_at DATETIME, row_version INTEGER NOT NULL DEFAULT 1
        );
        """)

    def _create_indexes(self) -> None:
        statements = (
            "CREATE INDEX IF NOT EXISTS ix_tenders_number ON tenders(number)",
            "CREATE INDEX IF NOT EXISTS ix_tenders_customer ON tenders(customer)",
            "CREATE INDEX IF NOT EXISTS ix_tenders_status ON tenders(status)",
            "CREATE INDEX IF NOT EXISTS ix_tenders_is_deleted ON tenders(is_deleted)",
            "CREATE INDEX IF NOT EXISTS ix_documents_tender_id ON documents(tender_id)",
            "CREATE INDEX IF NOT EXISTS ix_documents_kind ON documents(kind)",
            "CREATE INDEX IF NOT EXISTS ix_documents_is_deleted ON documents(is_deleted)",
            "CREATE INDEX IF NOT EXISTS ix_analyses_tender_id ON analyses(tender_id)",
            "CREATE INDEX IF NOT EXISTS ix_analyses_is_deleted ON analyses(is_deleted)",
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_contractors_inn ON contractors(inn)",
        )
        with self.engine.begin() as connection:
            for statement in statements:
                connection.exec_driver_sql(statement)

    def _verify(self) -> None:
        inspector = SchemaInspector(self.engine)
        required = {"id", "created_at", "updated_at", "is_deleted", "deleted_at", "row_version"}
        for table in ("tenders", "documents", "analyses"):
            if not inspector.table_exists(table):
                raise MigrationError(f"После миграции отсутствует таблица {table}")
            missing = required - set(inspector.columns(table))
            if missing:
                raise MigrationError(f"В таблице {table} отсутствуют колонки: {sorted(missing)}")
        with self.engine.connect() as connection:
            integrity = str(connection.scalar(text("PRAGMA integrity_check")) or "")
            if integrity.lower() != "ok":
                raise MigrationError(
                    f"Проверка целостности SQLite завершилась ошибкой: {integrity}"
                )
        contractor_columns = set(inspector.columns("contractors"))
        if contractor_columns != {
            "id",
            "inn",
            "created_at",
            "updated_at",
            "is_deleted",
            "deleted_at",
            "row_version",
        }:
            raise MigrationError("После миграции структура contractors не соответствует RM-156")
        with self.engine.connect() as connection:
            indexes = connection.exec_driver_sql("PRAGMA index_list('contractors')").fetchall()
            unique_indexes = {str(row[1]) for row in indexes if int(row[2]) == 1}
        if "ix_contractors_inn" not in unique_indexes:
            raise MigrationError("После миграции отсутствует unique index contractors.inn")
