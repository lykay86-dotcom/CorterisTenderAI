"""Tests for non-secret provider enablement settings."""

from __future__ import annotations

from app.tenders.collector.provider_settings import (
    ProviderEnablementRepository,
)
from app.tenders.providers.eis_async import AsyncEisTenderProvider
from app.tenders.providers.commercial_catalog import (
    default_commercial_provider_definitions,
)


def test_enablement_uses_descriptor_defaults(tmp_path) -> None:
    repository = ProviderEnablementRepository(tmp_path / "provider_settings.json")
    commercial = default_commercial_provider_definitions()[0]

    assert repository.is_enabled(AsyncEisTenderProvider.descriptor)
    assert not repository.is_enabled(commercial.descriptor)


def test_enablement_roundtrip_is_atomic_and_non_secret(
    tmp_path,
) -> None:
    path = tmp_path / "provider_settings.json"
    repository = ProviderEnablementRepository(path)

    repository.set_enabled("eis", False)
    repository.set_enabled("mos_supplier", True)

    assert repository.load() == {
        "eis": False,
        "mos_supplier": True,
    }
    text = path.read_text(encoding="utf-8")
    assert "token" not in text.casefold()
    assert "api_key" not in text.casefold()
