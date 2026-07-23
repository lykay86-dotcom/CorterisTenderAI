from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlalchemy import inspect, text

from app.database.database_health import DatabaseHealthService
from app.database.migration import CURRENT_SCHEMA_VERSION
from app.database.session import get_engine, init_database, reset_database_state
from app.repositories.tenders import TenderRepository


def _create_legacy_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript("""
    CREATE TABLE tenders (
      id INTEGER PRIMARY KEY NOT NULL, number VARCHAR(100) NOT NULL,
      title VARCHAR(500) NOT NULL, source_url TEXT NOT NULL,
      platform VARCHAR(200) NOT NULL, customer VARCHAR(500) NOT NULL,
      region VARCHAR(200) NOT NULL, law VARCHAR(50) NOT NULL,
      nmck FLOAT NOT NULL, deadline VARCHAR(50) NOT NULL,
      source_dir TEXT NOT NULL, status VARCHAR(50) NOT NULL,
      score INTEGER NOT NULL, recommendation VARCHAR(250) NOT NULL,
      created_at DATETIME NOT NULL
    );
    CREATE TABLE documents (
      id INTEGER PRIMARY KEY NOT NULL, tender_id INTEGER NOT NULL,
      name VARCHAR(500) NOT NULL, path TEXT NOT NULL,
      kind VARCHAR(100) NOT NULL, text TEXT NOT NULL, page_count INTEGER NOT NULL
    );
    CREATE TABLE analyses (
      id INTEGER PRIMARY KEY NOT NULL, tender_id INTEGER NOT NULL,
      created_at DATETIME NOT NULL, profile_score INTEGER NOT NULL,
      legal_risk INTEGER NOT NULL, competition_risk INTEGER NOT NULL,
      technical_risk INTEGER NOT NULL, financial_risk INTEGER NOT NULL,
      estimate_total FLOAT NOT NULL, estimated_profit FLOAT NOT NULL,
      margin_percent FLOAT NOT NULL, report JSON NOT NULL
    );
    INSERT INTO tenders VALUES (1,'OLD-1','Старый тендер','','ЕИС','Заказчик','Москва','44-ФЗ',1000000,'','','Новый',0,'Не анализировался','2026-07-01T10:00:00');
    INSERT INTO documents VALUES (10,1,'ТЗ.pdf','C:/docs/tz.pdf','ТЗ','Текст',3);
    INSERT INTO analyses VALUES (20,1,'2026-07-01T11:00:00',80,10,15,20,10,700000,300000,30,'{}');
    """)
    connection.commit()
    connection.close()


def test_migrates_integer_ids_and_audit_columns(tmp_path):
    reset_database_state()
    database = tmp_path / "legacy.db"
    _create_legacy_database(database)
    init_database(database)
    engine = get_engine()
    columns = {c["name"] for c in inspect(engine).get_columns("tenders")}
    assert {"updated_at", "deleted_at", "is_deleted", "row_version"} <= columns
    assert (
        "CHAR" in str(inspect(engine).get_columns("tenders")[0]["type"]).upper()
        or "VARCHAR" in str(inspect(engine).get_columns("tenders")[0]["type"]).upper()
    )
    rows = TenderRepository().list()
    assert len(rows) == 1
    assert rows[0].title == "Старый тендер"
    assert len(str(rows[0].id)) == 36
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM documents")) == 1
        assert connection.scalar(text("SELECT COUNT(*) FROM analyses")) == 1
        assert (
            connection.scalar(text("SELECT version FROM schema_version WHERE id=1"))
            == CURRENT_SCHEMA_VERSION
        )
    backups = list((tmp_path / "backups").glob("*.db"))
    assert backups
    reset_database_state()


def test_migration_is_idempotent(tmp_path):
    reset_database_state()
    database = tmp_path / "legacy.db"
    _create_legacy_database(database)
    init_database(database)
    reset_database_state()
    init_database(database)
    assert len(TenderRepository().list()) == 1
    reset_database_state()


def test_database_health_after_migration(tmp_path):
    reset_database_state()
    database = tmp_path / "legacy.db"
    _create_legacy_database(database)
    init_database(database)
    report = DatabaseHealthService(get_engine()).check()
    assert report.healthy
    assert report.journal_mode.lower() == "wal"
    reset_database_state()
