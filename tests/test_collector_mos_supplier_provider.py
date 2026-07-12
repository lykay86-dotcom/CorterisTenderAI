from __future__ import annotations

import asyncio
import json
from pathlib import Path
from urllib.parse import unquote

import httpx
import pytest

from app.tenders.collector.async_http import (
    AsyncHttpClient,
    AsyncHttpClientConfig,
    AsyncHttpTimeouts,
    AsyncRetryPolicy,
)
from app.tenders.collector.rate_limiter import AsyncRateLimiter, RateLimitPolicy
from app.tenders.provider_base import (
    ProviderHealthStatus,
    ProviderNotConfiguredError,
    TenderSearchQuery,
)
from app.tenders.providers.mos_supplier_api import (
    AsyncMosSupplierTenderProvider,
    MosSupplierApiConfig,
)


FIXTURES = Path(__file__).parent / "fixtures"
SEARCH_BODY = (
    FIXTURES / "mos_supplier_search_documented_contract.json"
).read_bytes()
CARD_BODY = (
    FIXTURES / "mos_supplier_card_documented_contract.json"
).read_bytes()


def _client(handler):
    raw = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    wrapper = AsyncHttpClient(
        config=AsyncHttpClientConfig(
            timeouts=AsyncHttpTimeouts(1, 1, 1, 1),
            retry_policy=AsyncRetryPolicy(
                max_attempts=2,
                base_delay_seconds=0,
                max_delay_seconds=0,
                jitter_ratio=0,
            ),
        ),
        rate_limiter=AsyncRateLimiter(
            default_policy=RateLimitPolicy(
                requests_per_second=100000,
                max_concurrent=4,
                min_interval_seconds=0,
            )
        ),
        client=raw,
    )
    return wrapper, raw


def _config(token: str = "test-bearer-token") -> MosSupplierApiConfig:
    return MosSupplierApiConfig(api_token=token)


def test_provider_requires_token_without_network_request() -> None:
    async def scenario() -> None:
        calls = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(200, content=SEARCH_BODY, request=request)

        client, raw = _client(handler)
        provider = AsyncMosSupplierTenderProvider(
            client,
            config=_config(""),
        )
        with pytest.raises(ProviderNotConfiguredError):
            await provider.search(TenderSearchQuery(keywords=("СКУД",)))
        health = await provider.check_health()

        assert calls == 0
        assert health.status == ProviderHealthStatus.NOT_CONFIGURED
        assert "CORTERIS_MOS_API_KEY" in health.message
        await raw.aclose()

    asyncio.run(scenario())


def test_provider_search_sends_bearer_and_parses_results() -> None:
    async def scenario() -> None:
        requests: list[httpx.Request] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(
                200,
                content=SEARCH_BODY,
                headers={"content-type": "application/json"},
                request=request,
            )

        client, raw = _client(handler)
        provider = AsyncMosSupplierTenderProvider(client, config=_config())
        result = await provider.search(
            TenderSearchQuery(
                keywords=("видеонаблюдение",),
                excluded_keywords=("дороги",),
                regions=("Москва",),
                min_price=100000,
                max_price=2000000,
                extra={"incremental": False},
            )
        )

        assert len(result.items) == 1
        assert result.items[0].external_id == "9294080"
        assert requests[0].headers["authorization"] == "Bearer test-bearer-token"
        payload = json.loads(unquote(requests[0].url.query.decode("ascii")))
        assert payload["filter"]["name"] == "видеонаблюдение"
        assert payload["startprice"]["start"] == [100000]
        assert provider.connection_mode == "official_api_bearer"
        assert provider.descriptor.capabilities.public_api is True
        await raw.aclose()

    asyncio.run(scenario())


def test_provider_get_tender_and_documents() -> None:
    async def scenario() -> None:
        requests: list[httpx.Request] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(
                200,
                content=CARD_BODY,
                headers={"content-type": "application/json"},
                request=request,
            )

        client, raw = _client(handler)
        provider = AsyncMosSupplierTenderProvider(client, config=_config())
        tender = await provider.get_tender("9294080")
        documents = await provider.list_documents("9294080")

        assert tender.procurement_number == "КС-9294080"
        assert len(documents) == 2
        assert len(requests) == 2
        assert all("auction/public/Get" in request.url.path for request in requests)
        await raw.aclose()

    asyncio.run(scenario())


def test_provider_health_reports_accepted_token() -> None:
    async def scenario() -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=SEARCH_BODY, request=request)

        client, raw = _client(handler)
        provider = AsyncMosSupplierTenderProvider(client, config=_config())
        health = await provider.check_health()

        assert health.status == ProviderHealthStatus.AVAILABLE
        assert "токен принят" in health.message
        assert health.latency_ms is not None
        await raw.aclose()

    asyncio.run(scenario())


def test_provider_maps_http_401_to_not_configured() -> None:
    async def scenario() -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"message": "unauthorized"}, request=request)

        client, raw = _client(handler)
        provider = AsyncMosSupplierTenderProvider(client, config=_config())
        with pytest.raises(ProviderNotConfiguredError) as captured:
            await provider.search(TenderSearchQuery(keywords=("СКУД",)))

        assert "отклонил bearer-токен" in str(captured.value)
        await raw.aclose()

    asyncio.run(scenario())
