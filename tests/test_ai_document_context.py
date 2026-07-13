from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.core.ai.document_context import TenderDocumentContextBuilder


class TextService:
    def __init__(self) -> None:
        self.available = SimpleNamespace(
            document_key="doc-1", source_path=Path("C:/docs/specification.pdf"),
            extracted_at="2026-07-13T00:00:00+00:00", status=SimpleNamespace(value="extracted"),
            checksum_sha256="abc", available_locally=True,
        )
        self.unavailable = SimpleNamespace(
            document_key="doc-2", source_path=None, extracted_at="", status=SimpleNamespace(value="failed"),
            checksum_sha256="", available_locally=False,
        )

    def list_results(self, _key):
        return (self.available, self.unavailable)

    def read_text(self, record):
        return "Technical specification text" if record is self.available else ""


def test_context_uses_only_available_extracted_text() -> None:
    documents = TenderDocumentContextBuilder(TextService()).build("procurement:test")

    assert len(documents) == 1
    assert documents[0].document_id == "doc-1"
    assert documents[0].document_type == "pdf"
    assert documents[0].text == "Technical specification text"
