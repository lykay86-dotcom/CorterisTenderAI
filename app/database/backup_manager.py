"""
AIBOS Security
Commit #43
File: app/database/backup_manager.py

Backup manager using SafeFileOperation and DatabaseLocker.
"""

from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.database.database_locker import DatabaseLocker
from app.database.engine import get_engine
from app.database.safe_file_operation import SafeFileOperation


@dataclass(slots=True)
class BackupInfo:
    path: Path
    created_at: datetime
    reason: str


class BackupManager:

    def __init__(self, database_path: Path | str, backup_dir: Path | str):
        self.database_path = Path(database_path)
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        self._files = SafeFileOperation()
        self._locker = DatabaseLocker(get_engine)

    def create(self, reason: str = "manual") -> BackupInfo:
        ts = datetime.now()
        backup = self.backup_dir / f"{ts:%Y%m%d_%H%M%S}.db"

        self._locker.release()
        self._files.safe_copy(self.database_path, backup)

        if not self._files.verify_copy(self.database_path, backup):
            raise RuntimeError("Backup verification failed")

        return BackupInfo(
            path=backup,
            created_at=ts,
            reason=reason,
        )

    def restore(self, backup_path: Path | str) -> None:
        backup_path = Path(backup_path)

        if not backup_path.exists():
            raise FileNotFoundError(backup_path)

        self._locker.release()

        safety = self.database_path.with_suffix(".before_restore.db")

        if self.database_path.exists():
            self._files.safe_copy(self.database_path, safety)

        temporary = self.database_path.with_suffix(".restore.tmp")

        try:
            self._files.safe_copy(backup_path, temporary)
            self._files.safe_replace(temporary, self.database_path)

            with sqlite3.connect(self.database_path) as conn:
                result = conn.execute(
                    "PRAGMA integrity_check"
                ).fetchone()[0]

            if result.lower() != "ok":
                raise RuntimeError(result)

        except Exception:
            if safety.exists():
                shutil.copy2(safety, self.database_path)
            raise

        finally:
            if temporary.exists():
                try:
                    self._files.safe_delete(temporary)
                except PermissionError:
                    pass

    def verify(self, backup_path: Path | str) -> bool:
        return self._files.verify_copy(
            self.database_path,
            Path(backup_path),
        )
