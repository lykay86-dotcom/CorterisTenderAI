from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx

from app.tenders.collector.async_http import (
    AsyncHttpClient,
    AsyncHttpClientConfig,
    AsyncHttpTimeouts,
    AsyncRetryPolicy,
)
from app.tenders.collector.rate_limiter import (
    AsyncRateLimiter,
    RateLimitPolicy,
)
from app.tenders.models import TenderStatus
from app.tenders.provider_base import (
    ProviderHealthStatus,
    TenderSearchQuery,
)
from app.tenders.providers.eis_async import AsyncEisTenderProvider


FIXTURES = Path(__file__).parent / "fixtures"
SEARCH_HTML = (FIXTURES / "eis_search_results.html").read_bytes()
DOCUMENTS_HTML = (FIXTURES / "eis_documents.html").read_bytes()


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


def test_async_eis_search_uses_public_query_and_parser() -> None:
    async def scenario() -> None:
        calls: list[str] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            return httpx.Response(
                200,
                content=SEARCH_HTML,
                headers={"content-type": "text/html; charset=utf-8"},
                request=request,
            )

        client, raw = _client(handler)
        provider = AsyncEisTenderProvider(client)
        result = await provider.search(
            TenderSearchQuery(
                keywords=("видеонаблюдение", "СКУД"),
                excluded_keywords=("продукты",),
                regions=("Москва",),
                laws=("44-ФЗ",),
                date_from=date(2026, 7, 1),
                date_to=date(2026, 7, 31),
                min_price=1_000_000,
                max_price=2_000_000,
                page=2,
                page_size=25,
                extra={"incremental": False},
            )
        )

        assert len(result.items) == 1
        assert result.items[0].status == TenderStatus.ACCEPTING_APPLICATIONS
        assert provider.connection_mode == "public_html_async"
        assert provider.descriptor.capabilities.public_api is False
        assert any("не официальный API" in item for item in result.warnings)

        parsed = urlparse(calls[0])
        params = parse_qs(parsed.query)
        assert parsed.netloc == "zakupki.gov.ru"
        assert parsed.path.endswith("/extendedsearch/results.html")
        assert params["searchString"] == ["видеонаблюдение СКУД"]
        assert params["pageNumber"] == ["2"]
        assert params["recordsPerPage"] == ["_50"]
        assert params["fz44"] == ["on"]
        assert "fz223" not in params
        await raw.aclose()

    asyncio.run(scenario())


def test_async_eis_get_tender_and_documents() -> None:
    async def scenario() -> None:
        calls: list[str] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            body = (
                DOCUMENTS_HTML
                if "documents.html" in request.url.path
                else SEARCH_HTML
            )
            return httpx.Response(
                200,
                content=body,
                headers={"content-type": "text/html; charset=utf-8"},
                request=request,
            )

        client, raw = _client(handler)
        provider = AsyncEisTenderProvider(client)
        tender = await provider.get_tender("0373100000126000001")
        documents = await provider.list_documents(
            "0373100000126000001"
        )

        assert tender.procurement_number == "0373100000126000001"
        assert [item.name for item in documents] == [
            "Описание объекта закупки.pdf",
            "Форма заявки.docx",
        ]
        assert any("documents.html" in item for item in calls)
        await raw.aclose()

    asyncio.run(scenario())


def test_async_eis_health_check_reports_public_html_mode() -> None:
    async def scenario() -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                text="Единая информационная система в сфере закупок",
                request=request,
            )

        client, raw = _client(handler)
        provider = AsyncEisTenderProvider(client)
        health = await provider.check_health()

        assert health.status == ProviderHealthStatus.AVAILABLE
        assert "public_html_async" in health.message
        assert health.latency_ms is not None
        await raw.aclose()

    asyncio.run(scenario())


def test_async_eis_retries_transient_timeout() -> None:
    async def scenario() -> None:
        calls = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise httpx.ConnectTimeout(
                    "SSL handshake operation timed out",
                    request=request,
                )
            return httpx.Response(
                200,
                content=SEARCH_HTML,
                request=request,
            )

        client, raw = _client(handler)
        provider = AsyncEisTenderProvider(client)
        result = await provider.search(
            TenderSearchQuery(
                keywords=("видеонаблюдение",),
                extra={"incremental": False},
            )
        )

        assert result.items
        assert calls == 2
        await raw.aclose()

    asyncio.run(scenario())
