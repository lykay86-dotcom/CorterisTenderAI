"""Catalog and safe file operations for workflow backups."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Iterable, Sequence

from app.core.workflow_backup import (
    WorkflowBackupInspection,
    WorkflowBackupService,
)


class WorkflowBackupKind(StrEnum):
    MANUAL = "manual"
    AUTOMATIC = "automatic"
    SAFETY = "safety"
    EXTERNAL = "external"


@dataclass(frozen=True, slots=True)
class WorkflowBackupEntry:
    path: Path
    inspection: WorkflowBackupInspection
    kind: WorkflowBackupKind
    size_bytes: int
    modified_at: datetime
    managed: bool

    @property
    def valid(self) -> bool:
        return self.inspection.valid

    @property
    def display_kind(self) -> str:
        return {
            WorkflowBackupKind.MANUAL: "Ручная",
            WorkflowBackupKind.AUTOMATIC: "Автоматическая",
            WorkflowBackupKind.SAFETY: "Страховочная",
            WorkflowBackupKind.EXTERNAL: "Внешняя",
        }[self.kind]

    @property
    def created_timestamp(self) -> datetime:
        return self.inspection.created_timestamp or self.modified_at


class WorkflowBackupCatalogService:
    """Scan backup folders, verify files and delete managed copies."""

    SUPPORTED_SUFFIXES = {".ctbackup", ".zip"}
    AUTOMATIC_PREFIX = "CORTERIS_auto_"
    SAFETY_PREFIX = "CORTERIS_auto_before_restore_"

    def __init__(
        self,
        backup_service: WorkflowBackupService | None = None,
    ) -> None:
        self.backup_service = backup_service or WorkflowBackupService()

    def list_backups(
        self,
        directories: Sequence[str | Path],
        *,
        external_files: Sequence[str | Path] = (),
    ) -> list[WorkflowBackupEntry]:
        roots = self._normalized_roots(directories)
        candidates: dict[str, tuple[Path, bool]] = {}

        for root in roots:
            if not root.is_dir():
                continue
            for path in root.rglob("*"):
                if path.is_file() and path.suffix.lower() in self.SUPPORTED_SUFFIXES:
                    candidates[self._identity(path)] = (path, True)

        for item in external_files:
            path = Path(item).expanduser()
            if path.is_file() and path.suffix.lower() in self.SUPPORTED_SUFFIXES:
                candidates[self._identity(path)] = (
                    path,
                    self._is_under_any(path, roots),
                )

        entries = [self._entry(path, managed=managed) for path, managed in candidates.values()]
        entries.sort(
            key=lambda entry: (
                entry.created_timestamp,
                entry.modified_at,
                entry.path.name.lower(),
            ),
            reverse=True,
        )
        return entries

    def refresh_entry(
        self,
        path: str | Path,
        *,
        managed_directories: Sequence[str | Path] = (),
    ) -> WorkflowBackupEntry:
        target = Path(path).expanduser()
        roots = self._normalized_roots(managed_directories)
        return self._entry(
            target,
            managed=self._is_under_any(target, roots),
        )

    def delete_backup(
        self,
        path: str | Path,
        *,
        managed_directories: Sequence[str | Path],
        allow_external: bool = False,
    ) -> Path:
        target = Path(path).expanduser()
        roots = self._normalized_roots(managed_directories)

        if not target.is_file():
            raise FileNotFoundError(target)
        if target.suffix.lower() not in self.SUPPORTED_SUFFIXES:
            raise ValueError("Можно удалять только файлы резервных копий.")
        if not allow_external and not self._is_under_any(
            target,
            roots,
        ):
            raise PermissionError("Внешний файл нельзя удалить без явного разрешения.")

        target.unlink()
        return target

    def classify(
        self,
        path: str | Path,
        *,
        managed: bool,
    ) -> WorkflowBackupKind:
        name = Path(path).name
        if name.startswith(self.SAFETY_PREFIX):
            return WorkflowBackupKind.SAFETY
        if name.startswith(self.AUTOMATIC_PREFIX):
            return WorkflowBackupKind.AUTOMATIC
        if not managed:
            return WorkflowBackupKind.EXTERNAL
        return WorkflowBackupKind.MANUAL

    def _entry(
        self,
        path: Path,
        *,
        managed: bool,
    ) -> WorkflowBackupEntry:
        stat = path.stat()
        inspection = self.backup_service.inspect_backup(path)
        return WorkflowBackupEntry(
            path=path,
            inspection=inspection,
            kind=self.classify(path, managed=managed),
            size_bytes=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime),
            managed=managed,
        )

    @staticmethod
    def _normalized_roots(
        directories: Iterable[str | Path],
    ) -> tuple[Path, ...]:
        result: list[Path] = []
        seen: set[str] = set()
        for item in directories:
            path = Path(item).expanduser()
            identity = WorkflowBackupCatalogService._identity(path)
            if identity in seen:
                continue
            seen.add(identity)
            result.append(path)
        return tuple(result)

    @staticmethod
    def _is_under_any(
        path: Path,
        roots: Sequence[Path],
    ) -> bool:
        resolved = path.resolve(strict=False)
        return any(resolved.is_relative_to(root.resolve(strict=False)) for root in roots)

    @staticmethod
    def _identity(path: Path) -> str:
        return str(path.resolve(strict=False)).casefold()


__all__ = [
    "WorkflowBackupCatalogService",
    "WorkflowBackupEntry",
    "WorkflowBackupKind",
]
