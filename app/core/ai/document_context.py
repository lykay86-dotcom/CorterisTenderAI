"""Deterministic AI context built only from locally extracted tender text."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import TYPE_CHECKING, Protocol

from app.core.ai.schemas import AiDocument
from app.core.document_classification import DocumentKind, classify_document_kind

if TYPE_CHECKING:
    from app.tenders.document_text_extractor import StoredDocumentText


AI_CONTEXT_VERSION = "4"
DEFAULT_MAX_DOCUMENT_CHARACTERS = 100_000
DEFAULT_MAX_TOTAL_CHARACTERS = 400_000


class _TextService(Protocol):
    def list_results(self, registry_key: str) -> tuple[StoredDocumentText, ...]: ...

    def read_text(self, result: StoredDocumentText) -> str: ...


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
    technical_specification_document_count: int = 0
    included_technical_specification_document_count: int = 0
    technical_specification_truncated: bool = False
    technical_specification_document_ids: tuple[str, ...] = ()
    included_technical_specification_document_ids: tuple[str, ...] = ()
    draft_contract_document_count: int = 0
    included_draft_contract_document_count: int = 0
    draft_contract_truncated: bool = False
    draft_contract_document_ids: tuple[str, ...] = ()
    included_draft_contract_document_ids: tuple[str, ...] = ()

    @property
    def truncated(self) -> bool:
        return bool(self.truncated_document_count or self.omitted_document_count)


@dataclass(frozen=True, slots=True)
class AiDocumentContext:
    documents: tuple[AiDocument, ...]
    statistics: AiContextStatistics


@dataclass(slots=True)
class _ScopedContextStatistics:
    kind: DocumentKind
    document_ids: tuple[str, ...]
    included_document_ids: list[str]
    incomplete: bool = False

    @classmethod
    def from_prepared(
        cls,
        kind: DocumentKind,
        prepared: tuple[_PreparedRecord, ...],
    ) -> _ScopedContextStatistics:
        return cls(
            kind=kind,
            document_ids=tuple(
                sorted(
                    (
                        str(getattr(item.record, "document_key", "") or "")
                        for item in prepared
                        if item.kind is kind
                    ),
                    key=str.casefold,
                )
            ),
            included_document_ids=[],
        )

    def mark_incomplete(self, kind: DocumentKind) -> None:
        if kind is self.kind:
            self.incomplete = True

    def include(self, kind: DocumentKind, document_id: str) -> None:
        if kind is self.kind:
            self.included_document_ids.append(document_id)


class TenderDocumentContextBuilder:
    """Never reads original files or downloads data; uses extraction results only."""

    def __init__(
        self,
        text_service: _TextService,
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
        current_records = _latest_revision_records(records)
        prepared = tuple(_prepare_record(record, self.text_service) for record in current_records)
        ordered = sorted(prepared, key=_prepared_sort_key)
        documents: list[AiDocument] = []
        seen_checksums: set[str] = set()
        characters = 0
        truncated = omitted = empty = unavailable = 0
        duplicate = len(records) - len(current_records)

        technical = _ScopedContextStatistics.from_prepared(
            DocumentKind.TECHNICAL_SPECIFICATION, prepared
        )
        contract = _ScopedContextStatistics.from_prepared(DocumentKind.DRAFT_CONTRACT, prepared)
        scoped = (technical, contract)

        for prepared_record in ordered:
            record = prepared_record.record
            kind = prepared_record.kind
            if not bool(getattr(record, "available_locally", False)):
                unavailable += 1
                for item in scoped:
                    item.mark_incomplete(kind)
                continue
            checksum = str(getattr(record, "checksum_sha256", "") or "").strip()
            if checksum and checksum in seen_checksums:
                duplicate += 1
                continue
            if checksum:
                seen_checksums.add(checksum)
            try:
                text = prepared_record.text
            except Exception:
                unavailable += 1
                for item in scoped:
                    item.mark_incomplete(kind)
                continue
            if prepared_record.read_failed:
                unavailable += 1
                for item in scoped:
                    item.mark_incomplete(kind)
                continue
            if not text:
                empty += 1
                for item in scoped:
                    item.mark_incomplete(kind)
                continue
            if characters >= self.max_total_characters:
                omitted += 1
                for item in scoped:
                    item.mark_incomplete(kind)
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
                for item in scoped:
                    item.mark_incomplete(kind)
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
                    document_kind=kind.value,
                )
            )
            for item in scoped:
                item.include(kind, document_key)

        statistics = AiContextStatistics(
            source_document_count=len(records),
            included_document_count=len(documents),
            character_count=characters,
            truncated_document_count=truncated,
            omitted_document_count=omitted,
            empty_document_count=empty,
            duplicate_document_count=duplicate,
            unavailable_document_count=unavailable,
            technical_specification_document_count=len(technical.document_ids),
            included_technical_specification_document_count=len(technical.included_document_ids),
            technical_specification_truncated=technical.incomplete,
            technical_specification_document_ids=technical.document_ids,
            included_technical_specification_document_ids=tuple(technical.included_document_ids),
            draft_contract_document_count=len(contract.document_ids),
            included_draft_contract_document_count=len(contract.included_document_ids),
            draft_contract_truncated=contract.incomplete,
            draft_contract_document_ids=contract.document_ids,
            included_draft_contract_document_ids=tuple(contract.included_document_ids),
        )
        return AiDocumentContext(tuple(documents), statistics)


def _latest_revision_records(
    records: tuple[StoredDocumentText, ...],
) -> tuple[StoredDocumentText, ...]:
    latest: dict[str, StoredDocumentText] = {}
    for record in records:
        document_key = str(getattr(record, "document_key", "") or "")
        previous = latest.get(document_key)
        if previous is None or _record_revision_key(record) > _record_revision_key(previous):
            latest[document_key] = record
    return tuple(latest.values())


def _record_revision_key(record: object) -> tuple[float, str, str]:
    raw_timestamp = str(getattr(record, "extracted_at", "") or "")
    try:
        parsed = datetime.fromisoformat(raw_timestamp)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        timestamp = parsed.timestamp()
    except (OSError, OverflowError, ValueError):
        timestamp = float("-inf")
    return (
        timestamp,
        str(getattr(record, "checksum_sha256", "") or ""),
        str(getattr(record, "source_path", "") or "").casefold(),
    )


@dataclass(frozen=True, slots=True)
class _PreparedRecord:
    record: StoredDocumentText
    text: str
    kind: DocumentKind
    read_failed: bool = False


def _prepare_record(record: StoredDocumentText, text_service: _TextService) -> _PreparedRecord:
    text = ""
    read_failed = False
    if bool(getattr(record, "available_locally", False)):
        try:
            text = str(text_service.read_text(record) or "").strip()
        except Exception:
            text = ""
            read_failed = True
    path = getattr(record, "source_path", None)
    name = path.name if path else str(getattr(record, "document_key", "") or "")
    return _PreparedRecord(record, text, classify_document_kind(name, text), read_failed)


def _prepared_sort_key(item: _PreparedRecord) -> tuple[int, str, str, str]:
    record = item.record
    path = getattr(record, "source_path", None)
    priority = {
        DocumentKind.TECHNICAL_SPECIFICATION: 0,
        DocumentKind.DRAFT_CONTRACT: 1,
        DocumentKind.PROCUREMENT_NOTICE: 2,
        DocumentKind.ESTIMATE: 2,
    }.get(item.kind, 3)
    return (
        priority,
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
