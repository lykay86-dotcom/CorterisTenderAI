"""Shared initialization boundary for Collector repositories."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
import sqlite3

if TYPE_CHECKING:
    from app.tenders.collector.schema import CollectorSchemaMigrator


def initialize_collector_database(
    path: str | Path,
    *,
    migrator: CollectorSchemaMigrator | None = None,
) -> int:
    """Initialize the base registry and apply the single Collector schema owner."""

    # Local imports keep this boundary usable while app.tenders is initializing.
    from app.tenders.collector.schema import CollectorSchemaMigrator
    from app.tenders.tender_registry import TenderRegistryRepository

    database_path = Path(path).expanduser()
    TenderRegistryRepository(database_path).initialize()
    connection = sqlite3.connect(database_path, timeout=30.0)
    try:
        version = (migrator or CollectorSchemaMigrator()).migrate(connection)
        connection.commit()
        return version
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


__all__ = ["initialize_collector_database"]
