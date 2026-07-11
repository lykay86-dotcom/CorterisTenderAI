"""Canonical normalization and identity generation for tender records."""

from __future__ import annotations

from decimal import Decimal
import hashlib
import re
import unicodedata
from typing import Iterable, Mapping

from app.tenders.collector.codec import stable_hash, tender_to_payload
from app.tenders.collector.models import (
    NormalizedTender,
    TenderAliasType,
    TenderIdentityAlias,
)
from app.tenders.models import UnifiedTender


_OFFICIAL_NUMBER_KEYS = (
    "eis_number",
    "purchase_number",
    "procurement_number",
    "notice_number",
    "registry_number",
    "reg_number",
)


class TenderNormalizer:
    """Create stable comparison fields, hashes and multi-level aliases."""

    def normalize(self, tender: UnifiedTender) -> NormalizedTender:
        title = normalize_text(tender.title)
        customer = normalize_text(tender.customer.name)
        customer_inn = normalize_digits(tender.customer.inn)
        procurement_number = normalize_identifier(
            tender.procurement_number
        )
        external_id = normalize_identifier(tender.external_id)
        source = tender.source.value.casefold()

        official_number = _official_number(tender.raw_metadata)
        if not official_number and _looks_like_eis_number(
            procurement_number
        ):
            official_number = procurement_number

        duplicate_payload = {
            "title": title,
            "customer_inn": customer_inn,
            "customer": customer if not customer_inn else "",
            "price": _price_value(tender),
            "deadline": (
                tender.application_deadline.isoformat()
                if tender.application_deadline is not None
                else ""
            ),
        }
        duplicate_hash = stable_hash(duplicate_payload)
        content_hash = stable_hash(
            _content_payload(tender, title, customer, customer_inn)
        )

        aliases: list[TenderIdentityAlias] = []
        if official_number:
            aliases.append(
                TenderIdentityAlias(
                    key=f"eis:{official_number}",
                    alias_type=TenderAliasType.EIS_NUMBER,
                    strength=100,
                )
            )

        if procurement_number:
            if _looks_cross_source_number(procurement_number):
                aliases.append(
                    TenderIdentityAlias(
                        key=f"procurement:{procurement_number}",
                        alias_type=(
                            TenderAliasType.PROCUREMENT_NUMBER
                        ),
                        strength=95,
                    )
                )
            aliases.append(
                TenderIdentityAlias(
                    key=(
                        f"platform:{source}:{procurement_number}"
                    ),
                    alias_type=TenderAliasType.PLATFORM_NUMBER,
                    strength=85,
                )
            )

        aliases.append(
            TenderIdentityAlias(
                key=f"source:{source}:{external_id}",
                alias_type=TenderAliasType.SOURCE_EXTERNAL_ID,
                strength=90,
            )
        )

        if title and (customer_inn or customer):
            aliases.append(
                TenderIdentityAlias(
                    key=f"composite:{duplicate_hash}",
                    alias_type=TenderAliasType.COMPOSITE,
                    strength=65,
                )
            )
        aliases.append(
            TenderIdentityAlias(
                key=f"content:{_dedupe_content_hash(tender)}",
                alias_type=TenderAliasType.CONTENT,
                strength=55,
            )
        )

        unique_aliases = _unique_aliases(aliases)
        if official_number:
            canonical = f"procurement:{official_number}"
        elif procurement_number and _looks_cross_source_number(
            procurement_number
        ):
            canonical = f"procurement:{procurement_number}"
        else:
            canonical = min(
                unique_aliases,
                key=lambda item: (-item.strength, item.key),
            ).key

        return NormalizedTender(
            tender=tender,
            canonical_key=canonical,
            aliases=unique_aliases,
            normalized_title=title,
            normalized_customer=customer,
            normalized_customer_inn=customer_inn,
            normalized_procurement_number=procurement_number,
            content_hash=content_hash,
            duplicate_hash=duplicate_hash,
            completeness_score=_completeness_score(tender),
        )

    def normalize_many(
        self,
        tenders: Iterable[UnifiedTender],
    ) -> tuple[NormalizedTender, ...]:
        return tuple(self.normalize(tender) for tender in tenders)


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    normalized = normalized.casefold().replace("ё", "е")
    normalized = re.sub(r"[^0-9a-zа-я]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def normalize_identifier(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    normalized = normalized.casefold().replace("ё", "е")
    return "".join(
        character
        for character in normalized
        if character.isalnum() or character in {"-", "_", ".", "/"}
    )


def normalize_digits(value: str) -> str:
    return "".join(character for character in str(value or "") if character.isdigit())


def _official_number(metadata: Mapping[str, object]) -> str:
    for key in _OFFICIAL_NUMBER_KEYS:
        raw = metadata.get(key)
        if raw not in (None, ""):
            normalized = normalize_identifier(str(raw))
            if normalized:
                return normalized
    return ""


def _looks_like_eis_number(value: str) -> bool:
    digits = normalize_digits(value)
    return len(digits) >= 18 and digits == value.replace("-", "")


def _looks_cross_source_number(value: str) -> bool:
    digits = normalize_digits(value)
    return len(digits) >= 12 or _looks_like_eis_number(value)


def _price_value(tender: UnifiedTender) -> str:
    if tender.price is None:
        return ""
    return f"{tender.price.amount}:{tender.price.currency.casefold()}"


def _dedupe_content_hash(tender: UnifiedTender) -> str:
    payload = {
        "title": normalize_text(tender.title),
        "customer": (
            normalize_digits(tender.customer.inn)
            or normalize_text(tender.customer.name)
        ),
        "price": _price_value(tender),
        "deadline": (
            tender.application_deadline.isoformat()
            if tender.application_deadline is not None
            else ""
        ),
        "law": normalize_text(tender.law),
        "region": normalize_text(tender.region),
    }
    return stable_hash(payload)


def _content_payload(
    tender: UnifiedTender,
    title: str,
    customer: str,
    customer_inn: str,
) -> dict[str, object]:
    documents = sorted(
        (
            {
                "id": normalize_identifier(item.id),
                "name": normalize_text(item.name),
                "url": item.url.strip(),
                "checksum": item.checksum_sha256.casefold(),
                "size": item.size_bytes,
            }
            for item in tender.documents
        ),
        key=lambda item: (
            str(item["checksum"]),
            str(item["url"]),
            str(item["id"]),
        ),
    )
    return {
        "title": title,
        "customer": customer,
        "customer_inn": customer_inn,
        "price": _price_value(tender),
        "published_at": (
            tender.published_at.isoformat()
            if tender.published_at is not None
            else ""
        ),
        "application_deadline": (
            tender.application_deadline.isoformat()
            if tender.application_deadline is not None
            else ""
        ),
        "execution_deadline": (
            tender.execution_deadline.isoformat()
            if tender.execution_deadline is not None
            else ""
        ),
        "status": tender.status.value,
        "procedure_type": tender.procedure_type.value,
        "law": normalize_text(tender.law),
        "region": normalize_text(tender.region),
        "description": normalize_text(tender.description),
        "classification_codes": sorted(
            normalize_identifier(item)
            for item in tender.classification_codes
        ),
        "documents": documents,
    }


def _completeness_score(tender: UnifiedTender) -> int:
    checks = (
        bool(tender.title.strip()),
        bool(tender.description.strip()),
        bool(tender.customer.name.strip()),
        bool(tender.customer.inn.strip()),
        bool(tender.region.strip() or tender.customer.region.strip()),
        tender.price is not None,
        tender.published_at is not None,
        tender.application_deadline is not None,
        bool(tender.law.strip()),
        bool(tender.documents),
        bool(tender.classification_codes),
        bool(tender.tags),
    )
    return round(sum(checks) / len(checks) * 100)


def _unique_aliases(
    aliases: Iterable[TenderIdentityAlias],
) -> tuple[TenderIdentityAlias, ...]:
    by_key: dict[str, TenderIdentityAlias] = {}
    for alias in aliases:
        current = by_key.get(alias.key)
        if current is None or alias.strength > current.strength:
            by_key[alias.key] = alias
    return tuple(
        sorted(
            by_key.values(),
            key=lambda item: (-item.strength, item.key),
        )
    )


__all__ = [
    "TenderNormalizer",
    "normalize_digits",
    "normalize_identifier",
    "normalize_text",
]
