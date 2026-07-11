from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx
import pytest

from app.tenders.collector.async_http import (
    AsyncHttpClient,
    AsyncHttpClientConfig,
    AsyncHttpStatusError,
    AsyncHttpTimeouts,
    AsyncRetryPolicy,
    parse_retry_after,
    sanitize_url,
)
from app.tenders.collector.rate_limiter import (
    AsyncRateLimiter,
    RateLimitPolicy,
)


def _config(*, attempts: int = 3) -> AsyncHttpClientConfig:
    return AsyncHttpClientConfig(
        timeouts=AsyncHttpTimeouts(1, 1, 1, 1),
        retry_policy=AsyncRetryPolicy(
            max_attempts=attempts,
            base_delay_seconds=0,
            max_delay_seconds=0,
            jitter_ratio=0,
        ),
        max_response_bytes=1024 * 1024,
    )


def _limiter() -> AsyncRateLimiter:
    return AsyncRateLimiter(
        default_policy=RateLimitPolicy(
            requests_per_second=100000,
            max_concurrent=4,
            min_interval_seconds=0,
        )
    )


def test_http_client_retries_timeout_then_succeeds() -> None:
    async def scenario() -> None:
        calls = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise httpx.ConnectTimeout("ssl handshake timed out", request=request)
            return httpx.Response(200, text="ok", request=request)

        raw_client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        )
        client = AsyncHttpClient(
            config=_config(),
            rate_limiter=_limiter(),
            client=raw_client,
        )
        response = await client.get(
            "https://example.org/test",
            provider_id="demo",
        )
        assert response.status_code == 200
        assert response.body == b"ok"
        assert calls == 2
        await raw_client.aclose()

    asyncio.run(scenario())


def test_http_client_retries_429_and_500() -> None:
    async def scenario() -> None:
        statuses = iter((429, 500, 200))
        calls = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            status = next(statuses)
            headers = {"Retry-After": "0"} if status == 429 else {}
            return httpx.Response(
                status,
                headers=headers,
                text="ok",
                request=request,
            )

        raw_client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        )
        client = AsyncHttpClient(
            config=_config(attempts=3),
            rate_limiter=_limiter(),
            client=raw_client,
        )
        response = await client.get(
            "https://example.org/test",
            provider_id="demo",
        )
        assert response.status_code == 200
        assert calls == 3
        await raw_client.aclose()

    asyncio.run(scenario())


def test_http_client_does_not_retry_403_by_default() -> None:
    async def scenario() -> None:
        calls = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(403, request=request)

        raw_client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        )
        client = AsyncHttpClient(
            config=_config(),
            rate_limiter=_limiter(),
            client=raw_client,
        )
        with pytest.raises(AsyncHttpStatusError) as captured:
            await client.get(
                "https://example.org/test",
                provider_id="demo",
            )
        assert captured.value.status_code == 403
        assert calls == 1
        await raw_client.aclose()

    asyncio.run(scenario())


def test_retry_after_and_url_redaction() -> None:
    now = datetime(2026, 7, 12, tzinfo=timezone.utc)
    assert parse_retry_after("12", now=now) == 12
    assert parse_retry_after("invalid", now=now) is None
    rendered = sanitize_url(
        "https://example.org/a?api_key=secret&q=camera#fragment"
    )
    assert "secret" not in rendered
    assert "api_key=%2A%2A%2A" in rendered
    assert "q=camera" in rendered
    assert "fragment" not in rendered


def test_certificate_verification_error_is_not_retried() -> None:
    async def scenario() -> None:
        calls = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            raise httpx.ConnectError(
                "certificate verify failed",
                request=request,
            )

        raw_client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        )
        client = AsyncHttpClient(
            config=_config(),
            rate_limiter=_limiter(),
            client=raw_client,
        )
        from app.tenders.collector.async_http import AsyncHttpTransportError

        with pytest.raises(AsyncHttpTransportError) as captured:
            await client.get(
                "https://example.org/test",
                provider_id="demo",
            )
        assert calls == 1
        assert not captured.value.transient
        await raw_client.aclose()

    asyncio.run(scenario())


def test_http_request_can_be_cancelled_while_waiting() -> None:
    async def scenario() -> None:
        from app.tenders.collector.cancellation import (
            CollectorCancellationToken,
            CollectorCancelledError,
        )

        async def handler(request: httpx.Request) -> httpx.Response:
            await asyncio.sleep(10)
            return httpx.Response(200, request=request)

        raw_client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        )
        client = AsyncHttpClient(
            config=_config(),
            rate_limiter=_limiter(),
            client=raw_client,
        )
        token = CollectorCancellationToken()
        task = asyncio.create_task(
            client.get(
                "https://example.org/slow",
                provider_id="demo",
                cancellation_token=token,
            )
        )
        await asyncio.sleep(0.02)
        token.cancel("stop")
        with pytest.raises(CollectorCancelledError):
            await asyncio.wait_for(task, timeout=0.5)
        await raw_client.aclose()

    asyncio.run(scenario())
