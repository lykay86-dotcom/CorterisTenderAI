"""Built-in provider descriptors and non-network placeholders."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Sequence

from app.tenders.models import (
    TenderDocument,
    UnifiedTender,
)
from app.tenders.provider_base import (
    ProviderCapabilityError,
    ProviderDescriptor,
    ProviderHealth,
    ProviderHealthStatus,
    ProviderNotConfiguredError,
    TenderProvider,
    TenderSearchQuery,
    TenderSearchResult,
)


class PlaceholderTenderProvider(TenderProvider):
    """Descriptor-only adapter used until a real connector is enabled."""

    def __init__(
        self,
        descriptor: ProviderDescriptor,
    ) -> None:
        self.descriptor = descriptor

    def search(
        self,
        query: TenderSearchQuery,
    ) -> TenderSearchResult:
        if not self.descriptor.capabilities.search:
            raise ProviderCapabilityError(f"{self.descriptor.display_name} does not support search")
        raise ProviderNotConfiguredError(
            f"{self.descriptor.display_name}: connector is not configured"
        )

    def get_tender(
        self,
        external_id: str,
    ) -> UnifiedTender:
        if not self.descriptor.capabilities.tender_details:
            raise ProviderCapabilityError(
                f"{self.descriptor.display_name} does not support tender details"
            )
        raise ProviderNotConfiguredError(
            f"{self.descriptor.display_name}: connector is not configured"
        )

    def list_documents(
        self,
        external_id: str,
    ) -> Sequence[TenderDocument]:
        if not self.descriptor.capabilities.documents:
            raise ProviderCapabilityError(
                f"{self.descriptor.display_name} does not support documents"
            )
        raise ProviderNotConfiguredError(
            f"{self.descriptor.display_name}: connector is not configured"
        )

    def check_health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_id=self.descriptor.id,
            status=ProviderHealthStatus.NOT_CONFIGURED,
            checked_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            message="Коннектор подготовлен, но ещё не настроен.",
        )

    def validate_configuration(self) -> tuple[str, ...]:
        return ("Реальная интеграция будет подключена в следующих коммитах.",)


def create_builtin_providers() -> tuple[TenderProvider, ...]:
    """Project the canonical catalog into the legacy synchronous registry."""

    # Imported lazily because the canonical async catalog imports this provider class.
    from app.tenders.collector.provider_definitions import canonical_provider_definitions

    return tuple(
        PlaceholderTenderProvider(
            descriptor
            if descriptor.id == "eis"
            else replace(
                descriptor,
                enabled_by_default=False,
                implementation_status="placeholder",
            )
        )
        for descriptor in canonical_provider_definitions()
    )


__all__ = [
    "PlaceholderTenderProvider",
    "create_builtin_providers",
]
