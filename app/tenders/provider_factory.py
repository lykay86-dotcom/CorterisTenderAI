"""Factory for the default tender provider registry."""

from __future__ import annotations

from app.tenders.provider_registry import TenderProviderRegistry
from app.tenders.providers.placeholders import (
    create_builtin_providers,
)


def create_default_provider_registry() -> TenderProviderRegistry:
    return TenderProviderRegistry(create_builtin_providers())


__all__ = ["create_default_provider_registry"]
