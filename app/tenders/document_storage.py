"""Tender-document discovery, download and content-addressed local storage."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import mimetypes
from pathlib import Path
import re
import shutil
import sqlite3
from threading import RLock
from typing import Mapping, Sequence
from urllib.parse import urlparse

from app.tenders.http_client import (
    HttpResponse,
    HttpTransport,
    HttpTransportError,
    UrllibHttpTransport,
)
from app.tenders.models import TenderDocument, UnifiedTender
from app.tenders.provider_base import (
    ProviderCapabilityError,
    ProviderNotConfiguredError,
    TenderProviderError,
)
from app.tenders.provider_registry import TenderProviderRegistry
from app.tenders.tender_registry import tender_registry_key


class DocumentDownloadStatus(StrEnum):
    DOWNLOADED = "downloaded"
    REUSED = "reused"
    DEDUPLICATED = "deduplicated"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class StoredTenderDocument:
    document_key: str
    registry_key: str
    procurement_number: str
    source: str
    external_id: str
    document_id: str
    name: str
    source_url: str
    local_path: Path | None
    mime_type: str
    size_bytes: int | None
    checksum_sha256: str
    status: DocumentDownloadStatus
    downloaded_at: str
    error_message: str = ""

    @property
    def available_locally(self) -> bool:
        return (
            self.local_path is not None
            and self.local_path.is_file()
            and self.status
            in {
                DocumentDownloadStatus.DOWNLOADED,
                DocumentDownloadStatus.REUSED,
                DocumentDownloadStatus.DEDUPLICATED,
            }
        )


@dataclass(frozen=True, slots=True)
class TenderDocumentDownloadResult:
    tender_registry_key: str
    procurement_number: str
    folder: Path
    documents: tuple[StoredTenderDocument, ...]
    catalog_warning: str = ""

    @property
    def downloaded_count(self) -> int:
        return sum(
            item.status == DocumentDownloadStatus.DOWNLOADED
            for item in self.documents
        )

    @property
    def reused_count(self) -> int:
        return sum(
            item.status
            in {
                DocumentDownloadStatus.REUSED,
                DocumentDownloadStatus.DEDUPLICATED,
            }
            for item in self.documents
        )

    @property
    def failed_count(self) -> int:
        return sum(
            item.status == DocumentDownloadStatus.FAILED
            for item in self.documents
        )

    @property
    def total_count(self) -> int:
        return len(self.documents)


@dataclass(frozen=True, slots=True)
class TenderDocumentStorageStatistics:
    tender_count: int
    document_count: int
    available_count: int
    failed_count: int
    unique_blob_count: int
    total_blob_bytes: int


class TenderDocumentDownloadError(RuntimeError):
    """Raised when a tender document cannot be downloaded safely."""


class TenderDocumentStore:
    """Persist document metadata and files without duplicate downloads."""

    SCHEMA_VERSION = 1

    def __init__(
        self,
        root_directory: str | Path,
        *,
        catalog_path: str | Path | None = None,
    ) -> None:
        self.root_directory = Path(root_directory).expanduser()
        self.root_directory.mkdir(parents=True, exist_ok=True)
        self.blob_directory = self.root_directory / ".blobs"
        self.blob_directory.mkdir(parents=True, exist_ok=True)
        self.catalog_path = (
            Path(catalog_path).expanduser()
            if catalog_path is not None
            else self.root_directory / "document_catalog.sqlite3"
        )
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS document_store_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS document_blobs (
                    checksum_sha256 TEXT PRIMARY KEY,
                    relative_path TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    mime_type TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tender_documents (
                    document_key TEXT PRIMARY KEY,
                    registry_key TEXT NOT NULL,
                    procurement_number TEXT NOT NULL,
                    source TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    mime_type TEXT NOT NULL DEFAULT '',
                    expected_size_bytes INTEGER,
                    size_bytes INTEGER,
                    checksum_sha256 TEXT NOT NULL DEFAULT '',
                    relative_path TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    error_message TEXT NOT NULL DEFAULT '',
                    first_seen_at TEXT NOT NULL,
                    last_attempt_at TEXT NOT NULL,
                    downloaded_at TEXT NOT NULL DEFAULT '',
                    UNIQUE(registry_key, source_url)
                );

                CREATE INDEX IF NOT EXISTS idx_tender_documents_registry
                    ON tender_documents(registry_key, name COLLATE NOCASE);
                CREATE INDEX IF NOT EXISTS idx_tender_documents_checksum
                    ON tender_documents(checksum_sha256);
                CREATE INDEX IF NOT EXISTS idx_tender_documents_status
                    ON tender_documents(status);
                """
            )
            connection.execute(
                """
                INSERT INTO document_store_meta(key, value)
                VALUES('schema_version', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (str(self.SCHEMA_VERSION),),
            )

    def tender_folder(self, tender: UnifiedTender) -> Path:
        number = _safe_component(
            tender.procurement_number,
            fallback=tender.external_id,
        )
        folder = self.root_directory / number
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def find_reusable(
        self,
        tender: UnifiedTender,
        document: TenderDocument,
    ) -> StoredTenderDocument | None:
        self.initialize()
        registry_key = tender_registry_key(tender)
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM tender_documents
                WHERE registry_key = ? AND source_url = ?
                """,
                (registry_key, document.url),
            ).fetchone()
        if row is None:
            return None
        stored = self._row_to_document(row)
        if not stored.available_locally:
            return None
        return replace(
            stored,
            status=DocumentDownloadStatus.REUSED,
        )

    def save_response(
        self,
        tender: UnifiedTender,
        document: TenderDocument,
        response: HttpResponse,
        *,
        downloaded_at: datetime | None = None,
    ) -> StoredTenderDocument:
        if not 200 <= response.status_code < 300:
            raise TenderDocumentDownloadError(
                f"HTTP {response.status_code} при скачивании документа"
            )
        if not response.body:
            raise TenderDocumentDownloadError(
                "Сервер вернул пустой файл документа"
            )
        if _looks_like_html(response):
            raise TenderDocumentDownloadError(
                "Вместо файла получена HTML-страница проверки доступа"
            )

        checksum = hashlib.sha256(response.body).hexdigest()
        expected_checksum = document.checksum_sha256.strip().casefold()
        if expected_checksum and expected_checksum != checksum:
            raise TenderDocumentDownloadError(
                "Контрольная сумма документа не совпадает"
            )

        moment = _utc_iso(downloaded_at)
        registry_key = tender_registry_key(tender)
        folder = self.tender_folder(tender)
        filename = _document_filename(document, response.headers)
        target_path = _unique_target_path(folder, filename)
        blob_path = self._blob_path(checksum, filename)
        blob_preexisted = blob_path.is_file()

        with self._lock:
            if not blob_preexisted:
                _atomic_write(blob_path, response.body)
            _link_or_copy(blob_path, target_path)

            mime_type = (
                _content_type(response.headers)
                or document.mime_type
                or mimetypes.guess_type(filename)[0]
                or "application/octet-stream"
            )
            relative_blob = blob_path.relative_to(
                self.root_directory
            ).as_posix()
            relative_target = target_path.relative_to(
                self.root_directory
            ).as_posix()
            document_key = _document_key(registry_key, document.url)

            self.initialize()
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    INSERT INTO document_blobs(
                        checksum_sha256,
                        relative_path,
                        size_bytes,
                        mime_type,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(checksum_sha256) DO NOTHING
                    """,
                    (
                        checksum,
                        relative_blob,
                        len(response.body),
                        mime_type,
                        moment,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO tender_documents(
                        document_key,
                        registry_key,
                        procurement_number,
                        source,
                        external_id,
                        document_id,
                        name,
                        source_url,
                        mime_type,
                        expected_size_bytes,
                        size_bytes,
                        checksum_sha256,
                        relative_path,
                        status,
                        error_message,
                        first_seen_at,
                        last_attempt_at,
                        downloaded_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?, ?)
                    ON CONFLICT(registry_key, source_url) DO UPDATE SET
                        document_id=excluded.document_id,
                        name=excluded.name,
                        mime_type=excluded.mime_type,
                        expected_size_bytes=excluded.expected_size_bytes,
                        size_bytes=excluded.size_bytes,
                        checksum_sha256=excluded.checksum_sha256,
                        relative_path=excluded.relative_path,
                        status=excluded.status,
                        error_message='',
                        last_attempt_at=excluded.last_attempt_at,
                        downloaded_at=excluded.downloaded_at
                    """,
                    (
                        document_key,
                        registry_key,
                        tender.procurement_number,
                        tender.source.value,
                        tender.external_id,
                        document.id,
                        document.name,
                        document.url,
                        mime_type,
                        document.size_bytes,
                        len(response.body),
                        checksum,
                        relative_target,
                        (
                            DocumentDownloadStatus.DEDUPLICATED.value
                            if blob_preexisted
                            else DocumentDownloadStatus.DOWNLOADED.value
                        ),
                        moment,
                        moment,
                        moment,
                    ),
                )
                connection.commit()

        return StoredTenderDocument(
            document_key=document_key,
            registry_key=registry_key,
            procurement_number=tender.procurement_number,
            source=tender.source.value,
            external_id=tender.external_id,
            document_id=document.id,
            name=document.name,
            source_url=document.url,
            local_path=target_path,
            mime_type=mime_type,
            size_bytes=len(response.body),
            checksum_sha256=checksum,
            status=(
                DocumentDownloadStatus.DEDUPLICATED
                if blob_preexisted
                else DocumentDownloadStatus.DOWNLOADED
            ),
            downloaded_at=moment,
        )

    def record_failure(
        self,
        tender: UnifiedTender,
        document: TenderDocument,
        error_message: str,
        *,
        attempted_at: datetime | None = None,
    ) -> StoredTenderDocument:
        self.initialize()
        moment = _utc_iso(attempted_at)
        registry_key = tender_registry_key(tender)
        document_key = _document_key(registry_key, document.url)
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO tender_documents(
                    document_key,
                    registry_key,
                    procurement_number,
                    source,
                    external_id,
                    document_id,
                    name,
                    source_url,
                    mime_type,
                    expected_size_bytes,
                    size_bytes,
                    checksum_sha256,
                    relative_path,
                    status,
                    error_message,
                    first_seen_at,
                    last_attempt_at,
                    downloaded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, '', '', ?, ?, ?, ?, '')
                ON CONFLICT(registry_key, source_url) DO UPDATE SET
                    document_id=excluded.document_id,
                    name=excluded.name,
                    mime_type=excluded.mime_type,
                    expected_size_bytes=excluded.expected_size_bytes,
                    status=excluded.status,
                    error_message=excluded.error_message,
                    last_attempt_at=excluded.last_attempt_at
                """,
                (
                    document_key,
                    registry_key,
                    tender.procurement_number,
                    tender.source.value,
                    tender.external_id,
                    document.id,
                    document.name,
                    document.url,
                    document.mime_type,
                    document.size_bytes,
                    DocumentDownloadStatus.FAILED.value,
                    error_message,
                    moment,
                    moment,
                ),
            )
        return StoredTenderDocument(
            document_key=document_key,
            registry_key=registry_key,
            procurement_number=tender.procurement_number,
            source=tender.source.value,
            external_id=tender.external_id,
            document_id=document.id,
            name=document.name,
            source_url=document.url,
            local_path=None,
            mime_type=document.mime_type,
            size_bytes=document.size_bytes,
            checksum_sha256="",
            status=DocumentDownloadStatus.FAILED,
            downloaded_at="",
            error_message=error_message,
        )

    def list_documents(
        self,
        registry_key: str,
    ) -> tuple[StoredTenderDocument, ...]:
        self.initialize()
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM tender_documents
                WHERE registry_key = ?
                ORDER BY name COLLATE NOCASE, source_url
                """,
                (registry_key.strip(),),
            ).fetchall()
        return tuple(self._row_to_document(row) for row in rows)

    def statistics(self) -> TenderDocumentStorageStatistics:
        self.initialize()
        with self._lock, self._connect() as connection:
            document_row = connection.execute(
                """
                SELECT COUNT(*) AS document_count,
                       COUNT(DISTINCT registry_key) AS tender_count,
                       SUM(CASE WHEN status IN ('downloaded', 'reused', 'deduplicated')
                           THEN 1 ELSE 0 END) AS available_count,
                       SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END)
                           AS failed_count
                FROM tender_documents
                """
            ).fetchone()
            blob_row = connection.execute(
                """
                SELECT COUNT(*) AS blob_count,
                       COALESCE(SUM(size_bytes), 0) AS total_bytes
                FROM document_blobs
                """
            ).fetchone()
        return TenderDocumentStorageStatistics(
            tender_count=int(document_row["tender_count"] or 0),
            document_count=int(document_row["document_count"] or 0),
            available_count=int(document_row["available_count"] or 0),
            failed_count=int(document_row["failed_count"] or 0),
            unique_blob_count=int(blob_row["blob_count"] or 0),
            total_blob_bytes=int(blob_row["total_bytes"] or 0),
        )

    def _row_to_document(
        self,
        row: sqlite3.Row,
    ) -> StoredTenderDocument:
        relative = str(row["relative_path"] or "")
        local_path = (
            self.root_directory / Path(relative)
            if relative
            else None
        )
        status_raw = str(row["status"])
        try:
            status = DocumentDownloadStatus(status_raw)
        except ValueError:
            status = DocumentDownloadStatus.FAILED
        return StoredTenderDocument(
            document_key=str(row["document_key"]),
            registry_key=str(row["registry_key"]),
            procurement_number=str(row["procurement_number"]),
            source=str(row["source"]),
            external_id=str(row["external_id"]),
            document_id=str(row["document_id"]),
            name=str(row["name"]),
            source_url=str(row["source_url"]),
            local_path=local_path,
            mime_type=str(row["mime_type"]),
            size_bytes=(
                int(row["size_bytes"])
                if row["size_bytes"] is not None
                else (
                    int(row["expected_size_bytes"])
                    if row["expected_size_bytes"] is not None
                    else None
                )
            ),
            checksum_sha256=str(row["checksum_sha256"]),
            status=status,
            downloaded_at=str(row["downloaded_at"]),
            error_message=str(row["error_message"]),
        )

    def _blob_path(self, checksum: str, filename: str) -> Path:
        suffix = Path(filename).suffix.lower()
        safe_suffix = suffix if re.fullmatch(r"\.[a-z0-9]{1,10}", suffix) else ""
        folder = self.blob_directory / checksum[:2]
        folder.mkdir(parents=True, exist_ok=True)
        return folder / f"{checksum}{safe_suffix}"

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.catalog_path,
            timeout=10.0,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection


class TenderDocumentDownloadService:
    """Discover provider documents and download them to local storage."""

    def __init__(
        self,
        provider_registry: TenderProviderRegistry,
        store: TenderDocumentStore,
        *,
        http_transport: HttpTransport | None = None,
        timeout_seconds: float = 45.0,
        user_agent: str = (
            "CorterisTenderAI/1.5.1 "
            "(+https://corteris.ru; tender document download)"
        ),
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.provider_registry = provider_registry
        self.store = store
        self.http_transport = http_transport or UrllibHttpTransport(
            max_response_bytes=250 * 1024 * 1024
        )
        self.timeout_seconds = float(timeout_seconds)
        self.user_agent = user_agent

    def download_for_tender(
        self,
        tender: UnifiedTender,
        *,
        force: bool = False,
        refresh_catalog: bool = True,
    ) -> TenderDocumentDownloadResult:
        documents = tender.documents
        catalog_warning = ""

        if refresh_catalog or not documents:
            try:
                provider = self.provider_registry.get(
                    tender.source.value
                )
                documents = tuple(
                    provider.list_documents(tender.external_id)
                )
            except (
                KeyError,
                ProviderCapabilityError,
                ProviderNotConfiguredError,
                TenderProviderError,
            ) as exc:
                if not documents:
                    catalog_warning = str(exc)
                else:
                    catalog_warning = (
                        "Не удалось обновить список документов: "
                        f"{exc}"
                    )

        results: list[StoredTenderDocument] = []
        for document in _unique_documents(documents):
            if not force:
                reusable = self.store.find_reusable(tender, document)
                if reusable is not None:
                    results.append(reusable)
                    continue

            try:
                response = self.http_transport.get(
                    document.url,
                    headers={
                        "User-Agent": self.user_agent,
                        "Accept": (
                            "application/pdf,application/zip,"
                            "application/octet-stream,*/*;q=0.8"
                        ),
                    },
                    timeout_seconds=self.timeout_seconds,
                )
                stored = self.store.save_response(
                    tender,
                    document,
                    response,
                )
            except (
                HttpTransportError,
                TenderDocumentDownloadError,
                OSError,
            ) as exc:
                stored = self.store.record_failure(
                    tender,
                    document,
                    str(exc),
                )
            results.append(stored)

        return TenderDocumentDownloadResult(
            tender_registry_key=tender_registry_key(tender),
            procurement_number=tender.procurement_number,
            folder=self.store.tender_folder(tender),
            documents=tuple(results),
            catalog_warning=catalog_warning,
        )


def _unique_documents(
    documents: Sequence[TenderDocument],
) -> tuple[TenderDocument, ...]:
    result: list[TenderDocument] = []
    seen: set[str] = set()
    for document in documents:
        key = document.url.strip().casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(document)
    return tuple(result)


def _document_key(registry_key: str, source_url: str) -> str:
    digest = hashlib.sha256(
        f"{registry_key}\0{source_url.strip().casefold()}".encode("utf-8")
    ).hexdigest()
    return f"document:{digest}"


def _safe_component(value: str, *, fallback: str) -> str:
    normalized = value.strip() or fallback.strip() or "tender"
    normalized = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip(" .")
    if not normalized:
        normalized = "tender"
    return normalized[:120]


def _document_filename(
    document: TenderDocument,
    headers: Mapping[str, str],
) -> str:
    name = document.name.strip()
    if not name:
        name = Path(urlparse(document.url).path).name
    name = _safe_component(name, fallback=document.id)

    if not Path(name).suffix:
        mime = _content_type(headers) or document.mime_type
        suffix = mimetypes.guess_extension(mime or "") or ""
        if suffix == ".jpe":
            suffix = ".jpg"
        name += suffix
    return name[:180]


def _unique_target_path(folder: Path, filename: str) -> Path:
    candidate = folder / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    for index in range(2, 10_000):
        next_candidate = folder / f"{stem} ({index}){suffix}"
        if not next_candidate.exists():
            return next_candidate
    raise OSError("Не удалось подобрать уникальное имя файла")


def _atomic_write(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    try:
        temporary.write_bytes(body)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _link_or_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.hardlink_to(source)
    except OSError:
        shutil.copy2(source, target)


def _content_type(headers: Mapping[str, str]) -> str:
    value = headers.get("content-type", "")
    return value.split(";", 1)[0].strip().casefold()


def _looks_like_html(response: HttpResponse) -> bool:
    content_type = _content_type(response.headers)
    if content_type in {"text/html", "application/xhtml+xml"}:
        return True
    prefix = response.body[:512].lstrip().lower()
    return prefix.startswith((b"<!doctype html", b"<html", b"<head"))


def _utc_iso(value: datetime | None = None) -> str:
    moment = value or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


__all__ = [
    "DocumentDownloadStatus",
    "StoredTenderDocument",
    "TenderDocumentDownloadError",
    "TenderDocumentDownloadResult",
    "TenderDocumentDownloadService",
    "TenderDocumentStorageStatistics",
    "TenderDocumentStore",
]
