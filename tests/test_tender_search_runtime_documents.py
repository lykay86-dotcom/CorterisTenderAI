"""Tests for document service wiring in production tender runtime."""

from __future__ import annotations

from app.tenders.search_runtime import create_tender_search_runtime


def test_runtime_initializes_document_store_and_service(tmp_path) -> None:
    runtime = create_tender_search_runtime(tmp_path)

    assert runtime.document_store is not None
    assert runtime.document_service is not None
    assert runtime.document_service.store is runtime.document_store
    assert runtime.document_service.provider_registry is runtime.registry
    assert runtime.document_store.root_directory == (tmp_path / "tender_documents")
    assert runtime.document_store.catalog_path.is_file()
