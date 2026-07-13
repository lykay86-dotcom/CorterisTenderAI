"""Multi-level cross-provider tender deduplication and merging."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from typing import Iterable

from app.tenders.collector.models import (
    DeduplicationGroup,
    DeduplicationMatchLevel,
    DeduplicationResult,
    NormalizedTender,
    TenderAliasType,
    TenderIdentityAlias,
)
from app.tenders.collector.normalizer import TenderNormalizer
from app.tenders.models import (
    TenderCustomer,
    TenderDocument,
    TenderMoney,
    TenderSource,
    TenderStatus,
    UnifiedTender,
)


_SOURCE_PRIORITY = {
    TenderSource.EIS: 100,
    TenderSource.SBER_A: 80,
    TenderSource.RTS_TENDER: 80,
    TenderSource.ROSELTORG: 80,
    TenderSource.GAZPROMBANK: 75,
    TenderSource.B2B_CENTER: 70,
    TenderSource.TEK_TORG: 70,
    TenderSource.COMMERCIAL: 60,
    TenderSource.CUSTOM: 50,
}

_STATUS_PRIORITY = {
    TenderStatus.CANCELLED: 100,
    TenderStatus.COMPLETED: 90,
    TenderStatus.REVIEW: 80,
    TenderStatus.APPLICATIONS_CLOSED: 70,
    TenderStatus.ACCEPTING_APPLICATIONS: 60,
    TenderStatus.PUBLISHED: 50,
    TenderStatus.UNKNOWN: 0,
}

_ALIAS_MATCH_LEVEL = {
    TenderAliasType.EIS_NUMBER: DeduplicationMatchLevel.EIS_NUMBER,
    TenderAliasType.PROCUREMENT_NUMBER: (DeduplicationMatchLevel.PROCUREMENT_NUMBER),
    TenderAliasType.PLATFORM_NUMBER: (DeduplicationMatchLevel.PLATFORM_NUMBER),
    TenderAliasType.SOURCE_EXTERNAL_ID: (DeduplicationMatchLevel.SOURCE_EXTERNAL_ID),
    TenderAliasType.COMPOSITE: DeduplicationMatchLevel.COMPOSITE,
    TenderAliasType.CONTENT: DeduplicationMatchLevel.CONTENT,
}


class TenderDeduplicator:
    """Union records sharing any supported identity alias."""

    def __init__(self, normalizer: TenderNormalizer | None = None) -> None:
        self.normalizer = normalizer or TenderNormalizer()

    def deduplicate(
        self,
        items: Iterable[NormalizedTender | UnifiedTender],
    ) -> DeduplicationResult:
        normalized = tuple(
            item if isinstance(item, NormalizedTender) else self.normalizer.normalize(item)
            for item in items
        )
        if not normalized:
            return DeduplicationResult(items=(), groups=(), raw_count=0)

        parent = list(range(len(normalized)))

        def find(index: int) -> int:
            while parent[index] != index:
                parent[index] = parent[parent[index]]
                index = parent[index]
            return index

        def union(left: int, right: int) -> None:
            root_left = find(left)
            root_right = find(right)
            if root_left != root_right:
                parent[root_right] = root_left

        alias_owner: dict[str, int] = {}
        for index, item in enumerate(normalized):
            for alias in item.aliases:
                owner = alias_owner.get(alias.key)
                if owner is None:
                    alias_owner[alias.key] = index
                else:
                    union(index, owner)

        grouped: dict[int, list[NormalizedTender]] = {}
        for index, item in enumerate(normalized):
            grouped.setdefault(find(index), []).append(item)

        groups: list[DeduplicationGroup] = []
        merged_items: list[NormalizedTender] = []
        for source_items in grouped.values():
            merged = self._merge_group(tuple(source_items))
            levels = _match_levels(source_items)
            groups.append(
                DeduplicationGroup(
                    canonical_key=merged.canonical_key,
                    item=merged,
                    source_items=tuple(source_items),
                    match_levels=levels,
                )
            )
            merged_items.append(merged)

        groups.sort(key=lambda item: item.canonical_key)
        merged_items = [group.item for group in groups]
        return DeduplicationResult(
            items=tuple(merged_items),
            groups=tuple(groups),
            raw_count=len(normalized),
        )

    def _merge_group(
        self,
        items: tuple[NormalizedTender, ...],
    ) -> NormalizedTender:
        if len(items) == 1:
            return items[0]

        representative = max(items, key=_representative_priority)
        source_tenders = tuple(item.tender for item in items)
        base = representative.tender

        documents = _merge_documents(source_tenders)
        metadata = dict(base.raw_metadata)
        metadata["collector_sources"] = [
            {
                "source": item.source.value,
                "external_id": item.external_id,
                "procurement_number": item.procurement_number,
                "source_url": item.source_url,
            }
            for item in sorted(
                source_tenders,
                key=lambda tender: (
                    tender.source.value,
                    tender.external_id,
                ),
            )
        ]
        metadata["collector_merged_count"] = len(source_tenders)
        metadata["collector_identity_keys"] = sorted(
            {alias.key for normalized in items for alias in normalized.aliases}
        )

        merged_tender = UnifiedTender(
            source=base.source,
            external_id=base.external_id,
            procurement_number=_best_procurement_number(items),
            title=_longest_nonempty(tender.title for tender in source_tenders) or base.title,
            customer=_merge_customer(source_tenders, base.customer),
            source_url=base.source_url,
            published_at=_earliest_datetime(tender.published_at for tender in source_tenders),
            application_deadline=_latest_datetime(
                tender.application_deadline for tender in source_tenders
            ),
            execution_deadline=_latest_date(tender.execution_deadline for tender in source_tenders),
            price=_best_price(source_tenders, base.price),
            status=max(
                (tender.status for tender in source_tenders),
                key=lambda value: _STATUS_PRIORITY[value],
            ),
            procedure_type=base.procedure_type,
            law=_longest_nonempty(tender.law for tender in source_tenders),
            region=_longest_nonempty(tender.region for tender in source_tenders),
            description=_longest_nonempty(tender.description for tender in source_tenders),
            classification_codes=_ordered_unique(
                code for tender in source_tenders for code in tender.classification_codes
            ),
            tags=_ordered_unique(tag for tender in source_tenders for tag in tender.tags),
            documents=documents,
            raw_metadata=metadata,
        )
        normalized = self.normalizer.normalize(merged_tender)

        all_aliases = _unique_aliases(alias for item in items for alias in item.aliases)
        procurement_aliases = tuple(
            alias.key
            for alias in all_aliases
            if alias.alias_type == TenderAliasType.PROCUREMENT_NUMBER
        )
        canonical = (
            sorted(procurement_aliases)[0]
            if procurement_aliases
            else min(
                all_aliases,
                key=lambda alias: (-alias.strength, alias.key),
            ).key
        )
        return replace(
            normalized,
            canonical_key=canonical,
            aliases=all_aliases,
            completeness_score=max(
                normalized.completeness_score,
                *(item.completeness_score for item in items),
            ),
        )


def _representative_priority(
    item: NormalizedTender,
) -> tuple[int, int, int, str]:
    return (
        _SOURCE_PRIORITY.get(item.tender.source, 0),
        item.completeness_score,
        len(item.tender.documents),
        item.tender.identity_key,
    )


def _match_levels(
    items: Iterable[NormalizedTender],
) -> tuple[DeduplicationMatchLevel, ...]:
    items_tuple = tuple(items)
    if len(items_tuple) <= 1:
        return (DeduplicationMatchLevel.SINGLE,)

    counts: dict[str, int] = {}
    types: dict[str, TenderAliasType] = {}
    for item in items_tuple:
        for alias in item.aliases:
            counts[alias.key] = counts.get(alias.key, 0) + 1
            types[alias.key] = alias.alias_type

    levels = {_ALIAS_MATCH_LEVEL[types[key]] for key, count in counts.items() if count > 1}
    return tuple(sorted(levels, key=lambda value: value.value))


def _best_procurement_number(
    items: Iterable[NormalizedTender],
) -> str:
    candidates = sorted(
        (item for item in items if item.normalized_procurement_number),
        key=lambda item: (
            -max(alias.strength for alias in item.aliases),
            -len(item.normalized_procurement_number),
            item.normalized_procurement_number,
        ),
    )
    return (
        candidates[0].tender.procurement_number
        if candidates
        else tuple(items)[0].tender.procurement_number
    )


def _merge_customer(
    tenders: Iterable[UnifiedTender],
    fallback: TenderCustomer,
) -> TenderCustomer:
    tenders_tuple = tuple(tenders)
    return TenderCustomer(
        name=_longest_nonempty(tender.customer.name for tender in tenders_tuple) or fallback.name,
        inn=_longest_nonempty(tender.customer.inn for tender in tenders_tuple),
        kpp=_longest_nonempty(tender.customer.kpp for tender in tenders_tuple),
        region=_longest_nonempty(tender.customer.region for tender in tenders_tuple),
        address=_longest_nonempty(tender.customer.address for tender in tenders_tuple),
    )


def _best_price(
    tenders: Iterable[UnifiedTender],
    fallback: TenderMoney | None,
) -> TenderMoney | None:
    prices = [tender.price for tender in tenders if tender.price is not None]
    if not prices:
        return fallback
    # Prefer RUB and exact decimal data from the highest amount only when
    # sources disagree. Change tracking will expose later price changes.
    return max(
        prices,
        key=lambda price: (
            int(price.currency.casefold() == "rub"),
            price.amount,
        ),
    )


def _merge_documents(
    tenders: Iterable[UnifiedTender],
) -> tuple[TenderDocument, ...]:
    by_key: dict[str, TenderDocument] = {}
    for tender in tenders:
        for document in tender.documents:
            key = (
                f"sha:{document.checksum_sha256.casefold()}"
                if document.checksum_sha256
                else f"url:{document.url.strip()}"
            )
            current = by_key.get(key)
            if current is None or _document_priority(document) > _document_priority(current):
                by_key[key] = document
    return tuple(sorted(by_key.values(), key=lambda item: (item.name.casefold(), item.url)))


def _document_priority(document: TenderDocument) -> tuple[int, int, int]:
    return (
        int(bool(document.checksum_sha256)),
        int(document.size_bytes is not None),
        len(document.name),
    )


def _longest_nonempty(values: Iterable[str]) -> str:
    candidates = [str(value).strip() for value in values if str(value).strip()]
    return max(candidates, key=len, default="")


def _earliest_datetime(
    values: Iterable[datetime | None],
) -> datetime | None:
    actual = [value for value in values if value is not None]
    comparable = _preferred_datetime_group(actual)
    return min(comparable) if comparable else None


def _latest_datetime(
    values: Iterable[datetime | None],
) -> datetime | None:
    actual = [value for value in values if value is not None]
    comparable = _preferred_datetime_group(actual)
    return max(comparable) if comparable else None


def _preferred_datetime_group(values: list[datetime]) -> list[datetime]:
    """Prefer timezone-confirmed candidates without inventing a source zone."""

    aware = [
        value
        for value in values
        if value.tzinfo is not None and value.utcoffset() is not None
    ]
    return aware or values


def _latest_date(values: Iterable[date | None]) -> date | None:
    actual = [value for value in values if value is not None]
    return max(actual) if actual else None


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        rendered = str(value).strip()
        identity = rendered.casefold()
        if not rendered or identity in seen:
            continue
        seen.add(identity)
        result.append(rendered)
    return tuple(result)


def _unique_aliases(
    aliases: Iterable[TenderIdentityAlias],
) -> tuple[TenderIdentityAlias, ...]:
    by_key: dict[str, TenderIdentityAlias] = {}
    for alias in aliases:
        current = by_key.get(alias.key)
        if current is None or alias.strength > current.strength:
            by_key[alias.key] = alias
    return tuple(sorted(by_key.values(), key=lambda item: (-item.strength, item.key)))


__all__ = ["TenderDeduplicator"]
