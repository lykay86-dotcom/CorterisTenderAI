from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import inspect, text

from app.database.backup import backup_sqlite_database
from app.database.models import Company
from app.database.repositories import CompanyRepository, SettingsRepository
from app.database.seed import seed_default_data
from app.database.session import (
    get_engine,
    init_database,
    reset_database_state,
    session_scope,
)
from app.database.unit_of_work import UnitOfWork


@pytest.fixture()
def database(tmp_path):
    reset_database_state()
    db_path = tmp_path / "test.db"
    init_database(db_path)
    yield db_path
    reset_database_state()


def test_database_creates_expected_tables(database):
    tables = set(inspect(get_engine()).get_table_names())
    assert {"companies", "app_settings", "audit_logs", "tenders", "documents", "analyses"} <= tables
    assert "schema_version" in tables


def test_sqlite_wal_and_foreign_keys(database):
    with get_engine().connect() as connection:
        assert str(connection.scalar(text("PRAGMA journal_mode"))).lower() == "wal"
        assert connection.scalar(text("PRAGMA foreign_keys")) == 1


def test_seed_is_idempotent(database):
    first = seed_default_data()
    second = seed_default_data()
    assert first.id == second.id
    with session_scope() as session:
        assert len(CompanyRepository(session).list()) == 1


def test_default_company_values(database):
    seed_default_data()
    with session_scope() as session:
        company = CompanyRepository(session).get_by_inn("9701327346")
        assert company is not None
        assert company.vat_rate == Decimal("22.00")
        assert company.profit_percent == Decimal("30.00")
        assert company.director_name == "Лукин Юрий Юрьевич"


def test_settings_round_trip(database):
    with session_scope() as session:
        repo = SettingsRepository(session)
        repo.set_value("test.flag", True)
    with session_scope() as session:
        assert SettingsRepository(session).get_value("test.flag") is True


def test_soft_delete_and_restore(database):
    with UnitOfWork() as uow:
        company = uow.companies.add(Company(full_name="Test", short_name="Test Company"))
        company_id = company.id
    with UnitOfWork() as uow:
        company = uow.companies.require(company_id)
        uow.companies.delete(company)
    with UnitOfWork() as uow:
        assert uow.companies.get(company_id) is None
        deleted = uow.companies.require(company_id, include_deleted=True)
        uow.companies.restore(deleted)
    with UnitOfWork() as uow:
        assert uow.companies.get(company_id) is not None


def test_unit_of_work_rolls_back_on_exception(database):
    with pytest.raises(RuntimeError):
        with UnitOfWork() as uow:
            uow.companies.add(Company(full_name="Rollback", short_name="Rollback Co"))
            raise RuntimeError("stop")
    with session_scope() as session:
        assert CompanyRepository(session).get_by_inn("") is None
        assert all(c.short_name != "Rollback Co" for c in CompanyRepository(session).list())


def test_backup_creates_readable_copy(database, tmp_path):
    seed_default_data()
    backup = backup_sqlite_database(database, tmp_path / "backups")
    assert backup.exists() and backup.stat().st_size > 0


def test_uuid_primary_key(database):
    with session_scope() as session:
        company = Company(full_name="UUID", short_name="UUID Co")
        session.add(company)
        session.flush()
        assert len(company.id) == 36


def test_schema_version(database):
    with get_engine().connect() as connection:
        assert connection.scalar(text("SELECT version FROM schema_version WHERE id = 1")) == 3
