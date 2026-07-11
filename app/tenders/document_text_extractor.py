"""Local text extraction for downloaded tender documents.

The extractor intentionally performs no OCR and no network requests. It reads
already-downloaded files from :mod:`app.tenders.document_storage`, extracts
machine-readable text and persists normalized UTF-8 text for later analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from io import BytesIO
import hashlib
import importlib
from pathlib import Path, PurePosixPath
import re
import sqlite3
from threading import RLock
from typing import BinaryIO, Callable, Iterable, Sequence
import xml.etree.ElementTree as ET
from zipfile import BadZipFile, ZipFile

from app.tenders.document_storage import (
    StoredTenderDocument,
    TenderDocumentStore,
)


class TextExtractionStatus(StrEnum):
    EXTRACTED = "extracted"
    REUSED = "reused"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ExtractedTextSection:
    label: str
    text: str
    source_name: str = ""

    @property
    def character_count(self) -> int:
        return len(self.text)


@dataclass(frozen=True, slots=True)
class RawTextExtraction:
    source_name: str
    document_format: str
    status: TextExtractionStatus
    text: str
    sections: tuple[ExtractedTextSection, ...] = ()
    warnings: tuple[str, ...] = ()
    error_message: str = ""

    @property
    def character_count(self) -> int:
        return len(self.text)


@dataclass(frozen=True, slots=True)
class StoredDocumentText:
    extraction_key: str
    document_key: str
    registry_key: str
    source_path: Path | None
    text_path: Path | None
    document_format: str
    status: TextExtractionStatus
    checksum_sha256: str
    character_count: int
    section_count: int
    extracted_at: str
    warnings: tuple[str, ...] = ()
    error_message: str = ""

    @property
    def available_locally(self) -> bool:
        return (
            self.text_path is not None
            and self.text_path.is_file()
            and self.status
            in {
                TextExtractionStatus.EXTRACTED,
                TextExtractionStatus.REUSED,
                TextExtractionStatus.PARTIAL,
            }
        )


@dataclass(frozen=True, slots=True)
class TenderTextExtractionResult:
    registry_key: str
    documents: tuple[StoredDocumentText, ...]

    @property
    def extracted_count(self) -> int:
        return sum(
            item.status == TextExtractionStatus.EXTRACTED
            for item in self.documents
        )

    @property
    def reused_count(self) -> int:
        return sum(
            item.status == TextExtractionStatus.REUSED
            for item in self.documents
        )

    @property
    def partial_count(self) -> int:
        return sum(
            item.status == TextExtractionStatus.PARTIAL
            for item in self.documents
        )

    @property
    def unsupported_count(self) -> int:
        return sum(
            item.status == TextExtractionStatus.UNSUPPORTED
            for item in self.documents
        )

    @property
    def failed_count(self) -> int:
        return sum(
            item.status == TextExtractionStatus.FAILED
            for item in self.documents
        )

    @property
    def total_character_count(self) -> int:
        return sum(item.character_count for item in self.documents)


class UnsupportedDocumentFormatError(RuntimeError):
    """Raised when no safe parser exists for a document format."""


PdfReaderFactory = Callable[[BinaryIO], object]


class TenderDocumentTextExtractor:
    """Extract text from PDF, DOCX, XLSX, TXT and ZIP documents."""

    TEXT_SUFFIXES = {
        ".txt",
        ".md",
        ".csv",
        ".log",
        ".json",
        ".xml",
    }
    SUPPORTED_SUFFIXES = TEXT_SUFFIXES | {
        ".pdf",
        ".docx",
        ".xlsx",
        ".zip",
    }

    def __init__(
        self,
        *,
        max_input_bytes: int = 250 * 1024 * 1024,
        max_text_characters: int = 8_000_000,
        max_archive_entries: int = 300,
        max_archive_uncompressed_bytes: int = 200 * 1024 * 1024,
        max_archive_depth: int = 2,
        pdf_reader_factory: PdfReaderFactory | None = None,
    ) -> None:
        if max_input_bytes < 1024:
            raise ValueError("max_input_bytes must be at least 1024")
        if max_text_characters < 1000:
            raise ValueError(
                "max_text_characters must be at least 1000"
            )
        if max_archive_entries < 1:
            raise ValueError("max_archive_entries must be positive")
        if max_archive_uncompressed_bytes < 1024:
            raise ValueError(
                "max_archive_uncompressed_bytes must be at least 1024"
            )
        if max_archive_depth < 0:
            raise ValueError(
                "max_archive_depth must be non-negative"
            )

        self.max_input_bytes = int(max_input_bytes)
        self.max_text_characters = int(max_text_characters)
        self.max_archive_entries = int(max_archive_entries)
        self.max_archive_uncompressed_bytes = int(
            max_archive_uncompressed_bytes
        )
        self.max_archive_depth = int(max_archive_depth)
        self._pdf_reader_factory = pdf_reader_factory

    def extract_file(self, path: str | Path) -> RawTextExtraction:
        source = Path(path).expanduser()
        if not source.is_file():
            return RawTextExtraction(
                source_name=source.name,
                document_format=source.suffix.lower().lstrip("."),
                status=TextExtractionStatus.FAILED,
                text="",
                error_message=f"Файл не найден: {source}",
            )

        try:
            size = source.stat().st_size
        except OSError as exc:
            return RawTextExtraction(
                source_name=source.name,
                document_format=source.suffix.lower().lstrip("."),
                status=TextExtractionStatus.FAILED,
                text="",
                error_message=str(exc),
            )

        if size > self.max_input_bytes:
            return RawTextExtraction(
                source_name=source.name,
                document_format=source.suffix.lower().lstrip("."),
                status=TextExtractionStatus.FAILED,
                text="",
                error_message=(
                    "Файл превышает безопасный лимит извлечения: "
                    f"{size} байт"
                ),
            )

        try:
            payload = source.read_bytes()
        except OSError as exc:
            return RawTextExtraction(
                source_name=source.name,
                document_format=source.suffix.lower().lstrip("."),
                status=TextExtractionStatus.FAILED,
                text="",
                error_message=str(exc),
            )

        return self.extract_bytes(
            payload,
            source_name=source.name,
            archive_depth=0,
        )

    def extract_bytes(
        self,
        payload: bytes,
        *,
        source_name: str,
        archive_depth: int = 0,
    ) -> RawTextExtraction:
        suffix = Path(source_name).suffix.lower()
        document_format = suffix.lstrip(".") or "unknown"

        if len(payload) > self.max_input_bytes:
            return RawTextExtraction(
                source_name=source_name,
                document_format=document_format,
                status=TextExtractionStatus.FAILED,
                text="",
                error_message=(
                    "Документ превышает безопасный лимит извлечения"
                ),
            )

        try:
            if suffix in self.TEXT_SUFFIXES:
                raw = self._extract_textual(payload, source_name)
            elif suffix == ".docx":
                raw = self._extract_docx(payload, source_name)
            elif suffix == ".xlsx":
                raw = self._extract_xlsx(payload, source_name)
            elif suffix == ".pdf":
                raw = self._extract_pdf(payload, source_name)
            elif suffix == ".zip":
                raw = self._extract_zip(
                    payload,
                    source_name,
                    archive_depth=archive_depth,
                )
            else:
                raise UnsupportedDocumentFormatError(
                    f"Формат {suffix or '<без расширения>'} "
                    "не поддерживается"
                )
        except UnsupportedDocumentFormatError as exc:
            return RawTextExtraction(
                source_name=source_name,
                document_format=document_format,
                status=TextExtractionStatus.UNSUPPORTED,
                text="",
                error_message=str(exc),
            )
        except (
            BadZipFile,
            ET.ParseError,
            OSError,
            RuntimeError,
            ValueError,
            IndexError,
            KeyError,
        ) as exc:
            return RawTextExtraction(
                source_name=source_name,
                document_format=document_format,
                status=TextExtractionStatus.FAILED,
                text="",
                error_message=f"{type(exc).__name__}: {exc}",
            )

        return self._truncate(raw)

    def _extract_textual(
        self,
        payload: bytes,
        source_name: str,
    ) -> RawTextExtraction:
        suffix = Path(source_name).suffix.lower()
        decoded, encoding = _decode_text(payload)
        warnings: list[str] = []

        if suffix == ".xml":
            try:
                root = ET.fromstring(decoded)
                decoded = "\n".join(
                    part.strip()
                    for part in root.itertext()
                    if part.strip()
                )
            except ET.ParseError:
                warnings.append(
                    "XML не разобран как структура; использован исходный текст."
                )

        text = _normalize_text(decoded)
        return RawTextExtraction(
            source_name=source_name,
            document_format=suffix.lstrip("."),
            status=TextExtractionStatus.EXTRACTED,
            text=text,
            sections=(
                ExtractedTextSection(
                    label="Документ",
                    text=text,
                    source_name=source_name,
                ),
            ),
            warnings=tuple(
                (
                    f"Определена кодировка: {encoding}",
                    *warnings,
                )
            ),
        )

    def _extract_docx(
        self,
        payload: bytes,
        source_name: str,
    ) -> RawTextExtraction:
        sections: list[ExtractedTextSection] = []
        warnings: list[str] = []

        with ZipFile(BytesIO(payload)) as archive:
            names = set(archive.namelist())
            preferred = ["word/document.xml"]
            preferred.extend(
                sorted(
                    name
                    for name in names
                    if re.fullmatch(
                        r"word/(header|footer)\d+\.xml",
                        name,
                    )
                )
            )
            preferred.extend(
                name
                for name in (
                    "word/footnotes.xml",
                    "word/endnotes.xml",
                    "word/comments.xml",
                )
                if name in names
            )

            for member in preferred:
                if member not in names:
                    continue
                xml_payload = archive.read(member)
                section_text = _word_xml_text(xml_payload)
                if not section_text:
                    continue
                sections.append(
                    ExtractedTextSection(
                        label=_docx_section_label(member),
                        text=section_text,
                        source_name=member,
                    )
                )

        if not sections:
            warnings.append(
                "В DOCX не найден извлекаемый текст."
            )

        text = _join_sections(sections)
        return RawTextExtraction(
            source_name=source_name,
            document_format="docx",
            status=(
                TextExtractionStatus.EXTRACTED
                if text
                else TextExtractionStatus.PARTIAL
            ),
            text=text,
            sections=tuple(sections),
            warnings=tuple(warnings),
        )

    def _extract_xlsx(
        self,
        payload: bytes,
        source_name: str,
    ) -> RawTextExtraction:
        sections: list[ExtractedTextSection] = []
        warnings: list[str] = []

        with ZipFile(BytesIO(payload)) as archive:
            names = set(archive.namelist())
            shared_strings = _xlsx_shared_strings(archive, names)
            sheets = _xlsx_sheet_paths(archive, names)

            if not sheets:
                worksheet_names = sorted(
                    name
                    for name in names
                    if re.fullmatch(
                        r"xl/worksheets/sheet\d+\.xml",
                        name,
                    )
                )
                sheets = tuple(
                    (Path(name).stem, name)
                    for name in worksheet_names
                )

            for sheet_name, member in sheets:
                if member not in names:
                    warnings.append(
                        f"Лист {sheet_name}: XML-файл не найден."
                    )
                    continue
                text = _xlsx_sheet_text(
                    archive.read(member),
                    shared_strings,
                )
                if not text:
                    continue
                sections.append(
                    ExtractedTextSection(
                        label=f"Лист: {sheet_name}",
                        text=text,
                        source_name=member,
                    )
                )

        if not sections:
            warnings.append(
                "В XLSX не найдено извлекаемых значений."
            )

        text = _join_sections(sections)
        return RawTextExtraction(
            source_name=source_name,
            document_format="xlsx",
            status=(
                TextExtractionStatus.EXTRACTED
                if text
                else TextExtractionStatus.PARTIAL
            ),
            text=text,
            sections=tuple(sections),
            warnings=tuple(warnings),
        )

    def _extract_pdf(
        self,
        payload: bytes,
        source_name: str,
    ) -> RawTextExtraction:
        factory = (
            self._pdf_reader_factory
            or _discover_pdf_reader_factory()
        )
        if factory is None:
            raise UnsupportedDocumentFormatError(
                "Для извлечения PDF установите пакет pypdf "
                "(или PyPDF2). OCR в этом модуле не выполняется."
            )

        reader = factory(BytesIO(payload))
        if getattr(reader, "is_encrypted", False):
            decrypt = getattr(reader, "decrypt", None)
            if callable(decrypt):
                try:
                    decrypted = decrypt("")
                except Exception as exc:
                    raise RuntimeError(
                        "PDF защищён паролем"
                    ) from exc
                if not decrypted:
                    raise RuntimeError("PDF защищён паролем")

        sections: list[ExtractedTextSection] = []
        warnings: list[str] = []
        pages = tuple(getattr(reader, "pages", ()))

        for index, page in enumerate(pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception as exc:
                warnings.append(
                    f"Страница {index}: {type(exc).__name__}: {exc}"
                )
                continue
            normalized = _normalize_text(text)
            if not normalized:
                warnings.append(
                    f"Страница {index}: текстовый слой отсутствует."
                )
                continue
            sections.append(
                ExtractedTextSection(
                    label=f"Страница {index}",
                    text=normalized,
                    source_name=source_name,
                )
            )

        text = _join_sections(sections)
        status = TextExtractionStatus.EXTRACTED
        if warnings:
            status = TextExtractionStatus.PARTIAL
        if not text:
            status = TextExtractionStatus.PARTIAL
            warnings.append(
                "PDF не содержит читаемого текстового слоя. "
                "Для скан-копий потребуется отдельный OCR-модуль."
            )

        return RawTextExtraction(
            source_name=source_name,
            document_format="pdf",
            status=status,
            text=text,
            sections=tuple(sections),
            warnings=tuple(_ordered_unique(warnings)),
        )

    def _extract_zip(
        self,
        payload: bytes,
        source_name: str,
        *,
        archive_depth: int,
    ) -> RawTextExtraction:
        if archive_depth >= self.max_archive_depth:
            raise UnsupportedDocumentFormatError(
                "Достигнут предел вложенности ZIP-архивов"
            )

        sections: list[ExtractedTextSection] = []
        warnings: list[str] = []
        total_uncompressed = 0
        processed_entries = 0

        with ZipFile(BytesIO(payload)) as archive:
            members = archive.infolist()
            if len(members) > self.max_archive_entries:
                warnings.append(
                    "Архив содержит слишком много элементов; "
                    f"обработаны первые {self.max_archive_entries}."
                )
                members = members[: self.max_archive_entries]

            for member in members:
                if member.is_dir():
                    continue
                if not _safe_archive_member(member.filename):
                    warnings.append(
                        f"Пропущен небезопасный путь: {member.filename}"
                    )
                    continue

                total_uncompressed += max(0, int(member.file_size))
                if (
                    total_uncompressed
                    > self.max_archive_uncompressed_bytes
                ):
                    warnings.append(
                        "Достигнут лимит распакованного объёма ZIP."
                    )
                    break

                suffix = Path(member.filename).suffix.lower()
                if suffix not in self.SUPPORTED_SUFFIXES:
                    warnings.append(
                        f"Пропущен неподдерживаемый файл: "
                        f"{member.filename}"
                    )
                    continue

                member_payload = archive.read(member)
                child = self.extract_bytes(
                    member_payload,
                    source_name=member.filename,
                    archive_depth=archive_depth + 1,
                )
                processed_entries += 1

                if child.text:
                    sections.append(
                        ExtractedTextSection(
                            label=f"Файл: {member.filename}",
                            text=child.text,
                            source_name=member.filename,
                        )
                    )
                warnings.extend(
                    f"{member.filename}: {warning}"
                    for warning in child.warnings
                )
                if child.error_message:
                    warnings.append(
                        f"{member.filename}: {child.error_message}"
                    )

        text = _join_sections(sections)
        status = TextExtractionStatus.EXTRACTED
        if warnings or not text:
            status = TextExtractionStatus.PARTIAL

        if processed_entries == 0:
            warnings.append(
                "В ZIP не найдено поддерживаемых документов."
            )

        return RawTextExtraction(
            source_name=source_name,
            document_format="zip",
            status=status,
            text=text,
            sections=tuple(sections),
            warnings=tuple(_ordered_unique(warnings)),
        )

    def _truncate(
        self,
        extraction: RawTextExtraction,
    ) -> RawTextExtraction:
        if len(extraction.text) <= self.max_text_characters:
            return extraction

        warning = (
            "Текст сокращён до безопасного лимита "
            f"{self.max_text_characters} символов."
        )
        return RawTextExtraction(
            source_name=extraction.source_name,
            document_format=extraction.document_format,
            status=TextExtractionStatus.PARTIAL,
            text=extraction.text[: self.max_text_characters],
            sections=extraction.sections,
            warnings=tuple(
                _ordered_unique((*extraction.warnings, warning))
            ),
            error_message=extraction.error_message,
        )


class TenderDocumentTextService:
    """Persist extracted text and reuse unchanged extraction results."""

    SCHEMA_VERSION = 1

    def __init__(
        self,
        document_store: TenderDocumentStore,
        output_directory: str | Path,
        *,
        extractor: TenderDocumentTextExtractor | None = None,
        catalog_path: str | Path | None = None,
    ) -> None:
        self.document_store = document_store
        self.output_directory = Path(output_directory).expanduser()
        self.output_directory.mkdir(parents=True, exist_ok=True)
        self.catalog_path = (
            Path(catalog_path).expanduser()
            if catalog_path is not None
            else self.output_directory / "text_catalog.sqlite3"
        )
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        self.extractor = extractor or TenderDocumentTextExtractor()
        self._lock = RLock()

    def initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS extracted_text_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS extracted_document_text (
                    extraction_key TEXT PRIMARY KEY,
                    document_key TEXT NOT NULL,
                    registry_key TEXT NOT NULL,
                    source_path TEXT NOT NULL DEFAULT '',
                    text_path TEXT NOT NULL DEFAULT '',
                    document_format TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    checksum_sha256 TEXT NOT NULL DEFAULT '',
                    character_count INTEGER NOT NULL DEFAULT 0,
                    section_count INTEGER NOT NULL DEFAULT 0,
                    warnings TEXT NOT NULL DEFAULT '',
                    error_message TEXT NOT NULL DEFAULT '',
                    extracted_at TEXT NOT NULL,
                    UNIQUE(document_key, checksum_sha256)
                );

                CREATE INDEX IF NOT EXISTS idx_extracted_text_registry
                    ON extracted_document_text(registry_key, extracted_at);
                CREATE INDEX IF NOT EXISTS idx_extracted_text_status
                    ON extracted_document_text(status);
                """
            )
            connection.execute(
                """
                INSERT INTO extracted_text_meta(key, value)
                VALUES('schema_version', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (str(self.SCHEMA_VERSION),),
            )

    def extract_document(
        self,
        document: StoredTenderDocument,
        *,
        force: bool = False,
    ) -> StoredDocumentText:
        self.initialize()

        if not document.available_locally or document.local_path is None:
            return self._record_result(
                document,
                RawTextExtraction(
                    source_name=document.name,
                    document_format=(
                        Path(document.name).suffix.lower().lstrip(".")
                    ),
                    status=TextExtractionStatus.FAILED,
                    text="",
                    error_message=(
                        "Документ отсутствует в локальном хранилище"
                    ),
                ),
                checksum=document.checksum_sha256,
                source_path=document.local_path,
            )

        source_path = document.local_path
        checksum = (
            document.checksum_sha256.strip().casefold()
            or _file_sha256(source_path)
        )

        if not force:
            reusable = self._find_reusable(
                document.document_key,
                checksum,
            )
            if reusable is not None:
                return StoredDocumentText(
                    extraction_key=reusable.extraction_key,
                    document_key=reusable.document_key,
                    registry_key=reusable.registry_key,
                    source_path=reusable.source_path,
                    text_path=reusable.text_path,
                    document_format=reusable.document_format,
                    status=TextExtractionStatus.REUSED,
                    checksum_sha256=reusable.checksum_sha256,
                    character_count=reusable.character_count,
                    section_count=reusable.section_count,
                    extracted_at=reusable.extracted_at,
                    warnings=reusable.warnings,
                    error_message=reusable.error_message,
                )

        extraction = self.extractor.extract_file(source_path)
        return self._record_result(
            document,
            extraction,
            checksum=checksum,
            source_path=source_path,
        )

    def extract_tender(
        self,
        registry_key: str,
        *,
        force: bool = False,
    ) -> TenderTextExtractionResult:
        documents = self.document_store.list_documents(
            registry_key.strip()
        )
        results = tuple(
            self.extract_document(document, force=force)
            for document in documents
        )
        return TenderTextExtractionResult(
            registry_key=registry_key.strip(),
            documents=results,
        )

    def list_results(
        self,
        registry_key: str,
    ) -> tuple[StoredDocumentText, ...]:
        self.initialize()
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM extracted_document_text
                WHERE registry_key = ?
                ORDER BY extracted_at DESC, document_key
                """,
                (registry_key.strip(),),
            ).fetchall()
        return tuple(self._row_to_result(row) for row in rows)

    def read_text(
        self,
        result: StoredDocumentText,
    ) -> str:
        if result.text_path is None or not result.text_path.is_file():
            return ""
        return result.text_path.read_text(encoding="utf-8")

    def _find_reusable(
        self,
        document_key: str,
        checksum: str,
    ) -> StoredDocumentText | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM extracted_document_text
                WHERE document_key = ? AND checksum_sha256 = ?
                  AND status IN ('extracted', 'partial')
                ORDER BY extracted_at DESC
                LIMIT 1
                """,
                (document_key, checksum),
            ).fetchone()
        if row is None:
            return None
        result = self._row_to_result(row)
        if result.text_path is None or not result.text_path.is_file():
            return None
        return result

    def _record_result(
        self,
        document: StoredTenderDocument,
        extraction: RawTextExtraction,
        *,
        checksum: str,
        source_path: Path | None,
    ) -> StoredDocumentText:
        moment = _utc_now()
        extraction_key = hashlib.sha256(
            (
                f"{document.document_key}|{checksum}|"
                f"{extraction.document_format}"
            ).encode("utf-8")
        ).hexdigest()

        text_path: Path | None = None
        if extraction.text:
            folder = self.output_directory / _safe_component(
                document.procurement_number,
                fallback=document.registry_key,
            )
            folder.mkdir(parents=True, exist_ok=True)
            name = _safe_component(
                Path(document.name).stem,
                fallback=document.document_id or "document",
            )
            text_path = folder / (
                f"{name}-{extraction_key[:10]}.txt"
            )
            _atomic_write_text(text_path, extraction.text)

        stored = StoredDocumentText(
            extraction_key=extraction_key,
            document_key=document.document_key,
            registry_key=document.registry_key,
            source_path=source_path,
            text_path=text_path,
            document_format=extraction.document_format,
            status=extraction.status,
            checksum_sha256=checksum,
            character_count=extraction.character_count,
            section_count=len(extraction.sections),
            extracted_at=moment,
            warnings=extraction.warnings,
            error_message=extraction.error_message,
        )

        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO extracted_document_text(
                    extraction_key,
                    document_key,
                    registry_key,
                    source_path,
                    text_path,
                    document_format,
                    status,
                    checksum_sha256,
                    character_count,
                    section_count,
                    warnings,
                    error_message,
                    extracted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_key, checksum_sha256) DO UPDATE SET
                    source_path=excluded.source_path,
                    text_path=excluded.text_path,
                    document_format=excluded.document_format,
                    status=excluded.status,
                    character_count=excluded.character_count,
                    section_count=excluded.section_count,
                    warnings=excluded.warnings,
                    error_message=excluded.error_message,
                    extracted_at=excluded.extracted_at
                """,
                (
                    stored.extraction_key,
                    stored.document_key,
                    stored.registry_key,
                    str(stored.source_path or ""),
                    (
                        str(
                            stored.text_path.relative_to(
                                self.output_directory
                            )
                        )
                        if stored.text_path is not None
                        else ""
                    ),
                    stored.document_format,
                    stored.status.value,
                    stored.checksum_sha256,
                    stored.character_count,
                    stored.section_count,
                    "\n".join(stored.warnings),
                    stored.error_message,
                    stored.extracted_at,
                ),
            )
        return stored

    def _row_to_result(
        self,
        row: sqlite3.Row,
    ) -> StoredDocumentText:
        source_path_raw = str(row["source_path"] or "")
        text_path_raw = str(row["text_path"] or "")
        try:
            status = TextExtractionStatus(str(row["status"]))
        except ValueError:
            status = TextExtractionStatus.FAILED

        return StoredDocumentText(
            extraction_key=str(row["extraction_key"]),
            document_key=str(row["document_key"]),
            registry_key=str(row["registry_key"]),
            source_path=(
                Path(source_path_raw)
                if source_path_raw
                else None
            ),
            text_path=(
                self.output_directory / Path(text_path_raw)
                if text_path_raw
                else None
            ),
            document_format=str(row["document_format"]),
            status=status,
            checksum_sha256=str(row["checksum_sha256"]),
            character_count=int(row["character_count"] or 0),
            section_count=int(row["section_count"] or 0),
            extracted_at=str(row["extracted_at"]),
            warnings=tuple(
                line
                for line in str(row["warnings"] or "").splitlines()
                if line
            ),
            error_message=str(row["error_message"] or ""),
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.catalog_path,
            timeout=10.0,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection


def _discover_pdf_reader_factory() -> PdfReaderFactory | None:
    for module_name in ("pypdf", "PyPDF2"):
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        reader = getattr(module, "PdfReader", None)
        if callable(reader):
            return reader
    return None


def _decode_text(payload: bytes) -> tuple[str, str]:
    candidates = (
        "utf-8-sig",
        "utf-16",
        "windows-1251",
        "cp866",
        "latin-1",
    )
    for encoding in candidates:
        try:
            decoded = payload.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
        if "\x00" in decoded and encoding not in {"utf-16"}:
            continue
        return decoded, encoding
    return payload.decode("utf-8", errors="replace"), "utf-8-replace"


def _normalize_text(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = value.replace("\u00a0", " ")
    lines: list[str] = []
    blank_pending = False

    for raw_line in value.splitlines():
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        if not line:
            blank_pending = bool(lines)
            continue
        if blank_pending:
            lines.append("")
            blank_pending = False
        lines.append(line)

    return "\n".join(lines).strip()


def _word_xml_text(payload: bytes) -> str:
    root = ET.fromstring(payload)
    word_ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    paragraphs: list[str] = []

    for paragraph in root.iter(f"{{{word_ns}}}p"):
        parts: list[str] = []
        for element in paragraph.iter():
            if element.tag == f"{{{word_ns}}}t":
                parts.append(element.text or "")
            elif element.tag == f"{{{word_ns}}}tab":
                parts.append("\t")
            elif element.tag in {
                f"{{{word_ns}}}br",
                f"{{{word_ns}}}cr",
            }:
                parts.append("\n")
        text = _normalize_text("".join(parts))
        if text:
            paragraphs.append(text)

    return "\n".join(paragraphs).strip()


def _docx_section_label(member: str) -> str:
    if member == "word/document.xml":
        return "Основной текст"
    if "header" in member:
        return "Верхний колонтитул"
    if "footer" in member:
        return "Нижний колонтитул"
    if "footnotes" in member:
        return "Сноски"
    if "endnotes" in member:
        return "Концевые сноски"
    if "comments" in member:
        return "Комментарии"
    return member


def _xlsx_shared_strings(
    archive: ZipFile,
    names: set[str],
) -> tuple[str, ...]:
    member = "xl/sharedStrings.xml"
    if member not in names:
        return ()

    root = ET.fromstring(archive.read(member))
    main_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    values: list[str] = []
    for item in root.findall(f".//{{{main_ns}}}si"):
        text = "".join(
            element.text or ""
            for element in item.iter(f"{{{main_ns}}}t")
        )
        values.append(_normalize_text(text))
    return tuple(values)


def _xlsx_sheet_paths(
    archive: ZipFile,
    names: set[str],
) -> tuple[tuple[str, str], ...]:
    workbook_member = "xl/workbook.xml"
    rels_member = "xl/_rels/workbook.xml.rels"
    if workbook_member not in names or rels_member not in names:
        return ()

    main_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    package_ns = "http://schemas.openxmlformats.org/package/2006/relationships"

    rel_root = ET.fromstring(archive.read(rels_member))
    relations = {
        str(element.attrib.get("Id", "")): str(
            element.attrib.get("Target", "")
        )
        for element in rel_root.findall(
            f".//{{{package_ns}}}Relationship"
        )
    }

    workbook_root = ET.fromstring(archive.read(workbook_member))
    result: list[tuple[str, str]] = []
    for sheet in workbook_root.findall(f".//{{{main_ns}}}sheet"):
        name = str(sheet.attrib.get("name", "Лист"))
        relationship_id = str(
            sheet.attrib.get(f"{{{rel_ns}}}id", "")
        )
        target = relations.get(relationship_id, "")
        if not target:
            continue

        if target.startswith("/"):
            member = target.lstrip("/")
        elif target.startswith("xl/"):
            member = target
        else:
            member = str(
                PurePosixPath("xl") / PurePosixPath(target)
            )
        member = _normalize_archive_path(member)
        result.append((name, member))

    return tuple(result)


def _xlsx_sheet_text(
    payload: bytes,
    shared_strings: Sequence[str],
) -> str:
    root = ET.fromstring(payload)
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    lines: list[str] = []

    for row in root.findall(f".//{{{ns}}}row"):
        values: list[str] = []
        previous_column = 0
        for cell in row.findall(f"{{{ns}}}c"):
            reference = str(cell.attrib.get("r", ""))
            column = _excel_column_index(reference)
            if column > previous_column + 1:
                values.extend("" for _ in range(column - previous_column - 1))

            value = _xlsx_cell_value(
                cell,
                namespace=ns,
                shared_strings=shared_strings,
            )
            values.append(value)
            previous_column = max(previous_column, column)

        while values and not values[-1]:
            values.pop()
        if values:
            lines.append("\t".join(values))

    return "\n".join(lines).strip()


def _xlsx_cell_value(
    cell: ET.Element,
    *,
    namespace: str,
    shared_strings: Sequence[str],
) -> str:
    cell_type = str(cell.attrib.get("t", ""))
    formula = cell.find(f"{{{namespace}}}f")
    value_node = cell.find(f"{{{namespace}}}v")

    if cell_type == "inlineStr":
        text = "".join(
            element.text or ""
            for element in cell.iter(f"{{{namespace}}}t")
        )
        value = _normalize_text(text)
    elif value_node is None or value_node.text is None:
        value = ""
    elif cell_type == "s":
        try:
            value = shared_strings[int(value_node.text)]
        except (ValueError, IndexError):
            value = value_node.text
    elif cell_type == "b":
        value = "Да" if value_node.text == "1" else "Нет"
    else:
        value = value_node.text

    if formula is not None and formula.text:
        formula_text = f"={formula.text}"
        if value:
            return f"{formula_text} [{value}]"
        return formula_text
    return _normalize_text(value)


def _excel_column_index(reference: str) -> int:
    match = re.match(r"([A-Za-z]+)", reference)
    if not match:
        return 1
    index = 0
    for character in match.group(1).upper():
        index = index * 26 + (ord(character) - ord("A") + 1)
    return index


def _safe_archive_member(name: str) -> bool:
    path = PurePosixPath(name.replace("\\", "/"))
    return (
        not path.is_absolute()
        and ".." not in path.parts
        and bool(path.name)
    )


def _normalize_archive_path(value: str) -> str:
    parts: list[str] = []
    for part in PurePosixPath(value).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)


def _join_sections(
    sections: Sequence[ExtractedTextSection],
) -> str:
    blocks = [
        f"===== {section.label} =====\n{section.text}"
        for section in sections
        if section.text.strip()
    ]
    return "\n\n".join(blocks).strip()


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return tuple(result)


def _safe_component(
    value: str,
    *,
    fallback: str,
) -> str:
    rendered = re.sub(
        r'[<>:"/\\|?*\x00-\x1f]+',
        "_",
        value.strip(),
    )
    rendered = rendered.strip(" .")
    if not rendered:
        rendered = hashlib.sha256(
            fallback.encode("utf-8")
        ).hexdigest()[:16]
    return rendered[:120]


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_text(path: Path, value: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


__all__ = [
    "ExtractedTextSection",
    "RawTextExtraction",
    "StoredDocumentText",
    "TenderDocumentTextExtractor",
    "TenderDocumentTextService",
    "TenderTextExtractionResult",
    "TextExtractionStatus",
    "UnsupportedDocumentFormatError",
]
