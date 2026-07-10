"""Безопасное резервное копирование локальной SQLite."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path


def backup_sqlite_database(source: Path, destination_dir: Path) -> Path:
    if not source.exists():
        raise FileNotFoundError(f"База данных не найдена: {source}")
    destination_dir.mkdir(parents=True, exist_ok=True)
    target = destination_dir / f"corteris_db_{datetime.now():%Y%m%d_%H%M%S}.db"
    with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    return target
