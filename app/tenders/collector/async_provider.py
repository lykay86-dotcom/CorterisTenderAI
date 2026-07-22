"""Asynchronous provider contract and compatibility adapter."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import AsyncIterator, Mapping
from typing import Sequence

from app.tenders.collector.artifacts import RawArtifactReference
from app.tenders.collector.cancellation import CollectorCancellationToken
from app.tenders.collector.checkpoint import CollectorCheckpoint
from app.tenders.collector.codec import stable_hash
from app.tenders.models import TenderDocument, UnifiedTender
from app.tenders.provider_base import (
    ProviderDescriptor,
    ProviderHealth,
    TenderProvider,
    TenderSearchQuery,
    TenderSearchResult,
)


_SENSITIVE_FILTER_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "password",
    "secret",
    "token",
)
_NAVIGATION_FILTERS = {
    "cursor",
    "next_cursor",
    "next_page",
    "next_page_token",
    "page",
    "page_number",
    "retry",
    "retry_count",
}


@dataclass(frozen=True, slots=True)
class ProviderCollectionPage:
    """One bounded, typed provider page before Collector acceptance."""

    provider_id: str
    contract_version: str
    parser_version: str
    query_fingerprint: str
    page_identity: str
    page_number: int
    items: tuple[UnifiedTender, ...]
    next_cursor: str
    terminal: bool
    artifacts: tuple[RawArtifactReference, ...]
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider page identity is required")
        if not self.contract_version.strip() or not self.parser_version.strip():
            raise ValueError("provider page contract and parser versions are required")
        if len(self.query_fingerprint) != 64:
            raise ValueError("provider page query fingerprint must be SHA-256")
        if not self.page_identity.strip():
            raise ValueError("provider page identity is required")
        if self.page_number < 1:
            raise ValueError("provider page number must be positive")
        if len(self.items) > 500:
            raise ValueError("provider page exceeds the 500 item limit")
        if self.terminal and self.next_cursor:
            raise ValueError("terminal provider page cannot expose a next cursor")

    @property
    def is_last(self) -> bool:
        """Compatibility projection used by earlier expected-red fixtures."""

        return self.terminal

    @property
    def artifact_refs(self) -> tuple[RawArtifactReference, ...]:
        return self.artifacts


class ProviderPageContractError(RuntimeError):
    """Safe page-protocol failure with a fixed public code."""

    code = "provider_page_contract_error"


class ProviderCursorCycleError(ProviderPageContractError):
    code = "provider_cursor_cycle"


class ProviderPageBudgetError(ProviderPageContractError):
    code = "provider_page_budget_exceeded"


def build_query_fingerprint(
    provider: AsyncTenderProvider,
    query: TenderSearchQuery,
) -> str:
    """Hash semantic search inputs while excluding secrets and navigation state."""

    payload = {
        "provider_id": provider.descriptor.id.strip().casefold(),
        "contract_version": str(provider.contract_version),
        "parser_version": str(provider.parser_version),
        "keywords": _canonical_strings(query.keywords),
        "excluded_keywords": _canonical_strings(query.excluded_keywords),
        "regions": _canonical_strings(query.regions),
        "laws": _canonical_strings(query.laws),
        "date_from": _semantic_value(query.date_from),
        "date_to": _semantic_value(query.date_to),
        "min_price": _semantic_value(query.min_price),
        "max_price": _semantic_value(query.max_price),
        "price_currency": query.price_currency,
        "page_size": query.page_size,
        "provider_filters": _safe_filter_value(query.extra),
    }
    return stable_hash(payload)


def _canonical_strings(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted({value.strip().casefold() for value in values if value.strip()}))


def _semantic_value(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, (date, Decimal)):
        return value.isoformat() if isinstance(value, date) else str(value)
    return value


def _safe_filter_value(value: object) -> object:
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key).strip()
            normalized = key.casefold()
            if not key or normalized in _NAVIGATION_FILTERS:
                continue
            if any(marker in normalized for marker in _SENSITIVE_FILTER_MARKERS):
                continue
            result[key] = _safe_filter_value(raw_value)
        return result
    if isinstance(value, (tuple, list, set, frozenset)):
        return tuple(_safe_filter_value(item) for item in value)
    return _semantic_value(value)


class AsyncTenderProvider(ABC):
    """Provider contract for new non-blocking collector connectors."""

    descriptor: ProviderDescriptor
    connection_mode: str = "unknown"
    contract_version: str = "1"
    parser_version: str = "1"

    async def iter_search_pages(
        self,
        query: TenderSearchQuery,
        *,
        resume: CollectorCheckpoint | None = None,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> AsyncIterator[ProviderCollectionPage]:
        """Adapt a legacy one-shot search into one terminal typed page."""

        del resume
        if cancellation_token is not None:
            cancellation_token.throw_if_cancelled()
        result = await self.search(query, cancellation_token=cancellation_token)
        if cancellation_token is not None:
            cancellation_token.throw_if_cancelled()
        fingerprint = build_query_fingerprint(self, query)
        next_cursor = result.next_page_token.strip()
        page_identity = stable_hash(
            {
                "provider_id": self.descriptor.id.strip().casefold(),
                "contract_version": self.contract_version,
                "parser_version": self.parser_version,
                "query_fingerprint": fingerprint,
                "page_number": result.page,
                "cursor": "initial",
            }
        )
        yield ProviderCollectionPage(
            provider_id=result.provider_id,
            contract_version=self.contract_version,
            parser_version=self.parser_version,
            query_fingerprint=fingerprint,
            page_identity=page_identity,
            page_number=result.page,
            items=tuple(result.items),
            next_cursor=next_cursor,
            terminal=not next_cursor,
            artifacts=(),
            warnings=tuple(result.warnings),
        )

    @abstractmethod
    async def search(
        self,
        query: TenderSearchQuery,
        *,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> TenderSearchResult:
        raise NotImplementedError

    @abstractmethod
    async def get_tender(
        self,
        external_id: str,
        *,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> UnifiedTender:
        raise NotImplementedError

    @abstractmethod
    async def list_documents(
        self,
        external_id: str,
        *,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> Sequence[TenderDocument]:
        raise NotImplementedError

    @abstractmethod
    async def check_health(
        self,
        *,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> ProviderHealth:
        raise NotImplementedError

    def validate_configuration(self) -> tuple[str, ...]:
        return ()


class LegacySyncProviderAdapter(AsyncTenderProvider):
    """Run an existing sync provider in a worker thread.

    This adapter preserves compatibility while real collector providers are
    migrated to HTTPX. Cancelling the asyncio task cannot forcibly terminate
    Python code already executing inside the legacy worker thread, therefore
    it is a transition tool rather than the final network implementation.
    """

    connection_mode = "legacy_thread"
    parser_version = "legacy"

    def __init__(self, provider: TenderProvider) -> None:
        self.provider = provider
        self.descriptor = provider.descriptor

    async def search(
        self,
        query: TenderSearchQuery,
        *,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> TenderSearchResult:
        self._check(cancellation_token)
        result = await asyncio.to_thread(self.provider.search, query)
        self._check(cancellation_token)
        return result

    async def get_tender(
        self,
        external_id: str,
        *,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> UnifiedTender:
        self._check(cancellation_token)
        result = await asyncio.to_thread(
            self.provider.get_tender,
            external_id,
        )
        self._check(cancellation_token)
        return result

    async def list_documents(
        self,
        external_id: str,
        *,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> Sequence[TenderDocument]:
        self._check(cancellation_token)
        result = await asyncio.to_thread(
            self.provider.list_documents,
            external_id,
        )
        self._check(cancellation_token)
        return result

    async def check_health(
        self,
        *,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> ProviderHealth:
        self._check(cancellation_token)
        result = await asyncio.to_thread(self.provider.check_health)
        self._check(cancellation_token)
        return result

    def validate_configuration(self) -> tuple[str, ...]:
        return self.provider.validate_configuration()

    @staticmethod
    def _check(
        cancellation_token: CollectorCancellationToken | None,
    ) -> None:
        if cancellation_token is not None:
            cancellation_token.throw_if_cancelled()


__all__ = [
    "AsyncTenderProvider",
    "LegacySyncProviderAdapter",
    "ProviderCollectionPage",
    "ProviderCursorCycleError",
    "ProviderPageBudgetError",
    "ProviderPageContractError",
    "build_query_fingerprint",
]
