"""Strict expected-red contracts for the RM-156 contractor model."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import timezone
import importlib
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import inspect, text

from app.database.backup_manager import BackupManager
from app.database.exceptions import DuplicateEntityError
from app.database.migration import MigrationError
from app.database.models import Company
from app.database.seed import seed_default_data
from app.database.session import (
    get_engine,
    init_database,
    reset_database_state,
    session_scope,
)
from app.database.unit_of_work import UnitOfWork
from app.tenders.collector.schema import COLLECTOR_SCHEMA_VERSION
from app.tenders.models import TenderCustomer


ORGANIZATION_INN = "9701327346"
INDIVIDUAL_INN = "500100732259"


@pytest.fixture(autouse=True)
def _isolated_database_state():
    reset_database_state()
    yield
    reset_database_state()


def _public_api():
    try:
        return importlib.import_module("app.contractors")
    except ModuleNotFoundError as exc:
        pytest.fail(f"RM-156 public contractor API is missing: {exc}")


def _public_symbol(name: str):
    module = _public_api()
    value = getattr(module, name, None)
    if value is None:
        pytest.fail(f"RM-156 public contractor symbol is missing: {name}")
    return value


def _database_symbol(module_name: str, name: str):
    module = importlib.import_module(module_name)
    value = getattr(module, name, None)
    if value is None:
        pytest.fail(f"RM-156 database symbol is missing: {module_name}.{name}")
    return value


def test_contractor_inn_accepts_canonical_organization_and_individual_vectors() -> None:
    contractor_inn = _public_symbol("ContractorInn")
    contractor_kind = _public_symbol("ContractorInnKind")

    organization = contractor_inn.parse(f"  {ORGANIZATION_INN}  ")
    individual = contractor_inn.parse(INDIVIDUAL_INN)

    assert organization.value == ORGANIZATION_INN
    assert organization.kind is contractor_kind.ORGANIZATION
    assert individual.value == INDIVIDUAL_INN
    assert individual.kind is contractor_kind.INDIVIDUAL
    with pytest.raises(FrozenInstanceError):
        organization.value = INDIVIDUAL_INN


@pytest.mark.parametrize(
    "value",
    [
        "",
        " ",
        "970132734",
        "97013273460",
        "50010073225",
        "5001007322590",
        "9701327347",
        "500100732258",
        "97013 27346",
        "97013-27346",
        "９７０１３２７３４６",
        9701327346,
        9701327346.0,
        True,
        None,
    ],
)
def test_contractor_inn_rejects_invalid_type_shape_and_checksum(value: object) -> None:
    contractor_inn = _public_symbol("ContractorInn")

    with pytest.raises((TypeError, ValueError)):
        contractor_inn.parse(value)


def test_contractor_orm_has_minimal_schema_and_direct_validation() -> None:
    contractor = _database_symbol("app.database.models", "Contractor")

    columns = set(contractor.__table__.columns.keys())
    assert columns == {
        "id",
        "inn",
        "created_at",
        "updated_at",
        "is_deleted",
        "deleted_at",
        "row_version",
    }
    assert contractor(inn=f" {ORGANIZATION_INN} ").inn == ORGANIZATION_INN
    with pytest.raises(ValueError):
        contractor(inn="9701327347")


def test_contractor_repository_owns_unique_lifecycle_and_uow_access(tmp_path: Path) -> None:
    database = tmp_path / "contractors.db"
    init_database(database)

    with UnitOfWork() as uow:
        created = uow.contractors.create(ORGANIZATION_INN)
        contractor_id = created.id

    with UnitOfWork() as uow:
        restored = uow.contractors.get_by_inn(f" {ORGANIZATION_INN} ")
        assert restored is not None
        assert restored.id == contractor_id
        uow.contractors.delete(restored)

    with UnitOfWork() as uow:
        assert uow.contractors.get_by_inn(ORGANIZATION_INN) is None
        deleted = uow.contractors.get_by_inn(ORGANIZATION_INN, include_deleted=True)
        assert deleted is not None
        with pytest.raises(DuplicateEntityError):
            uow.contractors.create(ORGANIZATION_INN)
        uow.contractors.restore(deleted)

    with UnitOfWork() as uow:
        active = uow.contractors.get_by_inn(ORGANIZATION_INN)
        assert active is not None
        assert active.id == contractor_id
        assert active.row_version == 3


def test_sqlite_audit_timestamps_remain_aware_utc_after_round_trip(tmp_path: Path) -> None:
    database = tmp_path / "timestamps.db"
    init_database(database)

    with session_scope() as session:
        company = Company(full_name="UTC probe", short_name="UTC probe")
        session.add(company)
        session.flush()
        assert company.created_at.tzinfo is timezone.utc

    with session_scope() as session:
        restored = session.query(Company).filter_by(short_name="UTC probe").one()
        assert restored.created_at.tzinfo is not None
        assert restored.created_at.utcoffset() == timezone.utc.utcoffset(None)
        restored.soft_delete()

    with session_scope() as session:
        deleted = session.query(Company).filter_by(short_name="UTC probe").one()
        assert deleted.deleted_at is not None
        assert deleted.deleted_at.tzinfo is not None
        assert deleted.updated_at.tzinfo is not None


def test_fresh_database_is_schema_four_with_unique_contractor_identity(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    init_database(database)
    engine = get_engine()

    assert "contractors" in inspect(engine).get_table_names()
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version FROM schema_version WHERE id=1")) == 4

    indexes = inspect(engine).get_indexes("contractors")
    constraints = inspect(engine).get_unique_constraints("contractors")
    assert any(
        item.get("unique") and item.get("column_names") == ["inn"] for item in indexes
    ) or any(item.get("column_names") == ["inn"] for item in constraints)


def test_schema_three_migration_preserves_rows_and_creates_verified_backup(tmp_path: Path) -> None:
    database = tmp_path / "schema3.db"
    backups = tmp_path / "backups"
    init_database(database, backup_dir=backups)
    seeded = seed_default_data()
    seeded_id = seeded.id
    reset_database_state()

    with sqlite3.connect(database) as connection:
        connection.execute("DROP TABLE IF EXISTS contractors")
        connection.execute("UPDATE schema_version SET version=3 WHERE id=1")
        connection.commit()

    backups_before = set(backups.glob("*.db"))
    init_database(database, backup_dir=backups)
    engine = get_engine()
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version FROM schema_version WHERE id=1")) == 4
        assert (
            connection.scalar(
                text("SELECT COUNT(*) FROM companies WHERE id=:id"), {"id": seeded_id}
            )
            == 1
        )
    assert "contractors" in inspect(engine).get_table_names()
    backups_after = set(backups.glob("*.db"))
    created_backups = backups_after - backups_before
    assert len(created_backups) == 1
    backup = created_backups.pop()
    assert backup.with_suffix(".json").is_file()
    assert BackupManager(database, backups).verify(backup)


def test_future_schema_is_rejected_without_downgrade_or_write(tmp_path: Path) -> None:
    database = tmp_path / "future.db"
    init_database(database)
    reset_database_state()

    with sqlite3.connect(database) as connection:
        connection.execute("DROP TABLE IF EXISTS contractors")
        connection.execute("UPDATE schema_version SET version=99 WHERE id=1")
        connection.commit()

    with pytest.raises(MigrationError):
        init_database(database)
    reset_database_state()

    with sqlite3.connect(database) as connection:
        assert (
            connection.execute("SELECT version FROM schema_version WHERE id=1").fetchone()[0] == 99
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='contractors'"
            ).fetchone()[0]
            == 0
        )


def test_corrupt_schema_version_is_sanitized_and_not_rewritten(tmp_path: Path) -> None:
    database = tmp_path / "corrupt.db"
    init_database(database)
    reset_database_state()

    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE schema_version SET version='broken' WHERE id=1")
        connection.commit()

    with pytest.raises(MigrationError, match="структур"):
        init_database(database)
    reset_database_state()

    with sqlite3.connect(database) as connection:
        assert (
            connection.execute("SELECT version FROM schema_version WHERE id=1").fetchone()[0]
            == "broken"
        )


def test_missing_existing_schema_version_row_is_not_recreated(tmp_path: Path) -> None:
    database = tmp_path / "missing-version.db"
    init_database(database)
    reset_database_state()

    with sqlite3.connect(database) as connection:
        connection.execute("DELETE FROM schema_version")
        connection.commit()

    with pytest.raises(MigrationError, match="структур"):
        init_database(database)
    reset_database_state()

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0] == 0


def test_contractor_public_context_has_no_future_stage_or_ui_imports() -> None:
    module = _public_api()
    root = Path(module.__file__).resolve().parent
    source = "\n".join(path.read_text(encoding="utf-8") for path in sorted(root.glob("*.py")))

    forbidden = (
        "app.tenders",
        "app.ui",
        "app.core.ai",
        "httpx",
        "keyring",
        "score",
        "recommendation",
    )
    assert not [name for name in forbidden if name in source]


def test_existing_company_owner_remains_the_corteris_profile() -> None:
    assert Company.__tablename__ == "companies"
    assert {"bank_name", "profit_percent", "logo_path", "licenses"} <= set(
        Company.__table__.columns.keys()
    )
    assert "contractor_id" not in Company.__table__.columns


def test_tender_customer_remains_an_observation_not_a_master_record() -> None:
    observation = TenderCustomer(name="Непроверенный заказчик")

    assert observation.inn == ""
    assert not hasattr(observation, "contractor_id")
    assert not hasattr(observation, "row_version")


def test_collector_schema_and_decision_boundary_remain_unchanged() -> None:
    assert COLLECTOR_SCHEMA_VERSION == 16
