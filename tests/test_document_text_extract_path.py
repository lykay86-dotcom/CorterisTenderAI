from __future__ import annotations

from app.tenders.document_storage import TenderDocumentStore
from app.tenders.document_text_extractor import TenderDocumentTextService


def test_extract_path_persists_archive_member_text(tmp_path) -> None:
    store = TenderDocumentStore(tmp_path / "documents")
    service = TenderDocumentTextService(store, tmp_path / "text")
    source = tmp_path / "extracted" / "ТЗ.txt"
    source.parent.mkdir()
    source.write_text("Монтаж видеонаблюдения и СКУД", encoding="utf-8")

    result = service.extract_path(
        "procurement:1",
        "1",
        source,
    )

    assert result.available_locally
    assert "СКУД" in service.read_text(result)
    assert service.list_results("procurement:1")
