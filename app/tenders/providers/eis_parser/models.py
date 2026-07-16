"""Value objects for deterministic EIS parsing and diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Mapping

from app.tenders.provider_base import ProviderHealthStatus


class EisLawType(StrEnum):
    FZ_44 = "44-FZ"
    FZ_223 = "223-FZ"
    UNKNOWN = "unknown"

    @property
    def display_name(self) -> str:
        return {
            EisLawType.FZ_44: "44-ФЗ",
            EisLawType.FZ_223: "223-ФЗ",
            EisLawType.UNKNOWN: "",
        }[self]


class EisPageType(StrEnum):
    SEARCH = "search"
    SEARCH_EMPTY = "search_empty"
    NOTICE_44 = "notice_44"
    NOTICE_223 = "notice_223"
    DOCUMENTS = "documents"
    CAPTCHA = "captcha"
    ACCESS_DENIED = "access_denied"
    MAINTENANCE = "maintenance"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class EisParseDiagnostics:
    page_type: EisPageType
    parser_version: str
    cards_detected: int = 0
    cards_parsed: int = 0
    cards_failed: int = 0
    parse_success_rate: float = 1.0
    missing_title_count: int = 0
    missing_customer_count: int = 0
    missing_price_count: int = 0
    unknown_law_count: int = 0
    warnings: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        return {
            "page_type": self.page_type.value,
            "parser_version": self.parser_version,
            "cards_detected": self.cards_detected,
            "cards_parsed": self.cards_parsed,
            "cards_failed": self.cards_failed,
            "parse_success_rate": self.parse_success_rate,
            "missing_title_count": self.missing_title_count,
            "missing_customer_count": self.missing_customer_count,
            "missing_price_count": self.missing_price_count,
            "unknown_law_count": self.unknown_law_count,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class EisTenderDetails:
    procurement_number: str
    title: str
    source_url: str
    law: EisLawType
    customer_name: str
    customer_inn: str | None = None
    customer_kpp: str | None = None
    organization_code: str | None = None
    customer_address: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    region: str | None = None
    delivery_place: str | None = None
    funding_source: str | None = None
    bid_security: Decimal | None = None
    contract_security: Decimal | None = None
    warranty_security: Decimal | None = None
    advance_percent: Decimal | None = None
    price: Decimal | None = None
    currency: str = "RUB"
    published_at: datetime | None = None
    updated_at: datetime | None = None
    application_deadline: datetime | None = None
    status: str | None = None
    procedure_type: str | None = None
    okpd2_codes: tuple[str, ...] = ()
    ktru_codes: tuple[str, ...] = ()
    requirements: tuple[str, ...] = ()
    restrictions: tuple[str, ...] = ()
    advantages: tuple[str, ...] = ()
    lots: tuple[Mapping[str, object], ...] = ()
    parser_version: str = ""

    def to_metadata(self) -> dict[str, object]:
        def decimal(value: Decimal | None) -> str | None:
            return str(value) if value is not None else None

        def moment(value: datetime | None) -> str | None:
            return value.isoformat() if value is not None else None

        return {
            "procurement_number": self.procurement_number,
            "law": self.law.value,
            "customer_inn": self.customer_inn,
            "customer_kpp": self.customer_kpp,
            "organization_code": self.organization_code,
            "contact_name": self.contact_name,
            "contact_phone": self.contact_phone,
            "contact_email": self.contact_email,
            "delivery_place": self.delivery_place,
            "funding_source": self.funding_source,
            "bid_security": decimal(self.bid_security),
            "contract_security": decimal(self.contract_security),
            "warranty_security": decimal(self.warranty_security),
            "advance_percent": decimal(self.advance_percent),
            "published_at": moment(self.published_at),
            "updated_at": moment(self.updated_at),
            "application_deadline": moment(self.application_deadline),
            "okpd2_codes": list(self.okpd2_codes),
            "ktru_codes": list(self.ktru_codes),
            "requirements": list(self.requirements),
            "restrictions": list(self.restrictions),
            "advantages": list(self.advantages),
            "lots": [dict(item) for item in self.lots],
            "parser_version": self.parser_version,
        }


@dataclass(frozen=True, slots=True)
class EisHealthReport:
    network_status: ProviderHealthStatus
    parser_status: ProviderHealthStatus
    network_message: str
    parser_message: str
    diagnostics: EisParseDiagnostics | None = None

    @property
    def status(self) -> ProviderHealthStatus:
        order = {
            ProviderHealthStatus.AVAILABLE: 0,
            ProviderHealthStatus.UNKNOWN: 1,
            ProviderHealthStatus.DEGRADED: 2,
            ProviderHealthStatus.NOT_CONFIGURED: 3,
            ProviderHealthStatus.UNAVAILABLE: 4,
        }
        return max(
            (self.network_status, self.parser_status),
            key=lambda value: order[value],
        )


__all__ = [
    "EisHealthReport",
    "EisLawType",
    "EisPageType",
    "EisParseDiagnostics",
    "EisTenderDetails",
]
