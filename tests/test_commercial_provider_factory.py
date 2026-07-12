from __future__ import annotations

import asyncio

import httpx

from app.tenders.collector.async_provider_factory import (
    create_default_async_providers,
)
from app.tenders.collector.network_runtime import (
    create_collector_network_runtime,
)
from app.tenders.providers.commercial_adapter import (
    AsyncCommercialAccessProvider,
)
from app.tenders.providers.commercial_catalog import (
    create_commercial_provider_catalog,
)
from app.tenders.providers.mos_supplier_config import MosSupplierApiConfig


def test_default_factory_still_excludes_commercial_catalog() -> None:
    async def scenario() -> None:
        raw = httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, request=request)
            )
        )
        runtime = create_collector_network_runtime(client=raw)
        providers = create_default_async_providers(
            runtime,
            mos_supplier_config=MosSupplierApiConfig(api_token=""),
        )

        assert [item.descriptor.id for item in providers] == [
            "eis",
            "mos_supplier",
        ]
        await raw.aclose()

    asyncio.run(scenario())


def test_factory_adds_only_explicitly_enabled_commercial_adapters() -> None:
    async def scenario() -> None:
        raw = httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, request=request)
            )
        )
        runtime = create_collector_network_runtime(client=raw)
        catalog = create_commercial_provider_catalog(
            environment={
                "CORTERIS_B2B_ENABLED": "true",
            }
        )
        providers = create_default_async_providers(
            runtime,
            mos_supplier_config=MosSupplierApiConfig(api_token=""),
            include_commercial_catalog=True,
            commercial_catalog=catalog,
        )

        assert [item.descriptor.id for item in providers] == [
            "eis",
            "mos_supplier",
            "b2b_center",
        ]
        assert isinstance(providers[-1], AsyncCommercialAccessProvider)
        await raw.aclose()

    asyncio.run(scenario())
