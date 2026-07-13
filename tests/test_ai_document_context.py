from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.core.ai.document_context import TenderDocumentContextBuilder


class TextService:
    def __init__(self) -> None:
        self.available = SimpleNamespace(
            document_key="doc-1",
            source_path=Path("C:/docs/specification.pdf"),
            extracted_at="2026-07-13T00:00:00+00:00",
            status=SimpleNamespace(value="extracted"),
            checksum_sha256="abc",
            available_locally=True,
        )
        self.unavailable = SimpleNamespace(
            document_key="doc-2",
            source_path=None,
            extracted_at="",
            status=SimpleNamespace(value="failed"),
            checksum_sha256="",
            available_locally=False,
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


def _record(key: str, checksum: str, *, available: bool = True):
    return SimpleNamespace(
        document_key=key,
        source_path=Path(f"C:/files-that-do-not-exist/{key}.pdf"),
        extracted_at="2026-07-13T00:00:00+00:00",
        status=SimpleNamespace(value="extracted"),
        checksum_sha256=checksum,
        available_locally=available,
    )


class FlexibleTextService:
    def __init__(self, records, texts) -> None:
        self.records = tuple(records)
        self.texts = dict(texts)

    def list_results(self, _key):
        return self.records

    def read_text(self, record):
        return self.texts.get(record.document_key, "")


def test_context_is_stably_sorted_and_reproducible() -> None:
    records = (_record("z", "z1"), _record("a", "a1"))
    service = FlexibleTextService(records, {"z": "Zulu", "a": "Alpha"})
    builder = TenderDocumentContextBuilder(service)

    first = builder.build_context("procurement:test")
    service.records = tuple(reversed(service.records))
    second = builder.build_context("procurement:test")

    assert [item.document_id for item in first.documents] == ["a", "z"]
    assert first == second


def test_context_excludes_empty_unavailable_and_checksum_duplicates() -> None:
    records = (
        _record("a-first", "same"),
        _record("z-duplicate", "same"),
        _record("empty", "empty"),
        _record("offline", "offline", available=False),
    )
    context = TenderDocumentContextBuilder(
        FlexibleTextService(
            records,
            {"a-first": "usable", "z-duplicate": "duplicate", "empty": "   "},
        )
    ).build_context("procurement:test")

    assert [item.document_id for item in context.documents] == ["a-first"]
    assert context.statistics.duplicate_document_count == 1
    assert context.statistics.empty_document_count == 1
    assert context.statistics.unavailable_document_count == 1


def test_context_applies_per_document_and_total_unicode_safe_limits() -> None:
    records = (_record("a", "one"), _record("b", "two"), _record("c", "three"))
    builder = TenderDocumentContextBuilder(
        FlexibleTextService(
            records,
            {"a": "абвгде", "b": "ёжзийк", "c": "остаток"},
        ),
        max_document_characters=5,
        max_total_characters=8,
    )

    context = builder.build_context("procurement:test")

    assert [item.text for item in context.documents] == ["абвгд", "ёжз"]
    assert all("�" not in item.text for item in context.documents)
    assert all(item.truncated for item in context.documents)
    assert context.documents[0].original_character_count == 6
    assert context.documents[0].checksum_sha256 == "one"
    assert context.statistics.character_count == 8
    assert context.statistics.omitted_document_count == 1
    assert context.statistics.truncated


def test_context_fingerprint_parameters_include_limits() -> None:
    builder = TenderDocumentContextBuilder(
        FlexibleTextService((), {}),
        max_document_characters=10,
        max_total_characters=20,
    )

    assert builder.fingerprint_parameters["max_document_characters"] == 10
    assert builder.fingerprint_parameters["max_total_characters"] == 20
    assert builder.fingerprint_parameters["context_version"]
