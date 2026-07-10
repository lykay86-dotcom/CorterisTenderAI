"""Резервное копирование, проверка, ротация и восстановление SQLite."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.database.database_locker import DatabaseLocker
from app.database.safe_file_operation import SafeFileOperation
from app.database.session import get_engine

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class BackupRecord:
    """Метаданные резервной копии SQLite."""

    path: Path
    created_at: datetime
    reason: str
    sha256: str
    size_bytes: int

    @property
    def metadata_path(self) -> Path:
        return self.path.with_suffix(".json")


# Совместимость с ранним именем класса.
BackupInfo = BackupRecord


class BackupManager:
    """Создаёт проверяемые резервные копии и безопасно восстанавливает SQLite."""

    def __init__(
        self,
        database_path: Path | str,
        backup_dir: Path | str,
        *,
        keep_last: int = 20,
    ) -> None:
        if keep_last < 1:
            raise ValueError("keep_last должно быть не меньше 1")

        self.database_path = Path(database_path).expanduser().resolve()
        self.backup_dir = Path(backup_dir).expanduser().resolve()
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.keep_last = keep_last
        self._files = SafeFileOperation()
        self._locker = DatabaseLocker(get_engine)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _sqlite_uri(path: Path, *, read_only: bool = False) -> str:
        mode = "?mode=ro" if read_only else ""
        return f"file:{path.as_posix()}{mode}"

    @staticmethod
    def _integrity(path: Path) -> str:
        if not path.is_file():
            return "missing"

        connection = sqlite3.connect(
            BackupManager._sqlite_uri(path, read_only=True),
            uri=True,
            timeout=30,
        )
        try:
            row = connection.execute("PRAGMA integrity_check").fetchone()
            return str(row[0] if row else "unknown")
        finally:
            connection.close()

    def _snapshot(self, source: Path, destination: Path) -> None:
        """Создаёт согласованный снимок SQLite через штатный backup API."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(
            f".{destination.name}.{os.getpid()}.tmp"
        )
        self._files.safe_delete(temporary)

        source_connection = sqlite3.connect(
            self._sqlite_uri(source, read_only=True),
            uri=True,
            timeout=30,
        )
        destination_connection = sqlite3.connect(temporary, timeout=30)
        try:
            source_connection.backup(destination_connection)
            destination_connection.commit()
        finally:
            destination_connection.close()
            source_connection.close()

        integrity = self._integrity(temporary)
        if integrity.lower() != "ok":
            self._files.safe_delete(temporary)
            raise RuntimeError(
                f"Проверка создаваемой копии SQLite завершилась ошибкой: {integrity}"
            )

        self._files.safe_replace(temporary, destination)

    def _restore_sqlite(self, source: Path, destination: Path) -> None:
        """
        Восстанавливает SQLite через sqlite3 backup API.

        На Windows это надёжнее, чем os.replace() поверх существующей базы:
        файловая система может продолжать удерживать дескриптор целевого файла
        даже после dispose() SQLAlchemy Engine.
        """
        destination.parent.mkdir(parents=True, exist_ok=True)

        # Не удаляем -wal и -shm вручную.
        # SQLite управляет этими файлами самостоятельно. На Windows они могут
        # оставаться открытыми ещё некоторое время после dispose(), что приводит
        # к WinError 32/5. Штатный SQLite backup API корректно работает с WAL.
        source_connection = sqlite3.connect(
            self._sqlite_uri(source, read_only=True),
            uri=True,
            timeout=30,
        )
        destination_connection = sqlite3.connect(destination, timeout=30)
        try:
            source_connection.backup(destination_connection)
            destination_connection.commit()
        finally:
            destination_connection.close()
            source_connection.close()

        integrity = self._integrity(destination)
        if integrity.lower() != "ok":
            raise RuntimeError(
                f"Восстановленная база не прошла integrity_check: {integrity}"
            )

    def _write_metadata(self, record: BackupRecord) -> None:
        payload: dict[str, Any] = {
            **asdict(record),
            "path": record.path.name,
            "created_at": record.created_at.isoformat(),
        }
        self._files.safe_write_text(
            record.metadata_path,
            json.dumps(payload, ensure_ascii=False, indent=2),
        )

    @staticmethod
    def _read_metadata(database_file: Path) -> BackupRecord | None:
        metadata = database_file.with_suffix(".json")
        if not metadata.is_file():
            return None
        try:
            payload = json.loads(metadata.read_text(encoding="utf-8"))
            return BackupRecord(
                path=database_file,
                created_at=datetime.fromisoformat(payload["created_at"]),
                reason=str(payload.get("reason", "unknown")),
                sha256=str(payload["sha256"]),
                size_bytes=int(payload["size_bytes"]),
            )
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            logger.exception("Не удалось прочитать метаданные копии %s", database_file)
            return None

    def create(self, reason: str = "manual") -> BackupRecord:
        """Создаёт согласованный снимок базы и JSON с контрольной суммой."""
        if not self.database_path.is_file():
            raise FileNotFoundError(f"База данных не найдена: {self.database_path}")

        created_at = self._now()
        stamp = created_at.strftime("%Y%m%d_%H%M%S_%f")
        target = self.backup_dir / f"corteris_{stamp}_{reason}.db"

        self._snapshot(self.database_path, target)
        record = BackupRecord(
            path=target,
            created_at=created_at,
            reason=reason,
            sha256=self._files.sha256(target),
            size_bytes=target.stat().st_size,
        )
        self._write_metadata(record)
        self._rotate()
        logger.info("Создана резервная копия: %s", target)
        return record

    def list(self) -> list[BackupRecord]:
        """Возвращает резервные копии от новых к старым."""
        records: list[BackupRecord] = []
        for path in self.backup_dir.glob("*.db"):
            record = self._read_metadata(path)
            if record is not None:
                records.append(record)
                continue

            try:
                records.append(
                    BackupRecord(
                        path=path,
                        created_at=datetime.fromtimestamp(
                            path.stat().st_mtime,
                            tz=timezone.utc,
                        ),
                        reason="legacy",
                        sha256=self._files.sha256(path),
                        size_bytes=path.stat().st_size,
                    )
                )
            except OSError:
                logger.exception("Не удалось прочитать резервную копию %s", path)

        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def _rotate(self) -> None:
        records = self.list()
        for record in records[self.keep_last :]:
            self._files.safe_delete(record.path)
            self._files.safe_delete(record.metadata_path)
            logger.info("Удалена старая резервная копия: %s", record.path)

    def verify(self, backup_path: Path | str) -> bool:
        """Проверяет размер, SHA-256 и внутреннюю целостность SQLite."""
        path = Path(backup_path).expanduser().resolve()
        record = self._read_metadata(path)
        if record is None or not path.is_file():
            return False
        try:
            return (
                path.stat().st_size == record.size_bytes
                and self._files.sha256(path) == record.sha256
                and self._integrity(path).lower() == "ok"
            )
        except OSError:
            return False

    def restore(
        self,
        backup_path: Path | str,
        *,
        create_safety_backup: bool = True,
    ) -> Path:
        """Восстанавливает базу через SQLite backup API без файловой замены."""
        source = Path(backup_path).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        if not self.verify(source):
            raise RuntimeError(f"Резервная копия не прошла проверку: {source}")

        safety: BackupRecord | None = None
        if create_safety_backup and self.database_path.is_file():
            safety = self.create(reason="before_restore")

        self._locker.release()

        try:
            self._restore_sqlite(source, self.database_path)
        except Exception:
            logger.exception("Не удалось восстановить базу из %s", source)
            if safety is not None and safety.path.is_file():
                self._locker.release()
                self._restore_sqlite(safety.path, self.database_path)
            raise

        logger.info("База восстановлена из %s", source)
        return self.database_path

    def export_copy(self, destination: Path | str) -> Path:
        """Экспортирует согласованную копию базы в указанный путь."""
        target = Path(destination).expanduser().resolve()
        if target == self.database_path:
            raise ValueError("Путь экспорта совпадает с рабочей базой")
        self._snapshot(self.database_path, target)
        return target
