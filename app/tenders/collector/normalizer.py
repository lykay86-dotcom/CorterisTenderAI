"""Versioned canonical normalization and identity generation for tender records."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import re
import unicodedata
from typing import Iterable, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.tenders.collector.codec import stable_hash
from app.tenders.collector.models import (
    NormalizationDiagnostic,
    NormalizationDiagnosticCode,
    NormalizationDiagnosticSeverity,
    NormalizationFieldOutcome,
    NormalizedFieldProvenance,
    NormalizedTender,
    TenderAliasType,
    TenderIdentityAlias,
)
from app.tenders.models import (
    TenderCustomer,
    TenderDocument,
    TenderMoney,
    TenderProcedureType,
    TenderSource,
    TenderStatus,
    UnifiedTender,
)


TENDER_NORMALIZATION_CONTRACT_VERSION = 1
_MAX_STRING_CHARS = 16_384
_MAX_COLLECTION_ITEMS = 256
_MAX_DIAGNOSTICS = 128
_MAX_SOURCE_FIELD_CHARS = 200
_SUPPORTED_CURRENCIES = frozenset({"RUB", "USD", "EUR", "CNY"})
_SECRET_QUERY_MARKERS = (
    "access_token",
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "password",
    "secret",
    "signature",
    "token",
)
_OFFICIAL_NUMBER_KEYS = (
    "eis_number",
    "purchase_number",
    "procurement_number",
    "notice_number",
    "registry_number",
    "reg_number",
)
_LAW_ALIASES = {
    "44-фз": "44-ФЗ",
    "44 фз": "44-ФЗ",
    "44-fz": "44-ФЗ",
    "223-фз": "223-ФЗ",
    "223 фз": "223-ФЗ",
    "223-fz": "223-ФЗ",
    "commercial": "COMMERCIAL",
    "коммерческая закупка": "COMMERCIAL",
}


class TenderNormalizationError(ValueError):
    """A single source record cannot safely become a canonical tender."""

    def __init__(self, diagnostics: Sequence[NormalizationDiagnostic]) -> None:
        self.diagnostics = tuple(diagnostics)
        super().__init__("tender normalization rejected")


class TenderNormalizer:
    """Create one pure canonical tender result, comparison fields and hashes."""

    def normalize(self, tender: UnifiedTender) -> NormalizedTender:
        diagnostics: list[NormalizationDiagnostic] = []
        provider_id = _provider_id(tender)

        external_id = _canonical_text(
            tender.external_id,
            field="external_id",
            provider_id=provider_id,
            diagnostics=diagnostics,
            required=True,
            collapse_lines=True,
        )
        procurement_number = _canonical_text(
            tender.procurement_number,
            field="procurement_number",
            provider_id=provider_id,
            diagnostics=diagnostics,
            required=True,
            collapse_lines=True,
        )
        title = _canonical_text(
            tender.title,
            field="title",
            provider_id=provider_id,
            diagnostics=diagnostics,
            required=True,
        )
        customer = TenderCustomer(
            name=_canonical_text(
                tender.customer.name,
                field="customer.name",
                provider_id=provider_id,
                diagnostics=diagnostics,
                required=True,
            ),
            inn=_canonical_text(
                tender.customer.inn,
                field="customer.inn",
                provider_id=provider_id,
                diagnostics=diagnostics,
                collapse_lines=True,
            ),
            kpp=_canonical_text(
                tender.customer.kpp,
                field="customer.kpp",
                provider_id=provider_id,
                diagnostics=diagnostics,
                collapse_lines=True,
            ),
            region=_canonical_text(
                tender.customer.region,
                field="customer.region",
                provider_id=provider_id,
                diagnostics=diagnostics,
            ),
            address=_canonical_text(
                tender.customer.address,
                field="customer.address",
                provider_id=provider_id,
                diagnostics=diagnostics,
            ),
        )
        source_url = _canonical_url(
            tender.source_url,
            field="source_url",
            provider_id=provider_id,
            diagnostics=diagnostics,
        )
        published_at = _canonical_datetime(
            tender.published_at,
            field="published_at",
            provider_id=provider_id,
            diagnostics=diagnostics,
        )
        application_deadline = _canonical_datetime(
            tender.application_deadline,
            field="application_deadline",
            provider_id=provider_id,
            diagnostics=diagnostics,
        )
        if (
            published_at is not None
            and application_deadline is not None
            and application_deadline < published_at
        ):
            _diagnostic(
                diagnostics,
                code=NormalizationDiagnosticCode.CONFLICTING_VALUES,
                severity=NormalizationDiagnosticSeverity.ERROR,
                field="application_deadline",
                provider_id=provider_id,
                message="Application deadline conflicts with publication time.",
                recoverable=True,
            )
            application_deadline = None

        price = tender.price
        if price is not None and price.currency not in _SUPPORTED_CURRENCIES:
            _diagnostic(
                diagnostics,
                code=NormalizationDiagnosticCode.UNSUPPORTED_VALUE,
                severity=NormalizationDiagnosticSeverity.WARNING,
                field="price.currency",
                provider_id=provider_id,
                message="Currency is not in the supported canonical allowlist.",
                recoverable=True,
            )

        law = _canonical_law(tender.law, provider_id=provider_id, diagnostics=diagnostics)
        documents = _canonical_documents(
            tender.documents,
            provider_id=provider_id,
            diagnostics=diagnostics,
        )
        classification_codes = _canonical_collection(
            tender.classification_codes,
            field="classification_codes",
            provider_id=provider_id,
            diagnostics=diagnostics,
            identifier=True,
        )
        tags = _canonical_collection(
            tender.tags,
            field="tags",
            provider_id=provider_id,
            diagnostics=diagnostics,
        )
        raw_metadata = dict(tender.raw_metadata)
        raw_metadata["normalization_contract_version"] = TENDER_NORMALIZATION_CONTRACT_VERSION
        previous_invalid = raw_metadata.get("normalization_invalid_fields", ())
        previous_invalid_fields = (
            {str(item) for item in previous_invalid}
            if isinstance(previous_invalid, (tuple, list))
            else set()
        )
        raw_metadata["normalization_invalid_fields"] = tuple(
            sorted(
                previous_invalid_fields
                | {
                    item.field
                    for item in diagnostics
                    if item.code
                    in {
                        NormalizationDiagnosticCode.NAIVE_DATETIME_REJECTED,
                        NormalizationDiagnosticCode.AMBIGUOUS_DATETIME_REJECTED,
                        NormalizationDiagnosticCode.INVALID_FORMAT,
                        NormalizationDiagnosticCode.CONFLICTING_VALUES,
                    }
                }
            )
        )
        canonical_tender = UnifiedTender(
            source=tender.source,
            external_id=external_id,
            procurement_number=procurement_number,
            title=title,
            customer=customer,
            source_url=source_url,
            published_at=published_at,
            application_deadline=application_deadline,
            execution_deadline=tender.execution_deadline,
            price=price,
            status=tender.status,
            procedure_type=tender.procedure_type,
            law=law,
            region=_canonical_text(
                tender.region,
                field="region",
                provider_id=provider_id,
                diagnostics=diagnostics,
            ),
            description=_canonical_text(
                tender.description,
                field="description",
                provider_id=provider_id,
                diagnostics=diagnostics,
            ),
            classification_codes=classification_codes,
            tags=tags,
            documents=documents,
            raw_metadata=raw_metadata,
        )

        normalized_title = normalize_text(canonical_tender.title)
        normalized_customer = normalize_text(canonical_tender.customer.name)
        normalized_customer_inn = normalize_digits(canonical_tender.customer.inn)
        normalized_procurement_number = normalize_identifier(canonical_tender.procurement_number)
        external_key = normalize_identifier(canonical_tender.external_id)
        source = canonical_tender.source.value.casefold()
        official_number = _official_number(canonical_tender.raw_metadata)
        if not official_number and _looks_like_eis_number(normalized_procurement_number):
            official_number = normalized_procurement_number

        duplicate_payload = {
            "title": normalized_title,
            "customer_inn": normalized_customer_inn,
            "customer": normalized_customer if not normalized_customer_inn else "",
            "price": _price_value(canonical_tender),
            "deadline": _optional_iso(canonical_tender.application_deadline),
        }
        duplicate_hash = stable_hash(duplicate_payload)
        content_hash = stable_hash(
            _content_payload(
                canonical_tender,
                normalized_title,
                normalized_customer,
                normalized_customer_inn,
            )
        )
        aliases = _aliases(
            canonical_tender,
            source=source,
            external_id=external_key,
            procurement_number=normalized_procurement_number,
            official_number=official_number,
            duplicate_hash=duplicate_hash,
        )
        if official_number:
            canonical_key = f"procurement:{official_number}"
        elif normalized_procurement_number and _looks_cross_source_number(
            normalized_procurement_number
        ):
            canonical_key = f"procurement:{normalized_procurement_number}"
        else:
            canonical_key = min(
                aliases,
                key=lambda item: (-item.strength, item.key),
            ).key

        ordered_diagnostics = tuple(
            sorted(
                diagnostics[:_MAX_DIAGNOSTICS],
                key=lambda item: (
                    item.field,
                    item.code.value,
                    item.severity.value,
                    item.source_field,
                ),
            )
        )
        provenance = _build_provenance(
            tender,
            canonical_tender,
            provider_id=provider_id,
            diagnostics=ordered_diagnostics,
        )
        return NormalizedTender(
            tender=canonical_tender,
            canonical_key=canonical_key,
            aliases=aliases,
            normalized_title=normalized_title,
            normalized_customer=normalized_customer,
            normalized_customer_inn=normalized_customer_inn,
            normalized_procurement_number=normalized_procurement_number,
            content_hash=content_hash,
            duplicate_hash=duplicate_hash,
            completeness_score=_completeness_score(canonical_tender),
            diagnostics=ordered_diagnostics,
            provenance=provenance,
            contract_version=TENDER_NORMALIZATION_CONTRACT_VERSION,
            semantic_fingerprint=content_hash,
        )

    def normalize_many(
        self,
        tenders: Iterable[UnifiedTender],
    ) -> tuple[NormalizedTender, ...]:
        results: list[NormalizedTender] = []
        for tender in tenders:
            try:
                results.append(self.normalize(tender))
            except TenderNormalizationError:
                continue
        return tuple(results)

    def normalize_manual_mapping(
        self,
        values: Mapping[object, object],
        *,
        provenance: Sequence[object],
        provider_id: str,
    ) -> NormalizedTender:
        """Route an RM-135 offline mapping preview through this same boundary."""

        mapped = {_field_name(key): value for key, value in values.items()}
        price = None
        amount = mapped.get("price.amount")
        currency = mapped.get("price.currency")
        if amount not in (None, "") and currency not in (None, ""):
            price = TenderMoney.from_value(amount, currency=str(currency))  # type: ignore[arg-type]
        status = _enum_or_default(
            TenderStatus,
            mapped.get("status"),
            TenderStatus.UNKNOWN,
        )
        result = self.normalize(
            UnifiedTender(
                source=TenderSource.CUSTOM,
                external_id=str(mapped.get("external_id", "")),
                procurement_number=str(mapped.get("procurement_number", "")),
                title=str(mapped.get("title", "")),
                customer=TenderCustomer(
                    name=str(mapped.get("customer.name", "")),
                    inn=str(mapped.get("customer.inn", "")),
                ),
                source_url=str(mapped.get("source_url", "")),
                published_at=_as_datetime(mapped.get("published_at")),
                application_deadline=_as_datetime(mapped.get("application_deadline")),
                price=price,
                status=status,
                procedure_type=TenderProcedureType.UNKNOWN,
                law=str(mapped.get("law", "")),
                region=str(mapped.get("region", "")),
                description=str(mapped.get("description", "")),
                raw_metadata={"provider_id": provider_id, "manual_mapping": True},
            )
        )
        source_fields: dict[str, str] = {}
        for item in provenance:
            target = _field_name(getattr(item, "target_field", ""))
            path = getattr(item, "source_path", ())
            if target and isinstance(path, tuple):
                source_fields[target] = _safe_source_field(".".join(map(str, path)))
        return replace(
            result,
            provenance=tuple(
                replace(
                    item,
                    source_field=source_fields.get(item.field, item.source_field),
                )
                for item in result.provenance
            ),
        )


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


def _canonical_text(
    value: object,
    *,
    field: str,
    provider_id: str,
    diagnostics: list[NormalizationDiagnostic],
    required: bool = False,
    collapse_lines: bool = False,
) -> str:
    original = str(value or "")
    normalized = unicodedata.normalize("NFC", original)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = "".join(
        character
        for character in normalized
        if character in {"\n", "\t"} or (ord(character) >= 32 and ord(character) != 127)
    )
    if collapse_lines:
        normalized = " ".join(normalized.split())
    else:
        normalized = normalized.strip()
    if len(normalized) > _MAX_STRING_CHARS:
        normalized = normalized[:_MAX_STRING_CHARS]
        _diagnostic(
            diagnostics,
            code=NormalizationDiagnosticCode.RESOURCE_LIMIT_EXCEEDED,
            severity=NormalizationDiagnosticSeverity.WARNING,
            field=field,
            provider_id=provider_id,
            message="String exceeded the canonical field limit and was bounded.",
            recoverable=True,
        )
    if required and not normalized:
        _diagnostic(
            diagnostics,
            code=NormalizationDiagnosticCode.MISSING_REQUIRED,
            severity=NormalizationDiagnosticSeverity.ERROR,
            field=field,
            provider_id=provider_id,
            message="Required canonical field is missing.",
            recoverable=False,
        )
        raise TenderNormalizationError(diagnostics)
    return normalized


def _canonical_datetime(
    value: datetime | None,
    *,
    field: str,
    provider_id: str,
    diagnostics: list[NormalizationDiagnostic],
) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        _diagnostic(
            diagnostics,
            code=NormalizationDiagnosticCode.NAIVE_DATETIME_REJECTED,
            severity=NormalizationDiagnosticSeverity.WARNING,
            field=field,
            provider_id=provider_id,
            message="Naive datetime was rejected without machine-timezone localization.",
            recoverable=True,
        )
        return None
    return value.astimezone(timezone.utc)


def _canonical_law(
    value: str,
    *,
    provider_id: str,
    diagnostics: list[NormalizationDiagnostic],
) -> str:
    normalized = _canonical_text(
        value,
        field="law",
        provider_id=provider_id,
        diagnostics=diagnostics,
        collapse_lines=True,
    )
    if not normalized:
        return ""
    mapped = _LAW_ALIASES.get(normalized.casefold())
    if mapped is not None:
        return mapped
    _diagnostic(
        diagnostics,
        code=NormalizationDiagnosticCode.UNMAPPED_VALUE,
        severity=NormalizationDiagnosticSeverity.WARNING,
        field="law",
        provider_id=provider_id,
        message="Procurement law is not in the explicit canonical allowlist.",
        recoverable=True,
    )
    return ""


def _canonical_url(
    value: str,
    *,
    field: str,
    provider_id: str,
    diagnostics: list[NormalizationDiagnostic],
) -> str:
    parsed = urlsplit(value.strip())
    kept_query: list[tuple[str, str]] = []
    removed = bool(parsed.fragment)
    for key, item in parse_qsl(parsed.query, keep_blank_values=True):
        folded = key.casefold()
        if any(marker in folded for marker in _SECRET_QUERY_MARKERS):
            removed = True
            continue
        kept_query.append((key, item))
    normalized = urlunsplit(
        (
            parsed.scheme.casefold(),
            parsed.netloc.casefold(),
            parsed.path,
            urlencode(sorted(kept_query)),
            "",
        )
    )
    if removed:
        _diagnostic(
            diagnostics,
            code=NormalizationDiagnosticCode.UNSAFE_URL_REJECTED,
            severity=NormalizationDiagnosticSeverity.WARNING,
            field=field,
            provider_id=provider_id,
            message="Unsafe or non-semantic URL components were removed.",
            recoverable=True,
        )
    return normalized


def _canonical_collection(
    values: Iterable[str],
    *,
    field: str,
    provider_id: str,
    diagnostics: list[NormalizationDiagnostic],
    identifier: bool = False,
) -> tuple[str, ...]:
    result: dict[str, str] = {}
    for raw in values:
        normalized = _canonical_text(
            raw,
            field=field,
            provider_id=provider_id,
            diagnostics=diagnostics,
            collapse_lines=True,
        )
        if identifier:
            normalized = unicodedata.normalize("NFC", normalized)
        if normalized:
            result.setdefault(normalized.casefold(), normalized)
    ordered = tuple(sorted(result.values(), key=lambda item: (item.casefold(), item)))
    if len(ordered) > _MAX_COLLECTION_ITEMS:
        _diagnostic(
            diagnostics,
            code=NormalizationDiagnosticCode.RESOURCE_LIMIT_EXCEEDED,
            severity=NormalizationDiagnosticSeverity.WARNING,
            field=field,
            provider_id=provider_id,
            message="Collection exceeded the canonical item limit and was bounded.",
            recoverable=True,
        )
        return ordered[:_MAX_COLLECTION_ITEMS]
    return ordered


def _canonical_documents(
    documents: Iterable[TenderDocument],
    *,
    provider_id: str,
    diagnostics: list[NormalizationDiagnostic],
) -> tuple[TenderDocument, ...]:
    by_key: dict[str, TenderDocument] = {}
    for item in documents:
        document = TenderDocument(
            id=_canonical_text(
                item.id,
                field="documents.id",
                provider_id=provider_id,
                diagnostics=diagnostics,
                required=True,
                collapse_lines=True,
            ),
            name=_canonical_text(
                item.name,
                field="documents.name",
                provider_id=provider_id,
                diagnostics=diagnostics,
                required=True,
            ),
            url=_canonical_url(
                item.url,
                field="documents.url",
                provider_id=provider_id,
                diagnostics=diagnostics,
            ),
            mime_type=_canonical_text(
                item.mime_type,
                field="documents.mime_type",
                provider_id=provider_id,
                diagnostics=diagnostics,
                collapse_lines=True,
            ),
            size_bytes=item.size_bytes,
            published_at=_canonical_datetime(
                item.published_at,
                field="documents.published_at",
                provider_id=provider_id,
                diagnostics=diagnostics,
            ),
            checksum_sha256=item.checksum_sha256.strip().casefold(),
        )
        key = document.checksum_sha256 or document.url.casefold() or document.id.casefold()
        by_key.setdefault(key, document)
    return tuple(
        sorted(
            by_key.values(),
            key=lambda item: (
                item.checksum_sha256,
                item.url.casefold(),
                item.id.casefold(),
            ),
        )[:_MAX_COLLECTION_ITEMS]
    )


def _diagnostic(
    diagnostics: list[NormalizationDiagnostic],
    *,
    code: NormalizationDiagnosticCode,
    severity: NormalizationDiagnosticSeverity,
    field: str,
    provider_id: str,
    message: str,
    recoverable: bool,
) -> None:
    if len(diagnostics) >= _MAX_DIAGNOSTICS:
        return
    diagnostics.append(
        NormalizationDiagnostic(
            code=code,
            severity=severity,
            field=field,
            source_field=_safe_source_field(field),
            provider_id=provider_id,
            message=message,
            recoverable=recoverable,
        )
    )


def _provider_id(tender: UnifiedTender) -> str:
    raw = tender.raw_metadata.get("provider_id") or tender.raw_metadata.get("provider")
    normalized = str(raw or tender.source.value).strip().casefold()
    safe = "".join(
        character for character in normalized if character.isalnum() or character in {"-", "_", "."}
    )[:128]
    return safe or tender.source.value


def _safe_source_field(value: str) -> str:
    safe = "".join(
        character
        for character in value
        if character.isalnum() or character in {"-", "_", ".", "[", "]"}
    )
    return safe[:_MAX_SOURCE_FIELD_CHARS] or "unknown"


def _build_provenance(
    source: UnifiedTender,
    canonical: UnifiedTender,
    *,
    provider_id: str,
    diagnostics: Sequence[NormalizationDiagnostic],
) -> tuple[NormalizedFieldProvenance, ...]:
    invalid_fields = {
        item.field
        for item in diagnostics
        if item.code
        in {
            NormalizationDiagnosticCode.INVALID_FORMAT,
            NormalizationDiagnosticCode.NAIVE_DATETIME_REJECTED,
            NormalizationDiagnosticCode.AMBIGUOUS_DATETIME_REJECTED,
            NormalizationDiagnosticCode.CONFLICTING_VALUES,
        }
    }
    fields = {
        "external_id": (source.external_id, canonical.external_id),
        "procurement_number": (
            source.procurement_number,
            canonical.procurement_number,
        ),
        "title": (source.title, canonical.title),
        "customer.name": (source.customer.name, canonical.customer.name),
        "customer.inn": (source.customer.inn, canonical.customer.inn),
        "source_url": (source.source_url, canonical.source_url),
        "published_at": (source.published_at, canonical.published_at),
        "application_deadline": (
            source.application_deadline,
            canonical.application_deadline,
        ),
        "price.amount": (
            source.price.amount if source.price else None,
            canonical.price.amount if canonical.price else None,
        ),
        "price.currency": (
            source.price.currency if source.price else None,
            canonical.price.currency if canonical.price else None,
        ),
        "status": (source.status, canonical.status),
        "law": (source.law, canonical.law),
        "region": (source.region, canonical.region),
        "classification_codes": (
            source.classification_codes,
            canonical.classification_codes,
        ),
    }
    source_record_id = normalize_identifier(canonical.external_id)[:128]
    result: list[NormalizedFieldProvenance] = []
    for field, (before, after) in fields.items():
        if field in invalid_fields:
            outcome = NormalizationFieldOutcome.INVALID
        elif after in (None, "", ()):
            outcome = NormalizationFieldOutcome.MISSING
        elif before != after:
            outcome = NormalizationFieldOutcome.NORMALIZED
        else:
            outcome = NormalizationFieldOutcome.DIRECT
        result.append(
            NormalizedFieldProvenance(
                field=field,
                source_field=_safe_source_field(field),
                provider_id=provider_id,
                transform_id=(f"tender-normalization-v{TENDER_NORMALIZATION_CONTRACT_VERSION}"),
                outcome=outcome,
                source_record_id=source_record_id,
                verified=False,
            )
        )
    return tuple(sorted(result, key=lambda item: (item.field, item.source_field)))


def _aliases(
    tender: UnifiedTender,
    *,
    source: str,
    external_id: str,
    procurement_number: str,
    official_number: str,
    duplicate_hash: str,
) -> tuple[TenderIdentityAlias, ...]:
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
                    alias_type=TenderAliasType.PROCUREMENT_NUMBER,
                    strength=95,
                )
            )
        aliases.append(
            TenderIdentityAlias(
                key=f"platform:{source}:{procurement_number}",
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
    if normalize_text(tender.title) and (
        normalize_digits(tender.customer.inn) or normalize_text(tender.customer.name)
    ):
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
    return _unique_aliases(aliases)


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
        "customer": (normalize_digits(tender.customer.inn) or normalize_text(tender.customer.name)),
        "price": _price_value(tender),
        "deadline": _optional_iso(tender.application_deadline),
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
    documents = [
        {
            "id": normalize_identifier(item.id),
            "name": normalize_text(item.name),
            "url": item.url,
            "checksum": item.checksum_sha256.casefold(),
            "size": item.size_bytes,
            "published_at": _optional_iso(item.published_at),
        }
        for item in tender.documents
    ]
    return {
        "normalization_contract_version": TENDER_NORMALIZATION_CONTRACT_VERSION,
        "title": title,
        "customer": customer,
        "customer_inn": customer_inn,
        "price": _price_value(tender),
        "published_at": _optional_iso(tender.published_at),
        "application_deadline": _optional_iso(tender.application_deadline),
        "execution_deadline": _optional_iso(tender.execution_deadline),
        "status": tender.status.value,
        "procedure_type": tender.procedure_type.value,
        "law": normalize_text(tender.law),
        "region": normalize_text(tender.region),
        "description": normalize_text(tender.description),
        "classification_codes": list(tender.classification_codes),
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
    return tuple(sorted(by_key.values(), key=lambda item: (-item.strength, item.key)))


def _field_name(value: object) -> str:
    return str(getattr(value, "value", value)).strip()


def _as_datetime(value: object) -> datetime | None:
    return value if isinstance(value, datetime) else None


def _optional_iso(value: object) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else ""


def _enum_or_default(
    enum_type: type[TenderStatus],
    value: object,
    default: TenderStatus,
) -> TenderStatus:
    try:
        return enum_type(str(value))
    except ValueError:
        return default


__all__ = [
    "TENDER_NORMALIZATION_CONTRACT_VERSION",
    "TenderNormalizationError",
    "TenderNormalizer",
    "normalize_digits",
    "normalize_identifier",
    "normalize_text",
]
