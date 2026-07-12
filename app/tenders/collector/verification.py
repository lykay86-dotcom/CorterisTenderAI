"""Field-level provenance, trust resolution and conflict detection.

This module is intentionally independent from provider implementations and
persistence. Providers may attach field-level metadata through
``UnifiedTender.raw_metadata['field_provenance']``; when they do not, a
conservative source policy is applied.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal
from enum import IntEnum, StrEnum
import hashlib
import json
from typing import Callable, Iterable, Mapping, Sequence

from app.tenders.collector.codec import stable_json
from app.tenders.collector.models import (
    DeduplicationGroup,
    DeduplicationResult,
    NormalizedTender,
)
from app.tenders.collector.normalizer import TenderNormalizer, normalize_text
from app.tenders.models import (
    TenderCustomer,
    TenderMoney,
    TenderSource,
    TenderStatus,
    UnifiedTender,
)


class SourceTrustLevel(IntEnum):
    """Deterministic source priority; larger values are more authoritative."""

    UNKNOWN = 0
    AGGREGATOR = 100
    PUBLIC_CARD = 200
    CUSTOMER_SITE = 300
    OFFICIAL_API = 400
    OFFICIAL_PLATFORM = 500
    EIS = 600
    OFFICIAL_DOCUMENTATION = 700


class TenderVerificationStatus(StrEnum):
    MISSING = "missing"
    UNVERIFIED = "unverified"
    AGGREGATOR_ONLY = "aggregator_only"
    PUBLIC_CARD = "public_card"
    CUSTOMER_SITE = "customer_site"
    VERIFIED_OFFICIAL_API = "verified_official_api"
    VERIFIED_PLATFORM = "verified_platform"
    VERIFIED_EIS = "verified_eis"
    VERIFIED_DOCUMENTATION = "verified_documentation"
    INCOMPLETE = "incomplete"
    CONFLICT = "conflict"


class FieldConflictType(StrEnum):
    OFFICIAL_OFFICIAL = "official_official"
    SAME_PRIORITY = "same_priority"
    OFFICIAL_LOWER_TRUST = "official_lower_trust"
    MULTI_SOURCE = "multi_source"


@dataclass(frozen=True, slots=True)
class FieldCandidate:
    candidate_id: str
    field_name: str
    value: object
    normalized_value: str
    value_hash: str
    source_id: str
    source_url: str
    retrieved_at: str
    trust_level: SourceTrustLevel
    official: bool
    verified: bool
    confidence: float
    selected: bool = False
    historical: bool = False

    def __post_init__(self) -> None:
        if not self.candidate_id.strip():
            raise ValueError("candidate_id must not be empty")
        if not self.field_name.strip():
            raise ValueError("field_name must not be empty")
        if not self.source_id.strip():
            raise ValueError("source_id must not be empty")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")

    def with_selected(self, value: bool) -> "FieldCandidate":
        return replace(self, selected=bool(value))

    def value_payload(self) -> object:
        return _value_payload(self.value)


@dataclass(frozen=True, slots=True)
class FieldProvenance:
    field_name: str
    value_hash: str
    source_id: str
    source_url: str
    retrieved_at: str
    verified: bool
    official: bool
    confidence: float
    trust_level: SourceTrustLevel
    candidate_id: str


@dataclass(frozen=True, slots=True)
class FieldConflict:
    conflict_id: str
    field_name: str
    conflict_type: FieldConflictType
    candidate_ids: tuple[str, ...]
    selected_candidate_id: str
    detected_at: str
    critical: bool
    unresolved: bool
    message: str

    def __post_init__(self) -> None:
        if len(self.candidate_ids) < 2:
            raise ValueError("a conflict needs at least two candidates")
        if self.selected_candidate_id not in self.candidate_ids:
            raise ValueError("selected candidate must belong to conflict")


@dataclass(frozen=True, slots=True)
class TenderVerificationState:
    registry_key: str
    verification_run_id: str
    status: TenderVerificationStatus
    last_verified_at: str
    critical_field_count: int
    verified_field_count: int
    official_field_count: int
    missing_fields: tuple[str, ...]
    conflict_count: int
    unresolved_conflict_count: int
    minimum_confidence: float


@dataclass(frozen=True, slots=True)
class TenderVerificationHistory:
    registry_key: str
    tender: UnifiedTender
    selected_candidates: Mapping[str, FieldCandidate]


@dataclass(frozen=True, slots=True)
class TenderVerificationResult:
    canonical_key: str
    tender: UnifiedTender
    candidates: tuple[FieldCandidate, ...]
    provenance: tuple[FieldProvenance, ...]
    conflicts: tuple[FieldConflict, ...]
    status: TenderVerificationStatus
    verified_at: str
    missing_fields: tuple[str, ...]
    critical_field_count: int
    verified_field_count: int
    official_field_count: int
    minimum_confidence: float

    @property
    def conflict_count(self) -> int:
        return len(self.conflicts)

    @property
    def unresolved_conflict_count(self) -> int:
        return sum(item.unresolved for item in self.conflicts)

    @property
    def selected_candidates(self) -> tuple[FieldCandidate, ...]:
        return tuple(item for item in self.candidates if item.selected)


@dataclass(frozen=True, slots=True)
class VerificationBatchResult:
    deduplication: DeduplicationResult
    items: tuple[TenderVerificationResult, ...]
    verified_at: str

    @property
    def by_canonical_key(self) -> Mapping[str, TenderVerificationResult]:
        return {item.canonical_key: item for item in self.items}

    @property
    def verified_field_count(self) -> int:
        return sum(item.verified_field_count for item in self.items)

    @property
    def conflict_count(self) -> int:
        return sum(item.conflict_count for item in self.items)

    @property
    def unresolved_conflict_count(self) -> int:
        return sum(item.unresolved_conflict_count for item in self.items)


HistoryLoader = Callable[[NormalizedTender], TenderVerificationHistory | None]


_CRITICAL_FIELDS = (
    "procurement_number",
    "price",
    "application_deadline",
    "status",
    "law",
    "customer.name",
    "customer.inn",
    "platform",
    "application_security",
    "contract_security",
    "documentation_url",
)

_MODEL_FIELDS = {
    "procurement_number",
    "price",
    "application_deadline",
    "status",
    "law",
    "customer.name",
    "customer.inn",
    "source_url",
}

_OFFICIAL_PLATFORM_SOURCES = {
    TenderSource.MOS_SUPPLIER,
    TenderSource.SBER_A,
    TenderSource.RTS_TENDER,
    TenderSource.ROSELTORG,
    TenderSource.B2B_CENTER,
    TenderSource.TEK_TORG,
    TenderSource.GAZPROMBANK,
    TenderSource.FABRIKANT,
    TenderSource.OTC,
}

_CONFIDENCE = {
    SourceTrustLevel.OFFICIAL_DOCUMENTATION: 1.0,
    SourceTrustLevel.EIS: 0.98,
    SourceTrustLevel.OFFICIAL_PLATFORM: 0.95,
    SourceTrustLevel.OFFICIAL_API: 0.92,
    SourceTrustLevel.CUSTOMER_SITE: 0.84,
    SourceTrustLevel.PUBLIC_CARD: 0.68,
    SourceTrustLevel.AGGREGATOR: 0.40,
    SourceTrustLevel.UNKNOWN: 0.20,
}


class TenderVerificationService:
    """Resolve critical fields without allowing lower-trust downgrades."""

    def __init__(
        self,
        *,
        normalizer: TenderNormalizer | None = None,
        history_loader: HistoryLoader | None = None,
        critical_fields: Sequence[str] = _CRITICAL_FIELDS,
    ) -> None:
        self.normalizer = normalizer or TenderNormalizer()
        self.history_loader = history_loader
        self.critical_fields = tuple(dict.fromkeys(critical_fields))

    def verify(
        self,
        result: DeduplicationResult,
        *,
        observed_at: str | None = None,
    ) -> VerificationBatchResult:
        moment = observed_at or _utc_now()
        verified_groups: list[DeduplicationGroup] = []
        verified_items: list[NormalizedTender] = []
        verification_results: list[TenderVerificationResult] = []

        for group in result.groups:
            history = (
                self.history_loader(group.item)
                if self.history_loader is not None
                else None
            )
            verification = self.verify_group(
                group,
                observed_at=moment,
                history=history,
            )
            normalized = self.normalizer.normalize(verification.tender)
            normalized = replace(
                normalized,
                canonical_key=group.item.canonical_key,
                aliases=group.item.aliases,
                completeness_score=max(
                    group.item.completeness_score,
                    normalized.completeness_score,
                ),
            )
            verified_group = replace(group, item=normalized)
            verified_groups.append(verified_group)
            verified_items.append(normalized)
            verification_results.append(
                replace(
                    verification,
                    canonical_key=normalized.canonical_key,
                    tender=normalized.tender,
                )
            )

        deduplication = DeduplicationResult(
            items=tuple(verified_items),
            groups=tuple(verified_groups),
            raw_count=result.raw_count,
        )
        return VerificationBatchResult(
            deduplication=deduplication,
            items=tuple(verification_results),
            verified_at=moment,
        )

    def verify_group(
        self,
        group: DeduplicationGroup,
        *,
        observed_at: str,
        history: TenderVerificationHistory | None = None,
    ) -> TenderVerificationResult:
        candidates: list[FieldCandidate] = []
        for source_item in group.source_items:
            candidates.extend(
                self._candidates_for_tender(
                    source_item.tender,
                    observed_at=observed_at,
                )
            )
        if history is not None:
            candidates.extend(
                self._historical_candidates(history)
            )

        by_field: dict[str, list[FieldCandidate]] = {}
        for candidate in candidates:
            by_field.setdefault(candidate.field_name, []).append(candidate)

        selected_by_field: dict[str, FieldCandidate] = {}
        conflicts: list[FieldConflict] = []
        final_candidates: list[FieldCandidate] = []
        missing: list[str] = []

        for field_name in self.critical_fields:
            field_candidates = _deduplicate_candidates(
                by_field.get(field_name, ())
            )
            if not field_candidates:
                missing.append(field_name)
                continue
            selected = max(field_candidates, key=_candidate_priority)
            selected_by_field[field_name] = selected
            selected_candidates = tuple(
                item.with_selected(
                    item.candidate_id == selected.candidate_id
                )
                for item in field_candidates
            )
            final_candidates.extend(selected_candidates)
            conflict = _build_conflict(
                field_name,
                selected_candidates,
                selected,
                observed_at,
                critical=field_name in self.critical_fields,
            )
            if conflict is not None:
                conflicts.append(conflict)

        tender = _apply_selected_values(
            group.item.tender,
            selected_by_field,
        )
        provenance = tuple(
            FieldProvenance(
                field_name=item.field_name,
                value_hash=item.value_hash,
                source_id=item.source_id,
                source_url=item.source_url,
                retrieved_at=item.retrieved_at,
                verified=item.verified,
                official=item.official,
                confidence=item.confidence,
                trust_level=item.trust_level,
                candidate_id=item.candidate_id,
            )
            for item in final_candidates
            if item.selected
        )
        unresolved = any(item.unresolved for item in conflicts)
        selected = tuple(selected_by_field.values())
        verified_count = sum(item.verified for item in selected)
        official_count = sum(item.official for item in selected)
        minimum_confidence = min(
            (item.confidence for item in selected),
            default=0.0,
        )
        status = _verification_status(
            selected,
            missing_fields=tuple(missing),
            unresolved_conflict=unresolved,
        )
        return TenderVerificationResult(
            canonical_key=group.item.canonical_key,
            tender=tender,
            candidates=tuple(
                sorted(
                    final_candidates,
                    key=lambda item: (
                        item.field_name,
                        not item.selected,
                        -int(item.trust_level),
                        item.source_id,
                    ),
                )
            ),
            provenance=provenance,
            conflicts=tuple(conflicts),
            status=status,
            verified_at=observed_at,
            missing_fields=tuple(missing),
            critical_field_count=len(self.critical_fields),
            verified_field_count=verified_count,
            official_field_count=official_count,
            minimum_confidence=minimum_confidence,
        )

    def _candidates_for_tender(
        self,
        tender: UnifiedTender,
        *,
        observed_at: str,
    ) -> tuple[FieldCandidate, ...]:
        values = _critical_values(tender)
        result: list[FieldCandidate] = []
        for field_name, value in values.items():
            if _is_missing(value):
                continue
            metadata = _field_metadata(tender, field_name)
            trust = _trust_level(tender, metadata)
            source_id = str(
                metadata.get("source_id")
                or tender.source.value
            ).strip().casefold()
            source_url = str(
                metadata.get("source_url")
                or tender.source_url
            ).strip()
            retrieved_at = str(
                metadata.get("retrieved_at")
                or tender.raw_metadata.get("retrieved_at")
                or tender.raw_metadata.get("fetched_at")
                or observed_at
            ).strip()
            official = _metadata_bool(
                metadata.get("official"),
                default=trust
                >= SourceTrustLevel.OFFICIAL_API,
            )
            verified = _metadata_bool(
                metadata.get("verified"),
                default=trust
                >= SourceTrustLevel.CUSTOMER_SITE,
            )
            confidence = _metadata_float(
                metadata.get("confidence"),
                default=_CONFIDENCE[trust],
            )
            normalized = _normalize_value(field_name, value)
            value_hash = hashlib.sha256(
                normalized.encode("utf-8")
            ).hexdigest()
            candidate_id = _candidate_id(
                field_name,
                value_hash,
                source_id,
                source_url,
                retrieved_at,
            )
            result.append(
                FieldCandidate(
                    candidate_id=candidate_id,
                    field_name=field_name,
                    value=value,
                    normalized_value=normalized,
                    value_hash=value_hash,
                    source_id=source_id,
                    source_url=source_url,
                    retrieved_at=retrieved_at,
                    trust_level=trust,
                    official=official,
                    verified=verified,
                    confidence=confidence,
                )
            )
        return tuple(result)

    def _historical_candidates(
        self,
        history: TenderVerificationHistory,
    ) -> tuple[FieldCandidate, ...]:
        values = _critical_values(history.tender)
        result: list[FieldCandidate] = []
        for field_name, stored in history.selected_candidates.items():
            value = values.get(field_name, stored.value)
            if _is_missing(value):
                continue
            normalized = _normalize_value(field_name, value)
            value_hash = hashlib.sha256(
                normalized.encode("utf-8")
            ).hexdigest()
            result.append(
                replace(
                    stored,
                    value=value,
                    normalized_value=normalized,
                    value_hash=value_hash,
                    candidate_id=_candidate_id(
                        field_name,
                        value_hash,
                        stored.source_id,
                        stored.source_url,
                        stored.retrieved_at,
                        historical=True,
                    ),
                    selected=False,
                    historical=True,
                )
            )
        return tuple(result)


def _critical_values(tender: UnifiedTender) -> dict[str, object]:
    metadata = tender.raw_metadata
    documentation_url = str(
        metadata.get("documentation_url") or ""
    ).strip()
    if not documentation_url and tender.documents:
        documentation_url = tender.documents[0].url
    return {
        "procurement_number": tender.procurement_number,
        "price": tender.price,
        "application_deadline": tender.application_deadline,
        "status": tender.status,
        "law": tender.law,
        "customer.name": tender.customer.name,
        "customer.inn": tender.customer.inn,
        "platform": str(
            metadata.get("platform_name")
            or tender.source.value
        ),
        "application_security": metadata.get(
            "application_security"
        ),
        "contract_security": metadata.get(
            "contract_security"
        ),
        "documentation_url": documentation_url,
        "source_url": tender.source_url,
    }


def _field_metadata(
    tender: UnifiedTender,
    field_name: str,
) -> Mapping[str, object]:
    raw = tender.raw_metadata.get("field_provenance")
    if isinstance(raw, Mapping):
        value = raw.get(field_name)
        if isinstance(value, Mapping):
            return value
    return {}


def _trust_level(
    tender: UnifiedTender,
    metadata: Mapping[str, object],
) -> SourceTrustLevel:
    explicit = metadata.get("trust_level")
    if explicit in (None, ""):
        explicit = tender.raw_metadata.get("source_trust")
    if explicit not in (None, ""):
        parsed = _parse_trust_level(explicit)
        if parsed is not None:
            return parsed

    kind = str(
        metadata.get("source_kind")
        or tender.raw_metadata.get("source_kind")
        or ""
    ).strip().casefold()
    if kind in {
        "official_document",
        "official_documentation",
        "procurement_documentation",
    }:
        return SourceTrustLevel.OFFICIAL_DOCUMENTATION
    if kind in {"eis", "official_eis"}:
        return SourceTrustLevel.EIS
    if kind in {"official_platform", "official_etp"}:
        return SourceTrustLevel.OFFICIAL_PLATFORM
    if kind in {"official_api", "commercial_api"}:
        return SourceTrustLevel.OFFICIAL_API
    if kind in {"customer_site", "official_customer_site"}:
        return SourceTrustLevel.CUSTOMER_SITE
    if kind in {"aggregator", "discovery_aggregator"}:
        return SourceTrustLevel.AGGREGATOR
    if kind in {"public_card", "public_html"}:
        return SourceTrustLevel.PUBLIC_CARD

    if bool(tender.raw_metadata.get("aggregator")) or bool(
        tender.raw_metadata.get("discovery_only")
    ):
        return SourceTrustLevel.AGGREGATOR
    if tender.source == TenderSource.EIS:
        return SourceTrustLevel.EIS
    if tender.source in _OFFICIAL_PLATFORM_SOURCES:
        connection_mode = str(
            tender.raw_metadata.get("connection_mode") or ""
        ).casefold()
        if "official_api" in connection_mode:
            return SourceTrustLevel.OFFICIAL_API
        return SourceTrustLevel.OFFICIAL_PLATFORM
    if bool(tender.raw_metadata.get("official_customer_site")):
        return SourceTrustLevel.CUSTOMER_SITE
    if tender.source == TenderSource.CUSTOM:
        return SourceTrustLevel.PUBLIC_CARD
    return SourceTrustLevel.PUBLIC_CARD


def _parse_trust_level(value: object) -> SourceTrustLevel | None:
    if isinstance(value, SourceTrustLevel):
        return value
    if isinstance(value, int):
        try:
            return SourceTrustLevel(value)
        except ValueError:
            return None
    rendered = str(value).strip().casefold()
    if rendered.isdigit():
        try:
            return SourceTrustLevel(int(rendered))
        except ValueError:
            return None
    aliases = {
        "official_document": SourceTrustLevel.OFFICIAL_DOCUMENTATION,
        "official_documentation": SourceTrustLevel.OFFICIAL_DOCUMENTATION,
        "eis": SourceTrustLevel.EIS,
        "official_platform": SourceTrustLevel.OFFICIAL_PLATFORM,
        "official_etp": SourceTrustLevel.OFFICIAL_PLATFORM,
        "official_api": SourceTrustLevel.OFFICIAL_API,
        "customer_site": SourceTrustLevel.CUSTOMER_SITE,
        "public_card": SourceTrustLevel.PUBLIC_CARD,
        "aggregator": SourceTrustLevel.AGGREGATOR,
        "unknown": SourceTrustLevel.UNKNOWN,
    }
    return aliases.get(rendered)


def _candidate_priority(
    candidate: FieldCandidate,
) -> tuple[int, int, float, tuple[int, ...], int, str]:
    return (
        int(candidate.trust_level),
        int(candidate.verified),
        candidate.confidence,
        _datetime_key(candidate.retrieved_at),
        int(not candidate.historical),
        candidate.candidate_id,
    )


def _datetime_key(value: str) -> tuple[int, ...]:
    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(
                tzinfo=None
            )
        return (
            parsed.year,
            parsed.month,
            parsed.day,
            parsed.hour,
            parsed.minute,
            parsed.second,
            parsed.microsecond,
        )
    except (ValueError, TypeError):
        return (0, 0, 0, 0, 0, 0, 0)


def _deduplicate_candidates(
    candidates: Iterable[FieldCandidate],
) -> tuple[FieldCandidate, ...]:
    by_identity: dict[tuple[str, str], FieldCandidate] = {}
    for candidate in candidates:
        key = (candidate.source_id, candidate.value_hash)
        current = by_identity.get(key)
        if current is None or _candidate_priority(
            candidate
        ) > _candidate_priority(current):
            by_identity[key] = candidate
    return tuple(by_identity.values())


def _build_conflict(
    field_name: str,
    candidates: Sequence[FieldCandidate],
    selected: FieldCandidate,
    detected_at: str,
    *,
    critical: bool,
) -> FieldConflict | None:
    distinct = {
        candidate.normalized_value for candidate in candidates
    }
    if len(distinct) <= 1:
        return None
    top_trust = max(candidate.trust_level for candidate in candidates)
    top_values = {
        candidate.normalized_value
        for candidate in candidates
        if candidate.trust_level == top_trust
    }
    top_official = [
        candidate
        for candidate in candidates
        if candidate.trust_level == top_trust
        and candidate.official
    ]
    unresolved = len(top_values) > 1
    if unresolved and len(top_official) >= 2:
        conflict_type = FieldConflictType.OFFICIAL_OFFICIAL
    elif unresolved:
        conflict_type = FieldConflictType.SAME_PRIORITY
    elif selected.official:
        conflict_type = FieldConflictType.OFFICIAL_LOWER_TRUST
    else:
        conflict_type = FieldConflictType.MULTI_SOURCE
    candidate_ids = tuple(
        sorted(candidate.candidate_id for candidate in candidates)
    )
    conflict_id = hashlib.sha256(
        "|".join(
            (field_name, selected.candidate_id, *candidate_ids)
        ).encode("utf-8")
    ).hexdigest()
    message = (
        f"Поле «{field_name}» содержит {len(distinct)} "
        "различающихся значения. "
        + (
            "Конфликт между источниками одинакового приоритета "
            "требует ручной проверки."
            if unresolved
            else (
                "Выбрано значение более надёжного источника; "
                "альтернативное значение сохранено."
            )
        )
    )
    return FieldConflict(
        conflict_id=conflict_id,
        field_name=field_name,
        conflict_type=conflict_type,
        candidate_ids=candidate_ids,
        selected_candidate_id=selected.candidate_id,
        detected_at=detected_at,
        critical=critical,
        unresolved=unresolved,
        message=message,
    )


def _apply_selected_values(
    tender: UnifiedTender,
    selected: Mapping[str, FieldCandidate],
) -> UnifiedTender:
    customer = tender.customer
    name = _candidate_value(
        selected.get("customer.name"),
        fallback=customer.name,
    )
    inn = _candidate_value(
        selected.get("customer.inn"),
        fallback=customer.inn,
    )
    customer = TenderCustomer(
        name=str(name),
        inn=str(inn),
        kpp=customer.kpp,
        region=customer.region,
        address=customer.address,
    )
    metadata = dict(tender.raw_metadata)
    for field_name in (
        "application_security",
        "contract_security",
        "documentation_url",
        "platform",
    ):
        candidate = selected.get(field_name)
        if candidate is not None:
            metadata[field_name] = _value_payload(candidate.value)
    metadata["verification_status"] = "field_verified"
    metadata["verified_fields"] = sorted(selected)

    return replace(
        tender,
        procurement_number=str(
            _candidate_value(
                selected.get("procurement_number"),
                fallback=tender.procurement_number,
            )
        ),
        customer=customer,
        price=_price_from_candidate(
            selected.get("price"),
            tender.price,
        ),
        application_deadline=_datetime_from_candidate(
            selected.get("application_deadline"),
            tender.application_deadline,
        ),
        status=_status_from_candidate(
            selected.get("status"),
            tender.status,
        ),
        law=str(
            _candidate_value(
                selected.get("law"),
                fallback=tender.law,
            )
        ),
        source_url=str(
            _candidate_value(
                selected.get("source_url"),
                fallback=tender.source_url,
            )
        ),
        raw_metadata=metadata,
    )


def _candidate_value(
    candidate: FieldCandidate | None,
    *,
    fallback: object,
) -> object:
    return candidate.value if candidate is not None else fallback


def _price_from_candidate(
    candidate: FieldCandidate | None,
    fallback: TenderMoney | None,
) -> TenderMoney | None:
    if candidate is None:
        return fallback
    value = candidate.value
    if isinstance(value, TenderMoney):
        return value
    if isinstance(value, Mapping):
        amount = value.get("amount")
        if amount in (None, ""):
            return fallback
        return TenderMoney.from_value(
            str(amount),
            currency=str(value.get("currency", "RUB")),
            includes_vat=value.get("includes_vat"),
        )
    return fallback


def _datetime_from_candidate(
    candidate: FieldCandidate | None,
    fallback: datetime | None,
) -> datetime | None:
    if candidate is None:
        return fallback
    if isinstance(candidate.value, datetime):
        return candidate.value
    rendered = str(candidate.value or "").strip()
    if not rendered:
        return fallback
    try:
        return datetime.fromisoformat(rendered.replace("Z", "+00:00"))
    except ValueError:
        return fallback


def _status_from_candidate(
    candidate: FieldCandidate | None,
    fallback: TenderStatus,
) -> TenderStatus:
    if candidate is None:
        return fallback
    if isinstance(candidate.value, TenderStatus):
        return candidate.value
    try:
        return TenderStatus(str(candidate.value))
    except ValueError:
        return fallback


def _verification_status(
    selected: Sequence[FieldCandidate],
    *,
    missing_fields: tuple[str, ...],
    unresolved_conflict: bool,
) -> TenderVerificationStatus:
    if unresolved_conflict:
        return TenderVerificationStatus.CONFLICT
    if not selected:
        return TenderVerificationStatus.MISSING
    if missing_fields:
        return TenderVerificationStatus.INCOMPLETE
    lowest = min(item.trust_level for item in selected)
    if lowest >= SourceTrustLevel.OFFICIAL_DOCUMENTATION:
        return TenderVerificationStatus.VERIFIED_DOCUMENTATION
    if lowest >= SourceTrustLevel.EIS:
        return TenderVerificationStatus.VERIFIED_EIS
    if lowest >= SourceTrustLevel.OFFICIAL_PLATFORM:
        return TenderVerificationStatus.VERIFIED_PLATFORM
    if lowest >= SourceTrustLevel.OFFICIAL_API:
        return TenderVerificationStatus.VERIFIED_OFFICIAL_API
    if lowest >= SourceTrustLevel.CUSTOMER_SITE:
        return TenderVerificationStatus.CUSTOMER_SITE
    if all(
        item.trust_level == SourceTrustLevel.AGGREGATOR
        for item in selected
    ):
        return TenderVerificationStatus.AGGREGATOR_ONLY
    if lowest >= SourceTrustLevel.PUBLIC_CARD:
        return TenderVerificationStatus.PUBLIC_CARD
    return TenderVerificationStatus.UNVERIFIED


def _normalize_value(field_name: str, value: object) -> str:
    if isinstance(value, TenderMoney):
        return stable_json(
            {
                "amount": str(value.amount),
                "currency": value.currency.upper(),
                "includes_vat": value.includes_vat,
            }
        )
    if isinstance(value, Decimal):
        return str(value.normalize())
    if isinstance(value, datetime):
        normalized = value
        if normalized.tzinfo is not None:
            normalized = normalized.astimezone(timezone.utc)
        return normalized.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Mapping):
        return stable_json(value)
    if field_name in {
        "procurement_number",
        "customer.inn",
    }:
        return "".join(
            character
            for character in str(value).casefold()
            if character.isalnum()
        )
    if field_name.endswith("_url"):
        return str(value).strip()
    return normalize_text(str(value))


def _value_payload(value: object) -> object:
    if isinstance(value, TenderMoney):
        return {
            "amount": str(value.amount),
            "currency": value.currency,
            "includes_vat": value.includes_vat,
        }
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    return json.loads(stable_json(value))


def _candidate_id(
    field_name: str,
    value_hash: str,
    source_id: str,
    source_url: str,
    retrieved_at: str,
    *,
    historical: bool = False,
) -> str:
    identity = stable_json(
        {
            "field": field_name,
            "value_hash": value_hash,
            "source": source_id,
            "url": source_url,
            "retrieved_at": retrieved_at,
            "historical": historical,
        }
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _metadata_bool(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    rendered = str(value).strip().casefold()
    if rendered in {"1", "true", "yes", "да"}:
        return True
    if rendered in {"0", "false", "no", "нет"}:
        return False
    return default


def _metadata_float(value: object, *, default: float) -> float:
    if value in (None, ""):
        return default
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, TenderStatus):
        return value == TenderStatus.UNKNOWN
    return False


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


__all__ = [
    "FieldCandidate",
    "FieldConflict",
    "FieldConflictType",
    "FieldProvenance",
    "SourceTrustLevel",
    "TenderVerificationHistory",
    "TenderVerificationResult",
    "TenderVerificationState",
    "TenderVerificationService",
    "TenderVerificationStatus",
    "VerificationBatchResult",
]
