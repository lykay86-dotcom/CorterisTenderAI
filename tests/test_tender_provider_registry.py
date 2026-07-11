"""Tests for provider registry configuration and ordering."""

from __future__ import annotations

import pytest

from app.tenders.provider_factory import (
    create_default_provider_registry,
)
from app.tenders.provider_registry import TenderProviderRegistry
from app.tenders.providers.placeholders import (
    create_builtin_providers,
)


def test_default_registry_contains_expected_platforms() -> None:
    registry = create_default_provider_registry()

    assert [
        descriptor.id
        for descriptor in registry.descriptors()
    ] == [
        "eis",
        "sber_a",
        "rts_tender",
        "roseltorg",
        "b2b_center",
        "tek_torg",
        "gazprombank",
        "commercial",
    ]
    assert not registry.is_enabled("commercial")
    assert registry.is_enabled("eis")
    assert registry.validate_unique_sources() == {}


def test_registry_enable_disable_and_priority() -> None:
    provider = create_builtin_providers()[0]
    registry = TenderProviderRegistry([provider])

    registry.set_enabled("eis", False)
    assert registry.list_enabled() == ()

    registry.set_enabled("eis", True)
    registry.set_priority("eis", 999)

    entry = registry.list_registered()[0]
    assert entry.enabled
    assert entry.priority == 999


def test_registry_rejects_duplicate_id() -> None:
    provider = create_builtin_providers()[0]
    registry = TenderProviderRegistry([provider])

    with pytest.raises(ValueError):
        registry.register(provider)

    registry.register(provider, replace=True)
    assert registry.get("eis") is provider
