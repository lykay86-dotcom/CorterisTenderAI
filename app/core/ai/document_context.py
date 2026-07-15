"""Deterministic AI context built only from locally extracted tender text."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import TYPE_CHECKING, Protocol

from app.core.ai.schemas import AiDocument, AiDocumentationDocumentSnapshot
from app.core.document_classification import (
    APPLICATION_REQUIREMENTS_SOURCE_KINDS,
    DocumentKind,
    classify_document_kind,
)

if TYPE_CHECKING:
    from app.tenders.document_storage import StoredTenderDocument
    from app.tenders.document_text_extractor import StoredDocumentText


AI_CONTEXT_VERSION = "6"
DEFAULT_MAX_DOCUMENT_CHARACTERS = 100_000
DEFAULT_MAX_TOTAL_CHARACTERS = 400_000


class _TextService(Protocol):
    def list_results(self, registry_key: str) -> tuple[StoredDocumentText, ...]: ...

    def read_text(self, result: StoredDocumentText) -> str: ...


class _DocumentStore(Protocol):
    def list_documents(self, registry_key: str) -> tuple[StoredTenderDocument, ...]: ...


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
    application_requirements_document_count: int = 0
    included_application_requirements_document_count: int = 0
    application_requirements_truncated: bool = False
    application_requirements_document_ids: tuple[str, ...] = ()
    included_application_requirements_document_ids: tuple[str, ...] = ()

    @property
    def truncated(self) -> bool:
        return bool(self.truncated_document_count or self.omitted_document_count)


@dataclass(frozen=True, slots=True)
class AiDocumentContext:
    documents: tuple[AiDocument, ...]
    statistics: AiContextStatistics
    documentation_inventory: tuple[AiDocumentationDocumentSnapshot, ...] = ()


@dataclass(slots=True)
class _ScopedContextStatistics:
    kinds: frozenset[DocumentKind]
    document_ids: tuple[str, ...]
    included_document_ids: list[str]
    incomplete: bool = False

    @classmethod
    def from_prepared(
        cls,
        kinds: frozenset[DocumentKind],
        prepared: tuple[_PreparedRecord, ...],
    ) -> _ScopedContextStatistics:
        return cls(
            kinds=kinds,
            document_ids=tuple(
                sorted(
                    (
                        str(getattr(item.record, "document_key", "") or "")
                        for item in prepared
                        if item.kind in kinds
                    ),
                    key=str.casefold,
                )
            ),
            included_document_ids=[],
        )

    def mark_incomplete(self, kind: DocumentKind) -> None:
        if kind in self.kinds:
            self.incomplete = True

    def include(self, kind: DocumentKind, document_id: str) -> None:
        if kind in self.kinds:
            self.included_document_ids.append(document_id)


class TenderDocumentContextBuilder:
    """Never reads original files or downloads data; uses extraction results only."""

    def __init__(
        self,
        text_service: _TextService,
        *,
        document_store: _DocumentStore | None = None,
        max_document_characters: int = DEFAULT_MAX_DOCUMENT_CHARACTERS,
        max_total_characters: int = DEFAULT_MAX_TOTAL_CHARACTERS,
    ) -> None:
        if max_document_characters < 1 or max_total_characters < 1:
            raise ValueError("AI context limits must be positive")
        self.text_service = text_service
        self.document_store = document_store
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
        catalog_records = (
            tuple(self.document_store.list_documents(registry_key))
            if self.document_store is not None
            else ()
        )
        current_records = _latest_revision_records(records)
        prepared = tuple(_prepare_record(record, self.text_service) for record in current_records)
        ordered = sorted(prepared, key=_prepared_sort_key)
        documents: list[AiDocument] = []
        seen_checksums: set[str] = set()
        characters = 0
        truncated = omitted = empty = unavailable = 0
        duplicate = len(records) - len(current_records)
        included_document_ids: set[str] = set()
        truncated_document_ids: set[str] = set()

        technical = _ScopedContextStatistics.from_prepared(
            frozenset({DocumentKind.TECHNICAL_SPECIFICATION}), prepared
        )
        contract = _ScopedContextStatistics.from_prepared(
            frozenset({DocumentKind.DRAFT_CONTRACT}), prepared
        )
        requirements = _ScopedContextStatistics.from_prepared(
            APPLICATION_REQUIREMENTS_SOURCE_KINDS, prepared
        )
        scoped = (technical, contract, requirements)

        for prepared_record in ordered:
            record = prepared_record.record
            kind = prepared_record.kind
            document_key = str(getattr(record, "document_key", "") or "")
            if not bool(getattr(record, "available_locally", False)):
                unavailable += 1
                for item in scoped:
                    item.mark_incomplete(kind)
                continue
            checksum = str(getattr(record, "checksum_sha256", "") or "").strip()
            if checksum and checksum in seen_checksums:
                duplicate += 1
                for item in scoped:
                    item.mark_incomplete(kind)
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
                truncated_document_ids.add(document_key)
                for item in scoped:
                    item.mark_incomplete(kind)
            characters += len(rendered)
            source_path = getattr(record, "source_path", None)
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
            included_document_ids.add(document_key)
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
            application_requirements_document_count=len(requirements.document_ids),
            included_application_requirements_document_count=len(
                requirements.included_document_ids
            ),
            application_requirements_truncated=requirements.incomplete,
            application_requirements_document_ids=requirements.document_ids,
            included_application_requirements_document_ids=tuple(
                requirements.included_document_ids
            ),
        )
        inventory = _build_documentation_inventory(
            catalog_records,
            current_records,
            prepared,
            included_document_ids=included_document_ids,
            truncated_document_ids=truncated_document_ids,
        )
        return AiDocumentContext(tuple(documents), statistics, inventory)


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


def _build_documentation_inventory(
    catalog_records: tuple[StoredTenderDocument, ...],
    text_records: tuple[StoredDocumentText, ...],
    prepared: tuple[_PreparedRecord, ...],
    *,
    included_document_ids: set[str],
    truncated_document_ids: set[str],
) -> tuple[AiDocumentationDocumentSnapshot, ...]:
    catalog_by_key = {
        str(getattr(item, "document_key", "") or ""): item
        for item in catalog_records
        if str(getattr(item, "document_key", "") or "")
    }
    text_by_key = {
        str(getattr(item, "document_key", "") or ""): item
        for item in text_records
        if str(getattr(item, "document_key", "") or "")
    }
    prepared_by_key = {
        str(getattr(item.record, "document_key", "") or ""): item
        for item in prepared
        if str(getattr(item.record, "document_key", "") or "")
    }
    inventory: list[AiDocumentationDocumentSnapshot] = []
    for document_id in sorted(set(catalog_by_key) | set(text_by_key), key=str.casefold):
        catalog = catalog_by_key.get(document_id)
        text_record = text_by_key.get(document_id)
        prepared_record = prepared_by_key.get(document_id)
        if catalog is not None:
            display_name = str(getattr(catalog, "name", "") or document_id)
            origin = "catalog"
            raw_download_status = getattr(getattr(catalog, "status", None), "value", "")
            download_status = (
                str(raw_download_status)
                if str(raw_download_status) in {"downloaded", "reused", "deduplicated", "failed"}
                else "not_recorded"
            )
            available_locally = bool(getattr(catalog, "available_locally", False))
        else:
            source_path = getattr(text_record, "source_path", None)
            display_name = source_path.name if source_path is not None else document_id
            origin = (
                "archive_member"
                if document_id.startswith("archive-member:")
                else "local_extraction"
            )
            download_status = "not_recorded"
            available_locally = bool(
                source_path is not None and getattr(source_path, "is_file", lambda: False)()
            )

        if text_record is not None:
            raw_extraction_status = getattr(
                getattr(text_record, "status", None),
                "value",
                "",
            )
            extraction_status = (
                str(raw_extraction_status)
                if str(raw_extraction_status)
                in {"extracted", "reused", "partial", "unsupported", "failed"}
                else "not_recorded"
            )
            recorded_text_available = bool(getattr(text_record, "available_locally", False))
            prepared_text_available = bool(
                prepared_record is not None
                and not prepared_record.read_failed
                and prepared_record.text
            )
            text_available = recorded_text_available and (
                int(getattr(text_record, "character_count", 0) or 0) > 0 or prepared_text_available
            )
            available_locally = (
                available_locally
                or recorded_text_available
                or bool(
                    getattr(text_record, "source_path", None) is not None
                    and getattr(text_record.source_path, "is_file", lambda: False)()
                )
            )
        else:
            extraction_status = "not_recorded"
            text_available = False

        checksum = (
            str(
                getattr(text_record, "checksum_sha256", "")
                or getattr(catalog, "checksum_sha256", "")
                or ""
            )
            .strip()
            .casefold()
        )
        if re.fullmatch(r"[0-9a-f]{64}", checksum) is None:
            checksum = ""
        kind = (
            prepared_record.kind
            if prepared_record is not None
            else classify_document_kind(display_name, "")
        )
        inventory.append(
            AiDocumentationDocumentSnapshot(
                document_id=document_id,
                display_name=display_name,
                document_kind=kind,
                origin=origin,
                download_status=download_status,
                extraction_status=extraction_status,
                checksum_sha256=checksum,
                available_locally=available_locally,
                text_available=text_available,
                included_in_context=document_id in included_document_ids,
                context_truncated=document_id in truncated_document_ids,
            )
        )
    return tuple(sorted(inventory, key=_documentation_sort_key))


def _documentation_sort_key(
    item: AiDocumentationDocumentSnapshot,
) -> tuple[int, str, str, str]:
    priority = {
        DocumentKind.TECHNICAL_SPECIFICATION: 0,
        DocumentKind.DRAFT_CONTRACT: 1,
        DocumentKind.APPLICATION_REQUIREMENTS: 2,
        DocumentKind.APPLICATION_FORM: 3,
        DocumentKind.INSTRUCTIONS: 4,
        DocumentKind.PROCUREMENT_NOTICE: 5,
        DocumentKind.ESTIMATE: 6,
        DocumentKind.OTHER: 7,
    }
    return (
        priority[DocumentKind(item.document_kind)],
        item.document_id.casefold(),
        item.origin,
        item.checksum_sha256,
    )


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
        DocumentKind.APPLICATION_REQUIREMENTS: 2,
        DocumentKind.APPLICATION_FORM: 3,
        DocumentKind.INSTRUCTIONS: 4,
        DocumentKind.PROCUREMENT_NOTICE: 5,
        DocumentKind.ESTIMATE: 6,
    }.get(item.kind, 7)
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
