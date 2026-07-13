"""Catalog and safe file operations for local crash reports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import shutil
from typing import Iterable, Sequence

from app.core.crash_reporting import (
    CrashReportDetails,
    CrashReportInspection,
    CrashReportService,
)


@dataclass(frozen=True, slots=True)
class CrashReportEntry:
    path: Path
    inspection: CrashReportInspection
    details: CrashReportDetails | None
    size_bytes: int
    modified_at: datetime
    managed: bool

    @property
    def valid(self) -> bool:
        return self.inspection.valid and self.details is not None

    @property
    def created_timestamp(self) -> datetime:
        if self.details is not None:
            timestamp = self.details.created_timestamp
            if timestamp is not None:
                return timestamp
        try:
            return datetime.fromisoformat(self.inspection.created_at)
        except (TypeError, ValueError):
            return self.modified_at


class CrashReportCatalogService:
    """Discover, verify, copy and delete .ctcrash files."""

    SUPPORTED_SUFFIXES = {".ctcrash"}
    MAX_REPORTS = 200

    def __init__(
        self,
        report_service: CrashReportService,
    ) -> None:
        self.report_service = report_service

    def list_reports(
        self,
        directories: Sequence[str | Path],
        *,
        external_files: Sequence[str | Path] = (),
    ) -> list[CrashReportEntry]:
        roots = self._unique_paths(directories)
        candidates: dict[str, tuple[Path, bool]] = {}

        for root in roots:
            if not root.is_dir():
                continue
            try:
                children = root.iterdir()
            except OSError:
                continue

            for path in children:
                try:
                    supported = path.is_file() and path.suffix.lower() in self.SUPPORTED_SUFFIXES
                except OSError:
                    continue
                if not supported:
                    continue
                candidates[self._identity(path)] = (path, True)

        for item in external_files:
            path = Path(item).expanduser()
            try:
                supported = path.is_file() and path.suffix.lower() in self.SUPPORTED_SUFFIXES
            except OSError:
                supported = False
            if not supported:
                continue
            candidates[self._identity(path)] = (
                path,
                self._is_under_any(path, roots),
            )

        ordered = sorted(
            candidates.values(),
            key=lambda item: self._safe_mtime(item[0]),
            reverse=True,
        )[: self.MAX_REPORTS]

        entries = [self._entry(path, managed=managed) for path, managed in ordered]
        entries.sort(
            key=lambda entry: (
                entry.valid,
                self._datetime_sort_key(entry.created_timestamp),
                self._datetime_sort_key(entry.modified_at),
                entry.path.name.casefold(),
            ),
            reverse=True,
        )
        return entries

    def refresh_entry(
        self,
        path: str | Path,
        *,
        managed_directories: Sequence[str | Path] = (),
    ) -> CrashReportEntry:
        target = Path(path).expanduser()
        roots = self._unique_paths(managed_directories)
        return self._entry(
            target,
            managed=self._is_under_any(target, roots),
        )

    def copy_report(
        self,
        source: str | Path,
        target: str | Path,
    ) -> Path:
        source_path = Path(source).expanduser()
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        if source_path.suffix.lower() not in self.SUPPORTED_SUFFIXES:
            raise ValueError("Выбранный файл не является crash-report.")

        destination = Path(target).expanduser()
        if destination.suffix.lower() != ".ctcrash":
            destination = destination.with_suffix(".ctcrash")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
        return destination

    def delete_report(
        self,
        source: str | Path,
        *,
        managed_directories: Sequence[str | Path],
        allow_external: bool = False,
    ) -> Path:
        path = Path(source).expanduser()
        roots = self._unique_paths(managed_directories)

        if not path.is_file():
            raise FileNotFoundError(path)
        if path.suffix.lower() not in self.SUPPORTED_SUFFIXES:
            raise ValueError("Можно удалять только файлы .ctcrash.")
        if not allow_external and not self._is_under_any(path, roots):
            raise PermissionError(
                "Внешний crash-report нельзя удалить без отдельного подтверждения."
            )

        path.unlink()
        return path

    def _entry(
        self,
        path: Path,
        *,
        managed: bool,
    ) -> CrashReportEntry:
        stat = path.stat()
        inspection = self.report_service.inspect_report(path)
        details: CrashReportDetails | None = None

        if inspection.valid:
            try:
                details = self.report_service.read_report(path)
            except Exception:
                # Keep the file visible as invalid if its verified content
                # still cannot be decoded into supported report details.
                inspection = CrashReportInspection(
                    path=inspection.path,
                    valid=False,
                    crash_id=inspection.crash_id,
                    created_at=inspection.created_at,
                    file_count=inspection.file_count,
                    errors=(
                        *inspection.errors,
                        "Не удалось прочитать содержимое crash-report.",
                    ),
                )

        return CrashReportEntry(
            path=path,
            inspection=inspection,
            details=details,
            size_bytes=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime),
            managed=managed,
        )

    @staticmethod
    def _unique_paths(
        paths: Iterable[str | Path],
    ) -> tuple[Path, ...]:
        result: list[Path] = []
        seen: set[str] = set()
        for item in paths:
            path = Path(item).expanduser()
            identity = CrashReportCatalogService._identity(path)
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

    @staticmethod
    def _datetime_sort_key(
        value: datetime,
    ) -> tuple[int, int, int, int, int, int, int]:
        """Return a comparable key for naive and timezone-aware values."""

        normalized = value
        if normalized.tzinfo is not None:
            normalized = normalized.astimezone(timezone.utc).replace(tzinfo=None)
        return (
            normalized.year,
            normalized.month,
            normalized.day,
            normalized.hour,
            normalized.minute,
            normalized.second,
            normalized.microsecond,
        )

    @staticmethod
    def _safe_mtime(path: Path) -> int:
        try:
            return path.stat().st_mtime_ns
        except OSError:
            return 0


__all__ = [
    "CrashReportCatalogService",
    "CrashReportEntry",
]
