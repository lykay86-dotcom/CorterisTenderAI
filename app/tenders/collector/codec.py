"""Stable serialization helpers for collector persistence and hashing."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
from typing import Any, Mapping

from app.core.json_serialization import json_dumps
from app.tenders.models import (
    TenderCustomer,
    TenderDocument,
    TenderMoney,
    TenderProcedureType,
    TenderSource,
    TenderStatus,
    UnifiedTender,
)
from app.tenders.provider_base import TenderSearchQuery


def stable_json(value: object) -> str:
    """Render JSON deterministically without converting money to float."""

    return json_dumps(
        value,
        ensure_ascii=False,
        indent=None,
        separators=(",", ":"),
        sort_keys=True,
    )


def stable_hash(value: object) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def tender_to_payload(tender: UnifiedTender) -> dict[str, Any]:
    """Convert ``UnifiedTender`` to a versioned JSON-safe payload."""

    return {
        "schema_version": 1,
        "source": tender.source.value,
        "external_id": tender.external_id,
        "procurement_number": tender.procurement_number,
        "title": tender.title,
        "customer": {
            "name": tender.customer.name,
            "inn": tender.customer.inn,
            "kpp": tender.customer.kpp,
            "region": tender.customer.region,
            "address": tender.customer.address,
        },
        "source_url": tender.source_url,
        "published_at": _optional_iso(tender.published_at),
        "application_deadline": _optional_iso(
            tender.application_deadline
        ),
        "execution_deadline": _optional_iso(tender.execution_deadline),
        "price": (
            {
                "amount": str(tender.price.amount),
                "currency": tender.price.currency,
                "includes_vat": tender.price.includes_vat,
            }
            if tender.price is not None
            else None
        ),
        "status": tender.status.value,
        "procedure_type": tender.procedure_type.value,
        "law": tender.law,
        "region": tender.region,
        "description": tender.description,
        "classification_codes": list(tender.classification_codes),
        "tags": list(tender.tags),
        "documents": [
            {
                "id": item.id,
                "name": item.name,
                "url": item.url,
                "mime_type": item.mime_type,
                "size_bytes": item.size_bytes,
                "published_at": _optional_iso(item.published_at),
                "checksum_sha256": item.checksum_sha256,
            }
            for item in tender.documents
        ],
        "raw_metadata": _json_safe(tender.raw_metadata),
    }


def tender_from_payload(payload: Mapping[str, Any]) -> UnifiedTender:
    """Restore a ``UnifiedTender`` from collector/registry JSON."""

    customer_payload = payload.get("customer")
    if not isinstance(customer_payload, Mapping):
        customer_payload = {}

    price_payload = payload.get("price")
    price = None
    if isinstance(price_payload, Mapping):
        price = TenderMoney.from_value(
            str(price_payload.get("amount", "0")),
            currency=str(price_payload.get("currency", "RUB")),
            includes_vat=_optional_bool(
                price_payload.get("includes_vat")
            ),
        )

    documents: list[TenderDocument] = []
    raw_documents = payload.get("documents") or ()
    if isinstance(raw_documents, (list, tuple)):
        for raw in raw_documents:
            if not isinstance(raw, Mapping):
                continue
            document_id = str(raw.get("id", "")).strip()
            name = str(raw.get("name", "")).strip()
            url = str(raw.get("url", "")).strip()
            if not document_id or not name or not url:
                continue
            documents.append(
                TenderDocument(
                    id=document_id,
                    name=name,
                    url=url,
                    mime_type=str(raw.get("mime_type", "")),
                    size_bytes=_optional_int(raw.get("size_bytes")),
                    published_at=_optional_datetime(
                        raw.get("published_at")
                    ),
                    checksum_sha256=str(
                        raw.get("checksum_sha256", "")
                    ),
                )
            )

    raw_metadata = payload.get("raw_metadata")
    if not isinstance(raw_metadata, Mapping):
        raw_metadata = {}

    return UnifiedTender(
        source=TenderSource(str(payload.get("source", "custom"))),
        external_id=str(payload.get("external_id", "")),
        procurement_number=str(
            payload.get("procurement_number", "")
        ),
        title=str(payload.get("title", "")),
        customer=TenderCustomer(
            name=str(customer_payload.get("name", "")),
            inn=str(customer_payload.get("inn", "")),
            kpp=str(customer_payload.get("kpp", "")),
            region=str(customer_payload.get("region", "")),
            address=str(customer_payload.get("address", "")),
        ),
        source_url=str(payload.get("source_url", "")),
        published_at=_optional_datetime(payload.get("published_at")),
        application_deadline=_optional_datetime(
            payload.get("application_deadline")
        ),
        execution_deadline=_optional_date(
            payload.get("execution_deadline")
        ),
        price=price,
        status=_enum_or_default(
            TenderStatus,
            payload.get("status"),
            TenderStatus.UNKNOWN,
        ),
        procedure_type=_enum_or_default(
            TenderProcedureType,
            payload.get("procedure_type"),
            TenderProcedureType.UNKNOWN,
        ),
        law=str(payload.get("law", "")),
        region=str(payload.get("region", "")),
        description=str(payload.get("description", "")),
        classification_codes=tuple(
            str(item)
            for item in (payload.get("classification_codes") or ())
        ),
        tags=tuple(
            str(item) for item in (payload.get("tags") or ())
        ),
        documents=tuple(documents),
        raw_metadata=dict(raw_metadata),
    )


def query_to_payload(query: TenderSearchQuery) -> dict[str, Any]:
    return {
        "keywords": list(query.keywords),
        "excluded_keywords": list(query.excluded_keywords),
        "regions": list(query.regions),
        "laws": list(query.laws),
        "date_from": _optional_iso(query.date_from),
        "date_to": _optional_iso(query.date_to),
        "min_price": (
            str(Decimal(str(query.min_price)))
            if query.min_price is not None
            else None
        ),
        "max_price": (
            str(Decimal(str(query.max_price)))
            if query.max_price is not None
            else None
        ),
        "page": query.page,
        "page_size": query.page_size,
        "extra": _json_safe(query.extra),
    }


def _json_safe(value: object) -> object:
    """Round-trip through the existing safe encoder to normalize objects."""

    return json.loads(stable_json(value))


def _optional_iso(value: date | datetime | None) -> str:
    return value.isoformat() if value is not None else ""


def _optional_datetime(value: object) -> datetime | None:
    rendered = str(value or "").strip()
    if not rendered:
        return None
    return datetime.fromisoformat(rendered.replace("Z", "+00:00"))


def _optional_date(value: object) -> date | None:
    rendered = str(value or "").strip()
    if not rendered:
        return None
    return date.fromisoformat(rendered)


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _optional_bool(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    rendered = str(value).strip().casefold()
    if rendered in {"1", "true", "yes", "да"}:
        return True
    if rendered in {"0", "false", "no", "нет"}:
        return False
    return None


def _enum_or_default(enum_type, value: object, default):
    try:
        return enum_type(str(value))
    except ValueError:
        return default


__all__ = [
    "query_to_payload",
    "stable_hash",
    "stable_json",
    "tender_from_payload",
    "tender_to_payload",
]
