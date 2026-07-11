"""Static integration tests for document text extraction runtime."""

from __future__ import annotations

from pathlib import Path


def test_runtime_builds_text_extraction_service() -> None:
    source = (
        Path(__file__).parents[1]
        / "app"
        / "tenders"
        / "search_runtime.py"
    ).read_text(encoding="utf-8")

    assert "TenderDocumentTextService" in source
    assert "text_extraction_service" in source
    assert 'data_path / "tender_text"' in source


def test_tender_package_exports_text_extraction_api() -> None:
    source = (
        Path(__file__).parents[1]
        / "app"
        / "tenders"
        / "__init__.py"
    ).read_text(encoding="utf-8")

    assert "TenderDocumentTextExtractor" in source
    assert "TenderDocumentTextService" in source
    assert "TextExtractionStatus" in source
