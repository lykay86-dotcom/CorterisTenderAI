"""Descriptor-only async adapters for commercial platforms.

C6 intentionally contains no unverified HTML parser or invented API contract.
Every operation fails with an explicit configuration/readiness message until a
future commit is backed by a permitted real response and fixtures.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from app.tenders.collector.async_provider import AsyncTenderProvider
from app.tenders.collector.cancellation import CollectorCancellationToken
from app.tenders.models import TenderDocument, UnifiedTender
from app.tenders.provider_base import (
    ProviderHealth,
    ProviderHealthStatus,
    ProviderNotConfiguredError,
    TenderSearchQuery,
    TenderSearchResult,
)
from app.tenders.providers.commercial_catalog import (
    CommercialProviderResolvedSettings,
    CommercialProviderState,
)


class AsyncCommercialAccessProvider(AsyncTenderProvider):
    """Future connector shell with honest readiness and no network calls."""

    connection_mode = "commercial_access_pending"
    parser_version = "catalog-1"

    def __init__(
        self,
        settings: CommercialProviderResolvedSettings,
    ) -> None:
        self.settings = settings
        self.descriptor = settings.definition.descriptor

    async def search(
        self,
        query: TenderSearchQuery,
        *,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> TenderSearchResult:
        del query
        if cancellation_token is not None:
            cancellation_token.throw_if_cancelled()
        raise ProviderNotConfiguredError(self._operation_message("поиск"))

    async def get_tender(
        self,
        external_id: str,
        *,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> UnifiedTender:
        del external_id
        if cancellation_token is not None:
            cancellation_token.throw_if_cancelled()
        raise ProviderNotConfiguredError(
            self._operation_message("получение карточки")
        )

    async def list_documents(
        self,
        external_id: str,
        *,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> Sequence[TenderDocument]:
        del external_id
        if cancellation_token is not None:
            cancellation_token.throw_if_cancelled()
        raise ProviderNotConfiguredError(
            self._operation_message("получение документов")
        )

    async def check_health(
        self,
        *,
        cancellation_token: CollectorCancellationToken | None = None,
    ) -> ProviderHealth:
        if cancellation_token is not None:
            cancellation_token.throw_if_cancelled()
        status = ProviderHealthStatus.NOT_CONFIGURED
        if self.settings.state == (
            CommercialProviderState.READY_FOR_VERIFICATION
        ):
            status = ProviderHealthStatus.UNKNOWN
        return ProviderHealth(
            provider_id=self.descriptor.id,
            status=status,
            checked_at=datetime.now(timezone.utc).isoformat(
                timespec="seconds"
            ),
            message=self.settings.message,
            latency_ms=0,
        )

    def validate_configuration(self) -> tuple[str, ...]:
        if self.settings.state == (
            CommercialProviderState.READY_FOR_VERIFICATION
        ):
            return (
                "Настройки заполнены, но реальный API-контракт ещё не "
                "подтверждён тестовым разрешённым ответом.",
            )
        return (self.settings.message,)

    def _operation_message(self, operation: str) -> str:
        return (
            f"{self.descriptor.display_name}: {operation} недоступно. "
            f"{self.settings.message}"
        )


def create_commercial_access_providers(
    settings: Sequence[CommercialProviderResolvedSettings],
    *,
    enabled_only: bool = False,
) -> tuple[AsyncCommercialAccessProvider, ...]:
    selected = (
        item for item in settings if (item.enabled or not enabled_only)
    )
    return tuple(AsyncCommercialAccessProvider(item) for item in selected)


__all__ = [
    "AsyncCommercialAccessProvider",
    "create_commercial_access_providers",
]
