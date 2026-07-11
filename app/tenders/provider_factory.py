"""Factory for the default tender provider registry."""

from __future__ import annotations

from app.tenders.http_client import HttpTransport
from app.tenders.provider_registry import TenderProviderRegistry
from app.tenders.providers.eis import EisTenderProvider
from app.tenders.providers.placeholders import create_builtin_providers


def create_default_provider_registry(
    *,
    http_transport: HttpTransport | None = None,
) -> TenderProviderRegistry:
    providers = [
        provider
        for provider in create_builtin_providers()
        if provider.descriptor.id != "eis"
    ]
    providers.insert(
        0,
        EisTenderProvider(transport=http_transport),
    )
    return TenderProviderRegistry(providers)


__all__ = ["create_default_provider_registry"]
