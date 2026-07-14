"""Pure, deterministic resolution of provider citation candidates."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
import math
import re

from app.core.ai.schemas import (
    AiDocument,
    AiEvidence,
    AiEvidenceVerificationMethod,
)


CITATION_RESOLVER_VERSION = "1"

_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}", re.IGNORECASE)
_SECTION_MARKER_PATTERN = re.compile(r"^===== (.+) =====$", re.MULTILINE)
_PAGE_LABEL_PATTERN = re.compile(r"Страница ([1-9][0-9]*)")


class CitationResolutionIssue(StrEnum):
    UNKNOWN_DOCUMENT = "unknown_document"
    INVALID_QUOTE = "invalid_quote"
    INVALID_CHECKSUM = "invalid_checksum"
    INVALID_CONFIDENCE = "invalid_confidence"
    QUOTE_NOT_FOUND = "quote_not_found"
    AMBIGUOUS_QUOTE = "ambiguous_quote"
    LOCATOR_CONFLICT = "locator_conflict"


@dataclass(frozen=True, slots=True)
class CitationResolution:
    evidence: AiEvidence | None
    issue: CitationResolutionIssue | None


@dataclass(frozen=True, slots=True)
class _Marker:
    start: int
    section: str
    page: int | None


@dataclass(frozen=True, slots=True)
class _Occurrence:
    start: int
    end: int
    section: str
    page: int | None


def resolve_citation(
    *,
    document_id: str,
    quote: str,
    section: str,
    page: int | None,
    confidence: float,
    documents: tuple[AiDocument, ...],
    context_fingerprint: str,
) -> CitationResolution:
    """Resolve one exact quote without trusting provider-supplied locators."""
    document = next(
        (item for item in documents if item.document_id == document_id),
        None,
    )
    if document is None:
        return _rejected(CitationResolutionIssue.UNKNOWN_DOCUMENT)
    if not isinstance(quote, str) or not quote:
        return _rejected(CitationResolutionIssue.INVALID_QUOTE)
    if _SHA256_PATTERN.fullmatch(document.checksum_sha256) is None:
        return _rejected(CitationResolutionIssue.INVALID_CHECKSUM)
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not math.isfinite(confidence)
        or not 0.0 <= confidence <= 1.0
    ):
        return _rejected(CitationResolutionIssue.INVALID_CONFIDENCE)

    occurrences = _find_occurrences(document.text, quote)
    if not occurrences:
        return _rejected(CitationResolutionIssue.QUOTE_NOT_FOUND)
    selected = _select_occurrence(occurrences, section=section, page=page)
    if isinstance(selected, CitationResolutionIssue):
        return _rejected(selected)

    citation_id = _citation_id(
        context_fingerprint=context_fingerprint,
        document_id=document.document_id,
        checksum_sha256=document.checksum_sha256,
        start=selected.start,
        end=selected.end,
        quote=quote,
    )
    source_digest = hashlib.sha256(document.document_id.encode("utf-8")).hexdigest()[:32]
    return CitationResolution(
        evidence=AiEvidence(
            citation_id=citation_id,
            document_id=document.document_id,
            quote=quote,
            character_start=selected.start,
            character_end=selected.end,
            section=selected.section,
            page=selected.page,
            confidence=float(confidence),
            verification_method=AiEvidenceVerificationMethod.EXACT_QUOTE,
            checksum_sha256=document.checksum_sha256,
            source_ref=f"doc_{source_digest}",
            context_fingerprint=context_fingerprint,
        ),
        issue=None,
    )


def _find_occurrences(text: str, quote: str) -> tuple[_Occurrence, ...]:
    markers = tuple(_markers(text))
    occurrences: list[_Occurrence] = []
    start = text.find(quote)
    while start >= 0:
        marker = next((item for item in reversed(markers) if item.start <= start), None)
        occurrences.append(
            _Occurrence(
                start=start,
                end=start + len(quote),
                section=marker.section if marker is not None else "",
                page=marker.page if marker is not None else None,
            )
        )
        start = text.find(quote, start + 1)
    return tuple(occurrences)


def _markers(text: str) -> tuple[_Marker, ...]:
    result: list[_Marker] = []
    for match in _SECTION_MARKER_PATTERN.finditer(text):
        section = match.group(1)
        page_match = _PAGE_LABEL_PATTERN.fullmatch(section)
        result.append(
            _Marker(
                start=match.start(),
                section=section,
                page=int(page_match.group(1)) if page_match is not None else None,
            )
        )
    return tuple(result)


def _select_occurrence(
    occurrences: tuple[_Occurrence, ...],
    *,
    section: str,
    page: int | None,
) -> _Occurrence | CitationResolutionIssue:
    if len(occurrences) == 1:
        return occurrences[0]

    selected = occurrences
    has_locator = bool(section) or page is not None
    if section:
        selected = tuple(item for item in selected if item.section == section)
    if page is not None:
        selected = tuple(item for item in selected if item.page == page)
    if len(selected) == 1:
        return selected[0]
    if not selected and has_locator:
        return CitationResolutionIssue.LOCATOR_CONFLICT
    return CitationResolutionIssue.AMBIGUOUS_QUOTE


def _citation_id(
    *,
    context_fingerprint: str,
    document_id: str,
    checksum_sha256: str,
    start: int,
    end: int,
    quote: str,
) -> str:
    canonical = json.dumps(
        {
            "character_end": end,
            "character_start": start,
            "checksum_sha256": checksum_sha256,
            "context_fingerprint": context_fingerprint,
            "document_id": document_id,
            "quote": quote,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]
    return f"cit_{digest}"


def _rejected(issue: CitationResolutionIssue) -> CitationResolution:
    return CitationResolution(evidence=None, issue=issue)


__all__ = [
    "CITATION_RESOLVER_VERSION",
    "CitationResolution",
    "CitationResolutionIssue",
    "resolve_citation",
]
