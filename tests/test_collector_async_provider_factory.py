from __future__ import annotations

import asyncio

import httpx

from app.tenders.collector.async_provider_factory import (
    create_default_async_providers,
    create_default_collector_service,
)
from app.tenders.collector.network_runtime import (
    create_collector_network_runtime,
)
from app.tenders.providers.eis_async import AsyncEisTenderProvider
from app.tenders.providers.mos_supplier_api import (
    AsyncMosSupplierTenderProvider,
    MosSupplierApiConfig,
)


def test_factory_registers_eis_and_moscow_supplier(tmp_path) -> None:
    async def scenario() -> None:
        raw = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, request=request))
        )
        runtime = create_collector_network_runtime(client=raw)
        service = create_default_collector_service(
            tmp_path,
            runtime,
            mos_supplier_config=MosSupplierApiConfig(api_token=""),
        )
        providers = service.engine.providers

        assert len(providers) == 2
        assert isinstance(providers[0], AsyncEisTenderProvider)
        assert isinstance(providers[1], AsyncMosSupplierTenderProvider)
        assert [item.descriptor.id for item in providers] == [
            "eis",
            "mos_supplier",
        ]
        assert providers[1].descriptor.implementation_status == ("official_api_token_required")
        assert providers[1].validate_configuration()[0].startswith("Требуется bearer-токен")
        await raw.aclose()

    asyncio.run(scenario())


def test_provider_factory_has_no_commercial_placeholders() -> None:
    async def scenario() -> None:
        raw = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, request=request))
        )
        runtime = create_collector_network_runtime(client=raw)
        providers = create_default_async_providers(
            runtime,
            mos_supplier_config=MosSupplierApiConfig(api_token="token"),
        )

        assert [item.descriptor.id for item in providers] == [
            "eis",
            "mos_supplier",
        ]
        assert all(item.descriptor.implementation_status != "placeholder" for item in providers)
        await raw.aclose()

    asyncio.run(scenario())
