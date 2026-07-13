"""Safe extraction of tender archives without executing their contents."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import os
from pathlib import Path, PurePosixPath
import stat
from typing import Iterable
from zipfile import BadZipFile, ZipFile, ZipInfo, is_zipfile


class ArchiveMemberStatus(StrEnum):
    EXTRACTED = "extracted"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ArchiveMemberResult:
    archive_path: Path
    member_name: str
    status: ArchiveMemberStatus
    output_path: Path | None = None
    size_bytes: int = 0
    message: str = ""
    depth: int = 0


@dataclass(frozen=True, slots=True)
class SafeArchiveExtractionResult:
    archives_processed: tuple[Path, ...]
    members: tuple[ArchiveMemberResult, ...]
    extracted_files: tuple[Path, ...]
    total_extracted_bytes: int
    warnings: tuple[str, ...] = ()

    @property
    def extracted_count(self) -> int:
        return sum(item.status == ArchiveMemberStatus.EXTRACTED for item in self.members)

    @property
    def blocked_count(self) -> int:
        return sum(item.status == ArchiveMemberStatus.BLOCKED for item in self.members)

    @property
    def failed_count(self) -> int:
        return sum(item.status == ArchiveMemberStatus.FAILED for item in self.members)


class UnsafeArchiveError(RuntimeError):
    """Raised when archive limits or path-safety rules are violated."""


@dataclass(slots=True)
class _ExtractionState:
    members: list[ArchiveMemberResult]
    archives: list[Path]
    extracted_files: list[Path]
    warnings: list[str]
    total_bytes: int = 0
    entry_count: int = 0


class SafeArchiveExtractor:
    """Extract ZIP archives with traversal, bomb and executable protections.

    RAR and 7Z are intentionally not extracted without optional, explicitly
    installed libraries. They are reported as unsupported rather than silently
    ignored or processed by an external executable.
    """

    ARCHIVE_SUFFIXES = {".zip", ".rar", ".7z"}
    BLOCKED_SUFFIXES = {
        ".exe",
        ".dll",
        ".com",
        ".bat",
        ".cmd",
        ".ps1",
        ".psm1",
        ".vbs",
        ".vbe",
        ".js",
        ".jse",
        ".msi",
        ".msp",
        ".scr",
        ".cpl",
        ".jar",
        ".lnk",
        ".hta",
        ".reg",
        ".sys",
    }

    def __init__(
        self,
        *,
        max_entries: int = 500,
        max_member_bytes: int = 100 * 1024 * 1024,
        max_total_bytes: int = 500 * 1024 * 1024,
        max_compression_ratio: float = 200.0,
        max_depth: int = 2,
        chunk_size: int = 1024 * 1024,
    ) -> None:
        if max_entries < 1 or max_member_bytes < 1 or max_total_bytes < 1:
            raise ValueError("archive limits must be positive")
        if max_compression_ratio <= 1:
            raise ValueError("max_compression_ratio must be greater than 1")
        if max_depth < 0 or chunk_size < 4096:
            raise ValueError("invalid archive depth or chunk size")
        self.max_entries = int(max_entries)
        self.max_member_bytes = int(max_member_bytes)
        self.max_total_bytes = int(max_total_bytes)
        self.max_compression_ratio = float(max_compression_ratio)
        self.max_depth = int(max_depth)
        self.chunk_size = int(chunk_size)

    def extract_many(
        self,
        archives: Iterable[str | Path],
        destination_root: str | Path,
    ) -> SafeArchiveExtractionResult:
        root = Path(destination_root).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        state = _ExtractionState([], [], [], [])

        for source_value in archives:
            source = Path(source_value).expanduser()
            if not source.is_file():
                state.warnings.append(f"Архив отсутствует: {source}")
                continue
            suffix = source.suffix.casefold()
            if suffix in {".rar", ".7z"}:
                state.warnings.append(
                    f"Формат {suffix.upper()} не распакован: безопасная "
                    "опциональная библиотека не подключена."
                )
                continue
            if suffix != ".zip" and not is_zipfile(source):
                continue
            folder = root / _safe_component(source.stem)
            folder.mkdir(parents=True, exist_ok=True)
            self._extract_zip(source, folder, depth=0, state=state)

        return SafeArchiveExtractionResult(
            archives_processed=tuple(state.archives),
            members=tuple(state.members),
            extracted_files=tuple(_unique_paths(state.extracted_files)),
            total_extracted_bytes=state.total_bytes,
            warnings=tuple(_ordered_unique(state.warnings)),
        )

    def _extract_zip(
        self,
        archive_path: Path,
        destination: Path,
        *,
        depth: int,
        state: _ExtractionState,
    ) -> None:
        if depth > self.max_depth:
            state.warnings.append(f"Превышена глубина вложенности архива: {archive_path.name}")
            return
        try:
            archive = ZipFile(archive_path)
        except (BadZipFile, OSError) as exc:
            state.warnings.append(f"Не удалось открыть ZIP {archive_path.name}: {exc}")
            return

        state.archives.append(archive_path.resolve())
        destination = destination.resolve()
        destination.mkdir(parents=True, exist_ok=True)

        seen_member_paths: set[str] = set()
        with archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                state.entry_count += 1
                if state.entry_count > self.max_entries:
                    raise UnsafeArchiveError(f"Архив содержит более {self.max_entries} файлов")
                safe_relative, reason = _safe_member_path(info.filename)
                if safe_relative is None:
                    state.members.append(
                        ArchiveMemberResult(
                            archive_path=archive_path,
                            member_name=info.filename,
                            status=ArchiveMemberStatus.BLOCKED,
                            message=reason,
                            depth=depth,
                        )
                    )
                    continue
                if _is_symlink(info):
                    state.members.append(
                        ArchiveMemberResult(
                            archive_path=archive_path,
                            member_name=info.filename,
                            status=ArchiveMemberStatus.BLOCKED,
                            message="Символические ссылки запрещены",
                            depth=depth,
                        )
                    )
                    continue
                suffix = safe_relative.suffix.casefold()
                if suffix in self.BLOCKED_SUFFIXES:
                    state.members.append(
                        ArchiveMemberResult(
                            archive_path=archive_path,
                            member_name=info.filename,
                            status=ArchiveMemberStatus.BLOCKED,
                            message="Исполняемый или сценарный файл запрещён",
                            depth=depth,
                        )
                    )
                    continue
                reason = self._validate_sizes(info, state.total_bytes)
                if reason:
                    state.members.append(
                        ArchiveMemberResult(
                            archive_path=archive_path,
                            member_name=info.filename,
                            status=ArchiveMemberStatus.BLOCKED,
                            message=reason,
                            depth=depth,
                        )
                    )
                    continue

                member_key = safe_relative.as_posix().casefold()
                if member_key in seen_member_paths:
                    state.members.append(
                        ArchiveMemberResult(
                            archive_path=archive_path,
                            member_name=info.filename,
                            status=ArchiveMemberStatus.BLOCKED,
                            message="Дублирующее имя файла в архиве",
                            depth=depth,
                        )
                    )
                    continue
                seen_member_paths.add(member_key)

                target = (destination / safe_relative).resolve()
                if not _is_relative_to(target, destination):
                    state.members.append(
                        ArchiveMemberResult(
                            archive_path=archive_path,
                            member_name=info.filename,
                            status=ArchiveMemberStatus.BLOCKED,
                            message="Путь выходит за каталог распаковки",
                            depth=depth,
                        )
                    )
                    continue

                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_name(f".{target.name}.part")
                written = 0
                try:
                    with archive.open(info, "r") as source, temporary.open("wb") as output:
                        while True:
                            chunk = source.read(self.chunk_size)
                            if not chunk:
                                break
                            written += len(chunk)
                            if written > self.max_member_bytes:
                                raise UnsafeArchiveError(
                                    "Файл превысил допустимый размер во время распаковки"
                                )
                            if state.total_bytes + written > self.max_total_bytes:
                                raise UnsafeArchiveError("Превышен общий лимит распаковки")
                            output.write(chunk)
                    os.replace(temporary, target)
                except Exception as exc:
                    temporary.unlink(missing_ok=True)
                    state.members.append(
                        ArchiveMemberResult(
                            archive_path=archive_path,
                            member_name=info.filename,
                            status=ArchiveMemberStatus.FAILED,
                            message=str(exc),
                            depth=depth,
                        )
                    )
                    continue

                state.total_bytes += written
                state.extracted_files.append(target)
                state.members.append(
                    ArchiveMemberResult(
                        archive_path=archive_path,
                        member_name=info.filename,
                        status=ArchiveMemberStatus.EXTRACTED,
                        output_path=target,
                        size_bytes=written,
                        depth=depth,
                    )
                )

                if target.suffix.casefold() == ".zip":
                    if depth >= self.max_depth:
                        state.warnings.append(
                            f"Вложенный ZIP не распакован из-за лимита глубины: {target.name}"
                        )
                    elif is_zipfile(target):
                        nested = target.parent / f"{target.stem}_extracted"
                        self._extract_zip(target, nested, depth=depth + 1, state=state)

    def _validate_sizes(self, info: ZipInfo, current_total: int) -> str:
        if info.file_size < 0 or info.compress_size < 0:
            return "Некорректный размер ZIP-записи"
        if info.file_size > self.max_member_bytes:
            return f"Файл больше лимита {self.max_member_bytes} байт"
        if current_total + info.file_size > self.max_total_bytes:
            return "Превышен общий лимит распаковки"
        if info.file_size > 0:
            if info.compress_size <= 0:
                return "Подозрительная нулевая сжатая длина"
            ratio = info.file_size / info.compress_size
            if ratio > self.max_compression_ratio:
                return f"Подозрительный коэффициент сжатия {ratio:.1f}"
        return ""


def _safe_member_path(value: str) -> tuple[Path | None, str]:
    raw = value.replace("\\", "/").replace("\x00", "")
    path = PurePosixPath(raw)
    if not raw.strip():
        return None, "Пустое имя файла"
    if path.is_absolute() or raw.startswith(("/", "\\")):
        return None, "Абсолютные пути запрещены"
    if re_drive(raw):
        return None, "Путь с буквой диска запрещён"
    if any(part in {"", ".", ".."} for part in path.parts):
        return None, "Переходы по каталогам запрещены"
    safe_parts = [_safe_component(part) for part in path.parts]
    if not safe_parts:
        return None, "Некорректное имя файла"
    return Path(*safe_parts), ""


def re_drive(value: str) -> bool:
    return len(value) >= 2 and value[1] == ":" and value[0].isalpha()


def _is_symlink(info: ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0xFFFF
    return stat.S_IFMT(mode) == stat.S_IFLNK


def _safe_component(value: str) -> str:
    rendered = "".join("_" if char in '<>:"/\\|?*' or ord(char) < 32 else char for char in value)
    rendered = " ".join(rendered.split()).strip(" .")
    return (rendered or "file")[:160]


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _unique_paths(values: Iterable[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for value in values:
        key = os.path.normcase(str(value.resolve()))
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _ordered_unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        rendered = str(value).strip()
        key = rendered.casefold()
        if not rendered or key in seen:
            continue
        seen.add(key)
        result.append(rendered)
    return result


__all__ = [
    "ArchiveMemberResult",
    "ArchiveMemberStatus",
    "SafeArchiveExtractionResult",
    "SafeArchiveExtractor",
    "UnsafeArchiveError",
]
