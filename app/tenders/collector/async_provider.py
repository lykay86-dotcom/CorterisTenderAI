"""Asynchronous provider contract and compatibility adapter."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Sequence

from app.tenders.collector.cancellation import CollectorCancellationToken
from app.tenders.models import TenderDocument, UnifiedTender
from app.tenders.provider_base import (
    ProviderDescriptor,
    ProviderHealth,
    TenderProvider,
    TenderSearchQuery,
    TenderSearchResult,
)


class AsyncTenderProvider(ABC):
    """Provider contract for new non-blocking collector connectors."""

    descriptor: ProviderDescriptor
    connection_mode: str = "unknown"
    parser_version: str = "1"

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
]
