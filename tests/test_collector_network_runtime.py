from __future__ import annotations

import asyncio

import httpx

from app.tenders.collector.network_runtime import (
    create_collector_network_runtime,
)


def test_network_runtime_builds_without_external_requests() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, request=request)

    async def scenario() -> None:
        raw_client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        )
        runtime = create_collector_network_runtime(client=raw_client)
        assert calls == 0
        assert runtime.settings.get("eis").domains == (
            "zakupki.gov.ru",
        )
        assert runtime.health_monitor.snapshot("eis").provider_id == "eis"
        await runtime.aclose()
        await raw_client.aclose()

    asyncio.run(scenario())
