"""Последовательность безопасного запуска базы данных."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Engine

from .backup_manager import BackupManager
from .database_health import DatabaseHealthService
from .migration import MigrationResult
from .seed import seed_default_data
from .session import get_engine, init_database


@dataclass(frozen=True, slots=True)
class StartupDatabaseResult:
    engine: Engine
    migration: MigrationResult | None
    backup_dir: Path
    database_path: Path


def initialize_database_pipeline(database_path: Path, backup_dir: Path) -> StartupDatabaseResult:
    """Инициализирует БД, выполняет миграции, проверяет целостность и seed."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)
    engine = init_database(database_path, backup_dir=backup_dir)

    health = DatabaseHealthService(engine).check()
    if not health.healthy:
        raise RuntimeError(
            f"Проверка базы не пройдена: integrity={health.integrity}, "
            f"foreign_keys={health.foreign_keys}, journal={health.journal_mode}"
        )
    seed_default_data()

    # init_database уже выполнил миграцию. Сохраняем сведения для вызывающего кода.
    from .migration import MigrationManager
    manager = MigrationManager(get_engine(), backup_dir=backup_dir)
    migration = MigrationResult(
        previous_version=manager.current_version(),
        current_version=manager.current_version(),
        changed=False,
        backup_path=None,
    )
    return StartupDatabaseResult(engine, migration, backup_dir, database_path)


def create_maintenance_service(database_path: Path, backup_dir: Path):
    from .maintenance import DatabaseMaintenanceService

    return DatabaseMaintenanceService(
        get_engine(), BackupManager(database_path, backup_dir)
    )
