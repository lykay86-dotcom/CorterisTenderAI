"""Explainable tender change detection between collector observations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Iterable
from uuid import uuid4

from app.tenders.collector.codec import stable_json
from app.tenders.collector.models import TenderObservationStatus
from app.tenders.models import TenderDocument, TenderStatus, UnifiedTender


class TenderChangeType(StrEnum):
    NEW = "new"
    PRICE_CHANGED = "price_changed"
    DEADLINE_EXTENDED = "deadline_extended"
    DEADLINE_SHORTENED = "deadline_shortened"
    STATUS_CHANGED = "status_changed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    DOCUMENT_ADDED = "document_added"
    DOCUMENT_REMOVED = "document_removed"
    TITLE_CHANGED = "title_changed"
    CUSTOMER_CHANGED = "customer_changed"
    DESCRIPTION_CHANGED = "description_changed"
    METADATA_CHANGED = "metadata_changed"


@dataclass(frozen=True, slots=True)
class TenderChange:
    change_id: str
    change_type: TenderChangeType
    field_name: str
    old_value: str
    new_value: str
    detected_at: str
    source: str


@dataclass(frozen=True, slots=True)
class TenderChangeSet:
    status: TenderObservationStatus
    changes: tuple[TenderChange, ...]

    @property
    def changed(self) -> bool:
        return self.status != TenderObservationStatus.UNCHANGED


class TenderChangeTracker:
    """Compare important business fields and document sets."""

    def compare(
        self,
        old: UnifiedTender | None,
        new: UnifiedTender,
        *,
        detected_at: str | None = None,
    ) -> TenderChangeSet:
        moment = detected_at or _utc_now()
        source = new.source.value
        if old is None:
            return TenderChangeSet(
                status=TenderObservationStatus.NEW,
                changes=(
                    _change(
                        TenderChangeType.NEW,
                        "tender",
                        "",
                        new.procurement_number,
                        moment,
                        source,
                    ),
                ),
            )

        changes: list[TenderChange] = []
        if old.title.strip() != new.title.strip():
            changes.append(
                _change(
                    TenderChangeType.TITLE_CHANGED,
                    "title",
                    old.title,
                    new.title,
                    moment,
                    source,
                )
            )

        old_customer = (
            old.customer.inn.strip(),
            old.customer.name.strip(),
        )
        new_customer = (
            new.customer.inn.strip(),
            new.customer.name.strip(),
        )
        if old_customer != new_customer:
            changes.append(
                _change(
                    TenderChangeType.CUSTOMER_CHANGED,
                    "customer",
                    stable_json(old_customer),
                    stable_json(new_customer),
                    moment,
                    source,
                )
            )

        old_price = _price(old)
        new_price = _price(new)
        if old_price != new_price:
            changes.append(
                _change(
                    TenderChangeType.PRICE_CHANGED,
                    "price",
                    old_price,
                    new_price,
                    moment,
                    source,
                )
            )

        if old.application_deadline != new.application_deadline:
            change_type = TenderChangeType.METADATA_CHANGED
            if old.application_deadline is not None and new.application_deadline is not None:
                change_type = (
                    TenderChangeType.DEADLINE_EXTENDED
                    if new.application_deadline > old.application_deadline
                    else TenderChangeType.DEADLINE_SHORTENED
                )
            changes.append(
                _change(
                    change_type,
                    "application_deadline",
                    _iso(old.application_deadline),
                    _iso(new.application_deadline),
                    moment,
                    source,
                )
            )

        if old.status != new.status:
            change_type = TenderChangeType.STATUS_CHANGED
            if new.status == TenderStatus.CANCELLED:
                change_type = TenderChangeType.CANCELLED
            elif new.status == TenderStatus.COMPLETED:
                change_type = TenderChangeType.COMPLETED
            changes.append(
                _change(
                    change_type,
                    "status",
                    old.status.value,
                    new.status.value,
                    moment,
                    source,
                )
            )

        if old.description.strip() != new.description.strip():
            changes.append(
                _change(
                    TenderChangeType.DESCRIPTION_CHANGED,
                    "description",
                    old.description,
                    new.description,
                    moment,
                    source,
                )
            )

        old_documents = _document_map(old.documents)
        new_documents = _document_map(new.documents)
        for key in sorted(new_documents.keys() - old_documents.keys()):
            document = new_documents[key]
            changes.append(
                _change(
                    TenderChangeType.DOCUMENT_ADDED,
                    "documents",
                    "",
                    _document_value(document),
                    moment,
                    source,
                )
            )
        for key in sorted(old_documents.keys() - new_documents.keys()):
            document = old_documents[key]
            changes.append(
                _change(
                    TenderChangeType.DOCUMENT_REMOVED,
                    "documents",
                    _document_value(document),
                    "",
                    moment,
                    source,
                )
            )

        if not changes:
            return TenderChangeSet(
                status=TenderObservationStatus.UNCHANGED,
                changes=(),
            )
        return TenderChangeSet(
            status=TenderObservationStatus.CHANGED,
            changes=tuple(changes),
        )


def _change(
    change_type: TenderChangeType,
    field_name: str,
    old_value: str,
    new_value: str,
    detected_at: str,
    source: str,
) -> TenderChange:
    return TenderChange(
        change_id=uuid4().hex,
        change_type=change_type,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        detected_at=detected_at,
        source=source,
    )


def _price(tender: UnifiedTender) -> str:
    if tender.price is None:
        return ""
    return stable_json(
        {
            "amount": str(tender.price.amount),
            "currency": tender.price.currency,
            "includes_vat": tender.price.includes_vat,
        }
    )


def _document_key(document: TenderDocument) -> str:
    if document.checksum_sha256:
        return f"sha:{document.checksum_sha256.casefold()}"
    return f"url:{document.url.strip()}"


def _document_map(
    documents: Iterable[TenderDocument],
) -> dict[str, TenderDocument]:
    return {_document_key(document): document for document in documents}


def _document_value(document: TenderDocument) -> str:
    return stable_json(
        {
            "id": document.id,
            "name": document.name,
            "url": document.url,
            "checksum_sha256": document.checksum_sha256,
            "size_bytes": document.size_bytes,
        }
    )


def _iso(value: object) -> str:
    return value.isoformat() if value is not None else ""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


__all__ = [
    "TenderChange",
    "TenderChangeSet",
    "TenderChangeTracker",
    "TenderChangeType",
]
