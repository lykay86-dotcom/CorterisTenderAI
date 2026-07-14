from __future__ import annotations

import re

import pytest

from app.core.ai.citations import (
    CITATION_RESOLVER_VERSION,
    CitationResolutionIssue,
    resolve_citation,
)
from app.core.ai.schemas import AiDocument, AiEvidenceVerificationMethod


def _document(
    *,
    text: str = "Exact quote.",
    checksum: str = "a" * 64,
    truncated: bool = False,
) -> AiDocument:
    return AiDocument(
        document_id="doc-1",
        name="tender.pdf",
        source="eis",
        document_type="pdf",
        received_at="2026-07-14T00:00:00+00:00",
        verification_status="verified",
        text=text,
        checksum_sha256=checksum,
        truncated=truncated,
        original_character_count=len(text) + (100 if truncated else 0),
    )


def _resolve(document: AiDocument, **overrides: object):
    values: dict[str, object] = {
        "document_id": "doc-1",
        "quote": "Exact quote.",
        "section": "",
        "page": None,
        "confidence": 0.8,
        "documents": (document,),
        "context_fingerprint": "b" * 64,
    }
    values.update(overrides)
    return resolve_citation(**values)  # type: ignore[arg-type]


def test_unique_exact_quote_resolves_offsets_and_stable_id() -> None:
    document = _document(text="===== Страница 2 =====\nСрок поставки десять дней.")

    first = _resolve(document, quote="Срок поставки десять дней.")
    second = _resolve(document, quote="Срок поставки десять дней.")

    assert CITATION_RESOLVER_VERSION == "1"
    assert first.issue is None
    assert first.evidence is not None
    assert second.evidence is not None
    assert first.evidence.character_start == document.text.index("Срок")
    assert first.evidence.character_end == first.evidence.character_start + len(
        first.evidence.quote
    )
    assert first.evidence.page == 2
    assert first.evidence.section == "Страница 2"
    assert first.evidence.citation_id == second.evidence.citation_id
    assert re.fullmatch(r"cit_[0-9a-f]{32}", first.evidence.citation_id)
    assert re.fullmatch(r"doc_[0-9a-f]{32}", first.evidence.source_ref)
    assert first.evidence.verification_method is AiEvidenceVerificationMethod.EXACT_QUOTE
    assert first.evidence.checksum_sha256 == document.checksum_sha256
    assert first.evidence.context_fingerprint == "b" * 64


@pytest.mark.parametrize(
    ("overrides", "issue"),
    [
        ({"document_id": "missing"}, CitationResolutionIssue.UNKNOWN_DOCUMENT),
        ({"quote": ""}, CitationResolutionIssue.INVALID_QUOTE),
        ({"quote": None}, CitationResolutionIssue.INVALID_QUOTE),
        ({"confidence": True}, CitationResolutionIssue.INVALID_CONFIDENCE),
        ({"confidence": "0.8"}, CitationResolutionIssue.INVALID_CONFIDENCE),
        ({"confidence": float("nan")}, CitationResolutionIssue.INVALID_CONFIDENCE),
        ({"confidence": float("inf")}, CitationResolutionIssue.INVALID_CONFIDENCE),
        ({"confidence": -0.01}, CitationResolutionIssue.INVALID_CONFIDENCE),
        ({"confidence": 1.01}, CitationResolutionIssue.INVALID_CONFIDENCE),
        ({"quote": "exact quote."}, CitationResolutionIssue.QUOTE_NOT_FOUND),
    ],
)
def test_rejections_return_no_evidence_and_closed_issue(
    overrides: dict[str, object], issue: CitationResolutionIssue
) -> None:
    result = _resolve(_document(), **overrides)

    assert result.evidence is None
    assert result.issue is issue
    assert result.issue in CitationResolutionIssue


@pytest.mark.parametrize("checksum", ["", "a" * 63, "g" * 64])
def test_invalid_document_checksum_is_rejected(checksum: str) -> None:
    result = _resolve(_document(checksum=checksum))

    assert result.evidence is None
    assert result.issue is CitationResolutionIssue.INVALID_CHECKSUM


def test_checksum_and_fingerprint_changes_change_citation_id() -> None:
    baseline = _resolve(_document(checksum="a" * 64))
    changed_checksum = _resolve(_document(checksum="c" * 64))
    changed_fingerprint = _resolve(_document(checksum="a" * 64), context_fingerprint="d" * 64)

    assert baseline.evidence is not None
    assert changed_checksum.evidence is not None
    assert changed_fingerprint.evidence is not None
    assert (
        len(
            {
                baseline.evidence.citation_id,
                changed_checksum.evidence.citation_id,
                changed_fingerprint.evidence.citation_id,
            }
        )
        == 3
    )
    assert baseline.evidence.source_ref == changed_checksum.evidence.source_ref


def test_duplicate_quote_without_locator_is_ambiguous() -> None:
    document = _document(
        text="===== Страница 1 =====\nExact quote.\n===== Страница 2 =====\nExact quote."
    )

    result = _resolve(document)

    assert result.evidence is None
    assert result.issue is CitationResolutionIssue.AMBIGUOUS_QUOTE


@pytest.mark.parametrize(
    ("hints", "expected_page", "expected_section"),
    [
        ({"page": 2}, 2, "Страница 2"),
        ({"section": "Условия поставки"}, None, "Условия поставки"),
    ],
)
def test_duplicate_quote_can_be_selected_only_by_locally_derived_locator(
    hints: dict[str, object], expected_page: int | None, expected_section: str
) -> None:
    document = _document(
        text=(
            "===== Страница 1 =====\nExact quote.\n"
            "===== Страница 2 =====\nExact quote.\n"
            "===== Условия поставки =====\nExact quote."
        )
    )

    result = _resolve(document, **hints)

    assert result.issue is None
    assert result.evidence is not None
    assert result.evidence.page == expected_page
    assert result.evidence.section == expected_section


def test_conflicting_duplicate_locator_is_rejected() -> None:
    document = _document(
        text="===== Страница 1 =====\nExact quote.\n===== Страница 2 =====\nExact quote."
    )

    result = _resolve(document, page=1, section="Страница 2")

    assert result.evidence is None
    assert result.issue is CitationResolutionIssue.LOCATOR_CONFLICT


def test_unique_quote_uses_local_locator_and_ignores_conflicting_hint() -> None:
    document = _document(text="===== Страница 4 =====\nExact quote.")

    result = _resolve(document, page=99, section="Provider section")

    assert result.issue is None
    assert result.evidence is not None
    assert result.evidence.page == 4
    assert result.evidence.section == "Страница 4"


def test_exact_quote_in_truncated_context_can_resolve() -> None:
    result = _resolve(_document(text="prefix Exact quote. suffix", truncated=True))

    assert result.issue is None
    assert result.evidence is not None
