"""Unified tender domain models used by all procurement providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
import re
from typing import Any, Mapping
from urllib.parse import urlparse


class TenderSource(StrEnum):
    EIS = "eis"
    MOS_SUPPLIER = "mos_supplier"
    SBER_A = "sber_a"
    RTS_TENDER = "rts_tender"
    ROSELTORG = "roseltorg"
    B2B_CENTER = "b2b_center"
    TEK_TORG = "tek_torg"
    GAZPROMBANK = "gazprombank"
    FABRIKANT = "fabrikant"
    OTC = "otc"
    COMMERCIAL = "commercial"
    CUSTOM = "custom"


class TenderProcedureType(StrEnum):
    UNKNOWN = "unknown"
    ELECTRONIC_AUCTION = "electronic_auction"
    OPEN_COMPETITION = "open_competition"
    REQUEST_FOR_QUOTATIONS = "request_for_quotations"
    REQUEST_FOR_PROPOSALS = "request_for_proposals"
    SINGLE_SUPPLIER = "single_supplier"
    COMMERCIAL_REQUEST = "commercial_request"


class TenderStatus(StrEnum):
    UNKNOWN = "unknown"
    PUBLISHED = "published"
    ACCEPTING_APPLICATIONS = "accepting_applications"
    APPLICATIONS_CLOSED = "applications_closed"
    REVIEW = "review"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class TenderDocument:
    id: str
    name: str
    url: str
    mime_type: str = ""
    size_bytes: int | None = None
    published_at: datetime | None = None
    checksum_sha256: str = ""

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("TenderDocument.id must not be empty")
        if not self.name.strip():
            raise ValueError("TenderDocument.name must not be empty")
        _validate_http_url(self.url, field_name="TenderDocument.url")
        if self.size_bytes is not None and self.size_bytes < 0:
            raise ValueError("TenderDocument.size_bytes must be non-negative")


@dataclass(frozen=True, slots=True)
class TenderCustomer:
    name: str
    inn: str = ""
    kpp: str = ""
    region: str = ""
    address: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("TenderCustomer.name must not be empty")


@dataclass(frozen=True, slots=True)
class TenderMoney:
    amount: Decimal
    currency: str = "RUB"
    includes_vat: bool | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "amount",
            normalize_money_amount(
                self.amount,
                field_name="TenderMoney.amount",
            ),
        )
        object.__setattr__(
            self,
            "currency",
            normalize_currency_code(self.currency),
        )

    @classmethod
    def from_value(
        cls,
        value: Decimal | int | float | str,
        *,
        currency: str = "RUB",
        includes_vat: bool | None = None,
    ) -> "TenderMoney":
        return cls(
            amount=normalize_money_amount(
                value,
                field_name="tender amount",
            ),
            currency=currency,
            includes_vat=includes_vat,
        )


def normalize_money_amount(
    value: Decimal | int | float | str,
    *,
    field_name: str = "amount",
) -> Decimal:
    """Return an exact, finite and non-negative monetary amount."""

    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid {field_name}: {value!r}") from exc
    if not amount.is_finite():
        raise ValueError(f"{field_name} must be finite")
    if amount < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return amount


_CURRENCY_ALIASES = {
    "₽": "RUB",
    "РУБ": "RUB",
    "РУБ.": "RUB",
    "RUR": "RUB",
    "643": "RUB",
    "$": "USD",
    "ДОЛЛАР": "USD",
    "ДОЛЛАР США": "USD",
    "840": "USD",
    "€": "EUR",
    "ЕВРО": "EUR",
    "978": "EUR",
    "ЮАНЬ": "CNY",
    "156": "CNY",
}


def normalize_currency_code(value: str) -> str:
    """Return a canonical ISO 4217 alpha code for a currency label."""

    normalized = " ".join(str(value).strip().upper().split())
    normalized = _CURRENCY_ALIASES.get(normalized, normalized)
    if not re.fullmatch(r"[A-Z]{3}", normalized):
        raise ValueError(f"Invalid currency code: {value!r}")
    return normalized


@dataclass(frozen=True, slots=True)
class UnifiedTender:
    """Provider-neutral tender representation."""

    source: TenderSource
    external_id: str
    procurement_number: str
    title: str
    customer: TenderCustomer
    source_url: str
    published_at: datetime | None = None
    application_deadline: datetime | None = None
    execution_deadline: date | None = None
    price: TenderMoney | None = None
    status: TenderStatus = TenderStatus.UNKNOWN
    procedure_type: TenderProcedureType = TenderProcedureType.UNKNOWN
    law: str = ""
    region: str = ""
    description: str = ""
    classification_codes: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    documents: tuple[TenderDocument, ...] = ()
    raw_metadata: Mapping[str, Any] = field(
        default_factory=dict,
        compare=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        if not self.external_id.strip():
            raise ValueError("UnifiedTender.external_id must not be empty")
        if not self.procurement_number.strip():
            raise ValueError("UnifiedTender.procurement_number must not be empty")
        if not self.title.strip():
            raise ValueError("UnifiedTender.title must not be empty")
        _validate_http_url(
            self.source_url,
            field_name="UnifiedTender.source_url",
        )
        if (
            self.application_deadline is not None
            and self.published_at is not None
            and _datetimes_are_comparable(
                self.application_deadline,
                self.published_at,
            )
            and self.application_deadline < self.published_at
        ):
            raise ValueError("application_deadline cannot precede published_at")

    @property
    def identity_key(self) -> str:
        return f"{self.source.value}:{self.external_id.strip().casefold()}"

    @property
    def cross_source_key(self) -> str:
        return self.procurement_number.strip().casefold()

    @property
    def is_open(self) -> bool:
        return self.status in {
            TenderStatus.PUBLISHED,
            TenderStatus.ACCEPTING_APPLICATIONS,
        }

    def with_documents(
        self,
        documents: tuple[TenderDocument, ...],
    ) -> "UnifiedTender":
        return UnifiedTender(
            source=self.source,
            external_id=self.external_id,
            procurement_number=self.procurement_number,
            title=self.title,
            customer=self.customer,
            source_url=self.source_url,
            published_at=self.published_at,
            application_deadline=self.application_deadline,
            execution_deadline=self.execution_deadline,
            price=self.price,
            status=self.status,
            procedure_type=self.procedure_type,
            law=self.law,
            region=self.region,
            description=self.description,
            classification_codes=self.classification_codes,
            tags=self.tags,
            documents=documents,
            raw_metadata=self.raw_metadata,
        )


def is_timezone_aware(value: datetime) -> bool:
    """Return whether a datetime carries an effective UTC offset."""

    return value.tzinfo is not None and value.utcoffset() is not None


def _datetimes_are_comparable(first: datetime, second: datetime) -> bool:
    """Avoid implicit localization and mixed naive/aware comparison errors."""

    return is_timezone_aware(first) == is_timezone_aware(second)


def _validate_http_url(value: str, *, field_name: str) -> None:
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{field_name} must be an absolute HTTP(S) URL")


__all__ = [
    "TenderCustomer",
    "TenderDocument",
    "TenderMoney",
    "normalize_currency_code",
    "normalize_money_amount",
    "TenderProcedureType",
    "TenderSource",
    "TenderStatus",
    "UnifiedTender",
    "is_timezone_aware",
]
