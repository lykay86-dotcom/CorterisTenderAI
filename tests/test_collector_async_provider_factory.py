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


def test_factory_registers_only_real_native_eis(tmp_path) -> None:
    async def scenario() -> None:
        raw = httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, request=request)
            )
        )
        runtime = create_collector_network_runtime(client=raw)
        service = create_default_collector_service(tmp_path, runtime)
        providers = service.engine.providers

        assert len(providers) == 1
        assert isinstance(providers[0], AsyncEisTenderProvider)
        assert providers[0].descriptor.id == "eis"
        assert providers[0].descriptor.implementation_status == (
            "public_html_async"
        )
        await raw.aclose()

    asyncio.run(scenario())


def test_provider_factory_has_no_commercial_placeholders() -> None:
    async def scenario() -> None:
        raw = httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, request=request)
            )
        )
        runtime = create_collector_network_runtime(client=raw)
        providers = create_default_async_providers(runtime)

        assert [item.descriptor.id for item in providers] == ["eis"]
        await raw.aclose()

    asyncio.run(scenario())
