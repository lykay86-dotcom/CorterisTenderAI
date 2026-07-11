"""Common provider contract for electronic tender platforms."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any, Mapping, Sequence

from app.tenders.models import (
    TenderDocument,
    TenderSource,
    UnifiedTender,
)


class ProviderHealthStatus(StrEnum):
    UNKNOWN = "unknown"
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    NOT_CONFIGURED = "not_configured"


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    search: bool = False
    tender_details: bool = False
    documents: bool = False
    authentication: bool = False
    public_api: bool = False
    incremental_updates: bool = False
    rate_limit_per_minute: int | None = None

    def __post_init__(self) -> None:
        if (
            self.rate_limit_per_minute is not None
            and self.rate_limit_per_minute <= 0
        ):
            raise ValueError(
                "rate_limit_per_minute must be positive"
            )


@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    id: str
    display_name: str
    source: TenderSource
    homepage_url: str
    capabilities: ProviderCapabilities
    enabled_by_default: bool = True
    priority: int = 100
    implementation_status: str = "placeholder"

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("ProviderDescriptor.id must not be empty")
        if not self.display_name.strip():
            raise ValueError(
                "ProviderDescriptor.display_name must not be empty"
            )
        if self.priority < 0:
            raise ValueError(
                "ProviderDescriptor.priority must be non-negative"
            )


@dataclass(frozen=True, slots=True)
class TenderSearchQuery:
    keywords: tuple[str, ...] = ()
    excluded_keywords: tuple[str, ...] = ()
    regions: tuple[str, ...] = ()
    laws: tuple[str, ...] = ()
    date_from: date | None = None
    date_to: date | None = None
    min_price: float | None = None
    max_price: float | None = None
    page: int = 1
    page_size: int = 50
    extra: Mapping[str, Any] = field(
        default_factory=dict,
        compare=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError("page must be at least 1")
        if not 1 <= self.page_size <= 500:
            raise ValueError("page_size must be between 1 and 500")
        if (
            self.min_price is not None
            and self.min_price < 0
        ):
            raise ValueError("min_price must be non-negative")
        if (
            self.max_price is not None
            and self.max_price < 0
        ):
            raise ValueError("max_price must be non-negative")
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError(
                "min_price cannot be greater than max_price"
            )
        if (
            self.date_from is not None
            and self.date_to is not None
            and self.date_from > self.date_to
        ):
            raise ValueError(
                "date_from cannot be greater than date_to"
            )


@dataclass(frozen=True, slots=True)
class TenderSearchResult:
    provider_id: str
    items: tuple[UnifiedTender, ...]
    total: int | None = None
    page: int = 1
    page_size: int = 50
    next_page_token: str = ""
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError(
                "TenderSearchResult.provider_id must not be empty"
            )
        if self.total is not None and self.total < 0:
            raise ValueError("total must be non-negative")


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    provider_id: str
    status: ProviderHealthStatus
    checked_at: str
    message: str = ""
    latency_ms: int | None = None

    def __post_init__(self) -> None:
        if self.latency_ms is not None and self.latency_ms < 0:
            raise ValueError("latency_ms must be non-negative")


class TenderProviderError(RuntimeError):
    """Base exception for provider-specific failures."""


class ProviderNotConfiguredError(TenderProviderError):
    """Raised when credentials or endpoint configuration are absent."""


class ProviderCapabilityError(TenderProviderError):
    """Raised when a provider does not support a requested operation."""


class TenderProvider(ABC):
    """Stable adapter contract implemented by every tender source."""

    descriptor: ProviderDescriptor

    @abstractmethod
    def search(
        self,
        query: TenderSearchQuery,
    ) -> TenderSearchResult:
        raise NotImplementedError

    @abstractmethod
    def get_tender(
        self,
        external_id: str,
    ) -> UnifiedTender:
        raise NotImplementedError

    @abstractmethod
    def list_documents(
        self,
        external_id: str,
    ) -> Sequence[TenderDocument]:
        raise NotImplementedError

    @abstractmethod
    def check_health(self) -> ProviderHealth:
        raise NotImplementedError

    def validate_configuration(self) -> tuple[str, ...]:
        return ()


__all__ = [
    "ProviderCapabilities",
    "ProviderCapabilityError",
    "ProviderDescriptor",
    "ProviderHealth",
    "ProviderHealthStatus",
    "ProviderNotConfiguredError",
    "TenderProvider",
    "TenderProviderError",
    "TenderSearchQuery",
    "TenderSearchResult",
]
