"""Factory tests for source enablement integration."""

from __future__ import annotations

from app.tenders.collector.async_provider_factory import (
    create_default_async_providers,
)
from app.tenders.collector.network_runtime import (
    create_collector_network_runtime,
)
from app.tenders.collector.provider_settings import (
    ProviderEnablementRepository,
)
from app.tenders.providers.commercial_catalog import (
    create_commercial_provider_catalog,
)


def test_factory_filters_disabled_sources(tmp_path) -> None:
    settings = ProviderEnablementRepository(tmp_path / "sources.json")
    settings.set_enabled("eis", False)
    settings.set_enabled("mos_supplier", True)
    runtime = create_collector_network_runtime()

    try:
        providers = create_default_async_providers(
            runtime,
            provider_settings_repository=settings,
        )
    finally:
        __import__("asyncio").run(runtime.aclose())

    assert [item.descriptor.id for item in providers] == ["mos_supplier"]


def test_factory_can_return_disabled_sources_for_ui(
    tmp_path,
) -> None:
    settings = ProviderEnablementRepository(tmp_path / "sources.json")
    catalog = create_commercial_provider_catalog(
        settings_path=tmp_path / "commercial.json",
        environment={},
        keyring_loader=lambda _name: None,
    )
    runtime = create_collector_network_runtime()

    try:
        providers = create_default_async_providers(
            runtime,
            include_commercial_catalog=True,
            commercial_catalog=catalog,
            provider_settings_repository=settings,
            include_disabled=True,
        )
    finally:
        __import__("asyncio").run(runtime.aclose())

    ids = {item.descriptor.id for item in providers}
    assert "eis" in ids
    assert "mos_supplier" in ids
    assert "b2b_center" in ids
    assert len(ids) == 13
