"""Tests for persistent extraction and reuse."""

from __future__ import annotations

from pathlib import Path

from app.tenders.document_storage import (
    DocumentDownloadStatus,
    StoredTenderDocument,
    TenderDocumentStore,
)
from app.tenders.document_text_extractor import (
    TenderDocumentTextService,
    TextExtractionStatus,
)


def _stored_document(path: Path) -> StoredTenderDocument:
    return StoredTenderDocument(
        document_key="doc-key",
        registry_key="procurement:001",
        procurement_number="001",
        source="eis",
        external_id="external-1",
        document_id="doc-1",
        name=path.name,
        source_url="https://example.org/doc.txt",
        local_path=path,
        mime_type="text/plain",
        size_bytes=path.stat().st_size,
        checksum_sha256="",
        status=DocumentDownloadStatus.DOWNLOADED,
        downloaded_at="2026-07-12T12:00:00+00:00",
    )


def test_service_persists_and_reuses_text(tmp_path) -> None:
    source = tmp_path / "ТЗ.txt"
    source.write_text(
        "Монтаж системы видеонаблюдения",
        encoding="utf-8",
    )
    store = TenderDocumentStore(tmp_path / "documents")
    service = TenderDocumentTextService(
        store,
        tmp_path / "text",
    )
    document = _stored_document(source)

    first = service.extract_document(document)
    second = service.extract_document(document)

    assert first.status == TextExtractionStatus.EXTRACTED
    assert second.status == TextExtractionStatus.REUSED
    assert first.text_path is not None
    assert first.text_path.is_file()
    assert service.read_text(first) == (
        "Монтаж системы видеонаблюдения"
    )


def test_service_reextracts_changed_document(tmp_path) -> None:
    source = tmp_path / "ТЗ.txt"
    source.write_text("Первая версия", encoding="utf-8")
    service = TenderDocumentTextService(
        TenderDocumentStore(tmp_path / "documents"),
        tmp_path / "text",
    )
    document = _stored_document(source)

    first = service.extract_document(document)
    source.write_text("Вторая версия", encoding="utf-8")
    changed = _stored_document(source)
    second = service.extract_document(changed)

    assert first.checksum_sha256 != second.checksum_sha256
    assert second.status == TextExtractionStatus.EXTRACTED
    assert "Вторая версия" in service.read_text(second)


def test_missing_local_document_is_recorded_as_failure(
    tmp_path,
) -> None:
    missing = tmp_path / "missing.txt"
    document = StoredTenderDocument(
        document_key="missing",
        registry_key="procurement:001",
        procurement_number="001",
        source="eis",
        external_id="external-1",
        document_id="doc-1",
        name="missing.txt",
        source_url="https://example.org/missing.txt",
        local_path=missing,
        mime_type="text/plain",
        size_bytes=None,
        checksum_sha256="",
        status=DocumentDownloadStatus.DOWNLOADED,
        downloaded_at="",
    )
    service = TenderDocumentTextService(
        TenderDocumentStore(tmp_path / "documents"),
        tmp_path / "text",
    )

    result = service.extract_document(document)

    assert result.status == TextExtractionStatus.FAILED
    assert "отсутствует" in result.error_message
