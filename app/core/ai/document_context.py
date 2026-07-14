"""Deterministic AI context built only from locally extracted tender text."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from app.core.ai.schemas import AiDocument


AI_CONTEXT_VERSION = "2"
DEFAULT_MAX_DOCUMENT_CHARACTERS = 100_000
DEFAULT_MAX_TOTAL_CHARACTERS = 400_000


@dataclass(frozen=True, slots=True)
class AiContextStatistics:
    source_document_count: int = 0
    included_document_count: int = 0
    character_count: int = 0
    truncated_document_count: int = 0
    omitted_document_count: int = 0
    empty_document_count: int = 0
    duplicate_document_count: int = 0
    unavailable_document_count: int = 0

    @property
    def truncated(self) -> bool:
        return bool(self.truncated_document_count or self.omitted_document_count)


@dataclass(frozen=True, slots=True)
class AiDocumentContext:
    documents: tuple[AiDocument, ...]
    statistics: AiContextStatistics


class TenderDocumentContextBuilder:
    """Never reads original files or downloads data; uses extraction results only."""

    def __init__(
        self,
        text_service: object,
        *,
        max_document_characters: int = DEFAULT_MAX_DOCUMENT_CHARACTERS,
        max_total_characters: int = DEFAULT_MAX_TOTAL_CHARACTERS,
    ) -> None:
        if max_document_characters < 1 or max_total_characters < 1:
            raise ValueError("AI context limits must be positive")
        self.text_service = text_service
        self.max_document_characters = max_document_characters
        self.max_total_characters = max_total_characters

    @property
    def fingerprint_parameters(self) -> dict[str, int | str]:
        return {
            "context_version": AI_CONTEXT_VERSION,
            "max_document_characters": self.max_document_characters,
            "max_total_characters": self.max_total_characters,
        }

    def build(self, registry_key: str) -> tuple[AiDocument, ...]:
        """Compatibility API for existing RM-109 consumers."""
        return self.build_context(registry_key).documents

    def build_context(self, registry_key: str) -> AiDocumentContext:
        records = tuple(self.text_service.list_results(registry_key))
        ordered = sorted(records, key=_record_sort_key)
        documents: list[AiDocument] = []
        seen_checksums: set[str] = set()
        characters = 0
        truncated = omitted = empty = duplicate = unavailable = 0

        for record in ordered:
            if not bool(getattr(record, "available_locally", False)):
                unavailable += 1
                continue
            checksum = str(getattr(record, "checksum_sha256", "") or "").strip()
            if checksum and checksum in seen_checksums:
                duplicate += 1
                continue
            if checksum:
                seen_checksums.add(checksum)
            try:
                text = str(self.text_service.read_text(record) or "").strip()
            except Exception:
                unavailable += 1
                continue
            if not text:
                empty += 1
                continue
            if characters >= self.max_total_characters:
                omitted += 1
                continue

            original_count = len(text)
            allowed = min(
                self.max_document_characters,
                self.max_total_characters - characters,
            )
            rendered = text[:allowed]
            was_truncated = len(rendered) < original_count
            if was_truncated:
                truncated += 1
            characters += len(rendered)
            source_path = getattr(record, "source_path", None)
            document_key = str(getattr(record, "document_key", "") or "")
            name = source_path.name if source_path else document_key
            status = getattr(getattr(record, "status", None), "value", "")
            document_type = _safe_document_type(
                getattr(record, "document_format", ""),
                name,
            )
            documents.append(
                AiDocument(
                    document_id=document_key,
                    name=name,
                    source="local_document_store",
                    document_type=document_type,
                    received_at=str(getattr(record, "extracted_at", "") or ""),
                    verification_status=str(status),
                    text=rendered,
                    checksum_sha256=checksum,
                    truncated=was_truncated,
                    original_character_count=original_count,
                )
            )

        statistics = AiContextStatistics(
            source_document_count=len(records),
            included_document_count=len(documents),
            character_count=characters,
            truncated_document_count=truncated,
            omitted_document_count=omitted,
            empty_document_count=empty,
            duplicate_document_count=duplicate,
            unavailable_document_count=unavailable,
        )
        return AiDocumentContext(tuple(documents), statistics)


def _record_sort_key(record: object) -> tuple[str, str, str]:
    path = getattr(record, "source_path", None)
    return (
        str(getattr(record, "document_key", "") or "").casefold(),
        str(path or "").casefold(),
        str(getattr(record, "checksum_sha256", "") or ""),
    )


def _safe_document_type(value: object, display_name: str) -> str:
    rendered = str(value or "").strip().lstrip(".").lower()
    if re.fullmatch(r"[a-z0-9][a-z0-9_.+-]{0,79}", rendered):
        return rendered
    suffix = Path(display_name).suffix.lower().lstrip(".")
    return suffix if re.fullmatch(r"[a-z0-9][a-z0-9_.+-]{0,79}", suffix) else "unknown"


__all__ = [
    "AI_CONTEXT_VERSION",
    "DEFAULT_MAX_DOCUMENT_CHARACTERS",
    "DEFAULT_MAX_TOTAL_CHARACTERS",
    "AiContextStatistics",
    "AiDocumentContext",
    "TenderDocumentContextBuilder",
]
