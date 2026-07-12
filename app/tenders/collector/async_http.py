"""Shared asynchronous HTTP client for tender provider adapters."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import logging
import random
import re
import ssl
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from app.core.ssl_support import build_ssl_context
from app.tenders.collector.cancellation import (
    CollectorCancellationToken,
    CollectorCancelledError,
)
from app.tenders.collector.rate_limiter import (
    AsyncRateLimiter,
    DailyRateLimitExceeded,
    RateLimitPolicy,
)
from app.tenders.http_client import HttpResponse


LOGGER = logging.getLogger("corteris.tenders.collector.http")
_SENSITIVE_QUERY_NAMES = re.compile(
    r"(?:api[_-]?key|token|secret|password|passwd|signature|auth)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class AsyncHttpTimeouts:
    connect_seconds: float = 10.0
    read_seconds: float = 30.0
    write_seconds: float = 30.0
    pool_seconds: float = 10.0

    def __post_init__(self) -> None:
        for name, value in (
            ("connect_seconds", self.connect_seconds),
            ("read_seconds", self.read_seconds),
            ("write_seconds", self.write_seconds),
            ("pool_seconds", self.pool_seconds),
        ):
            if value <= 0:
                raise ValueError(f"{name} must be positive")

    def to_httpx(self) -> httpx.Timeout:
        return httpx.Timeout(
            connect=self.connect_seconds,
            read=self.read_seconds,
            write=self.write_seconds,
            pool=self.pool_seconds,
        )


@dataclass(frozen=True, slots=True)
class AsyncRetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 0.75
    backoff_multiplier: float = 2.0
    max_delay_seconds: float = 20.0
    jitter_ratio: float = 0.1
    retry_status_codes: tuple[int, ...] = (
        429,
        500,
        502,
        503,
        504,
    )
    retry_forbidden: bool = False

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.base_delay_seconds < 0:
            raise ValueError("base_delay_seconds must be non-negative")
        if self.backoff_multiplier < 1:
            raise ValueError("backoff_multiplier must be at least 1")
        if self.max_delay_seconds < 0:
            raise ValueError("max_delay_seconds must be non-negative")
        if not 0 <= self.jitter_ratio <= 1:
            raise ValueError("jitter_ratio must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class AsyncHttpClientConfig:
    timeouts: AsyncHttpTimeouts = AsyncHttpTimeouts()
    retry_policy: AsyncRetryPolicy = AsyncRetryPolicy()
    max_connections: int = 20
    max_keepalive_connections: int = 10
    keepalive_expiry_seconds: float = 30.0
    max_response_bytes: int = 50 * 1024 * 1024
    follow_redirects: bool = True
    trust_env: bool = True
    ca_bundle_path: Path | None = None
    user_agent: str = (
        "CorterisTenderAI/1.5.1 "
        "(Windows; tender collector; +https://corteris.ru)"
    )

    def __post_init__(self) -> None:
        if self.max_connections < 1:
            raise ValueError("max_connections must be positive")
        if self.max_keepalive_connections < 0:
            raise ValueError(
                "max_keepalive_connections must be non-negative"
            )
        if self.keepalive_expiry_seconds <= 0:
            raise ValueError("keepalive_expiry_seconds must be positive")
        if self.max_response_bytes < 1024:
            raise ValueError("max_response_bytes must be at least 1024")


class AsyncHttpError(RuntimeError):
    """Base error for collector HTTP requests."""

    def __init__(
        self,
        message: str,
        *,
        url: str,
        provider_id: str,
        attempts: int,
        transient: bool,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.url = url
        self.provider_id = provider_id
        self.attempts = attempts
        self.transient = transient
        self.status_code = status_code


class AsyncHttpStatusError(AsyncHttpError):
    """HTTP status response considered an error by the collector."""


class AsyncHttpTransportError(AsyncHttpError):
    """Network, SSL or timeout error after retry processing."""


class AsyncHttpResponseTooLargeError(AsyncHttpError):
    """Response exceeded the configured byte limit."""


class AsyncHttpClient:
    """HTTPX AsyncClient wrapper with retries, limits and cancellation."""

    def __init__(
        self,
        *,
        config: AsyncHttpClientConfig | None = None,
        rate_limiter: AsyncRateLimiter | None = None,
        client: httpx.AsyncClient | None = None,
        random_source: random.Random | None = None,
    ) -> None:
        self.config = config or AsyncHttpClientConfig()
        self.rate_limiter = rate_limiter or AsyncRateLimiter(
            default_policy=RateLimitPolicy()
        )
        self._random = random_source or random.Random()
        self._owns_client = client is None
        self._closed = False
        self._client = client or self._create_client(self.config)

    @staticmethod
    def _create_client(config: AsyncHttpClientConfig) -> httpx.AsyncClient:
        ssl_context = build_ssl_context(
            config.ca_bundle_path
        )
        return httpx.AsyncClient(
            timeout=config.timeouts.to_httpx(),
            limits=httpx.Limits(
                max_connections=config.max_connections,
                max_keepalive_connections=(
                    config.max_keepalive_connections
                ),
                keepalive_expiry=config.keepalive_expiry_seconds,
            ),
            verify=ssl_context,
            follow_redirects=config.follow_redirects,
            trust_env=config.trust_env,
            headers={"User-Agent": config.user_agent},
        )

    @property
    def is_closed(self) -> bool:
        return self._closed

    async def __aenter__(self) -> "AsyncHttpClient":
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._owns_client:
            await self._client.aclose()

    async def get(
        self,
        url: str,
        *,
        provider_id: str,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        timeouts: AsyncHttpTimeouts | None = None,
        retry_policy: AsyncRetryPolicy | None = None,
        cancellation_token: CollectorCancellationToken | None = None,
        raise_for_status: bool = True,
    ) -> HttpResponse:
        return await self.request(
            "GET",
            url,
            provider_id=provider_id,
            headers=headers,
            params=params,
            timeouts=timeouts,
            retry_policy=retry_policy,
            cancellation_token=cancellation_token,
            raise_for_status=raise_for_status,
        )

    async def request(
        self,
        method: str,
        url: str,
        *,
        provider_id: str,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        content: bytes | None = None,
        timeouts: AsyncHttpTimeouts | None = None,
        retry_policy: AsyncRetryPolicy | None = None,
        cancellation_token: CollectorCancellationToken | None = None,
        raise_for_status: bool = True,
    ) -> HttpResponse:
        if self._closed:
            raise RuntimeError("AsyncHttpClient is closed")
        normalized_provider_id = provider_id.strip().casefold()
        if not normalized_provider_id:
            raise ValueError("provider_id must not be empty")
        if cancellation_token is not None:
            cancellation_token.throw_if_cancelled()

        policy = retry_policy or self.config.retry_policy
        effective_timeouts = timeouts or self.config.timeouts
        safe_url = sanitize_url(url)
        last_error: BaseException | None = None

        for attempt in range(1, policy.max_attempts + 1):
            if cancellation_token is not None:
                cancellation_token.throw_if_cancelled()
            try:
                async with self.rate_limiter.limit(
                    url,
                    cancellation_token=cancellation_token,
                ):
                    response = await self._send_once(
                        method,
                        url,
                        headers=headers,
                        params=params,
                        content=content,
                        timeouts=effective_timeouts,
                        provider_id=normalized_provider_id,
                        cancellation_token=cancellation_token,
                    )
            except CollectorCancelledError:
                raise
            except DailyRateLimitExceeded:
                raise
            except AsyncHttpResponseTooLargeError:
                raise
            except httpx.HTTPError as exc:
                last_error = exc
                transient = _is_transient_httpx_error(exc)
                if not transient or attempt >= policy.max_attempts:
                    raise AsyncHttpTransportError(
                        _transport_message(exc, attempt),
                        url=safe_url,
                        provider_id=normalized_provider_id,
                        attempts=attempt,
                        transient=transient,
                    ) from exc
                await self._retry_sleep(
                    policy,
                    attempt,
                    cancellation_token=cancellation_token,
                )
                continue

            status_code = response.status_code
            retryable_status = status_code in policy.retry_status_codes
            if status_code == 403 and policy.retry_forbidden:
                retryable_status = True

            if retryable_status and attempt < policy.max_attempts:
                retry_after = parse_retry_after(
                    response.headers.get("retry-after", "")
                )
                delay = (
                    retry_after
                    if retry_after is not None
                    else self._retry_delay(policy, attempt)
                )
                if status_code == 429:
                    if retry_after is None and delay <= 0:
                        delay = self.rate_limiter.policy_for(
                            url
                        ).block_after_429_seconds
                    await self.rate_limiter.block(url, delay)
                LOGGER.warning(
                    "collector_http_retry provider=%s status=%s "
                    "attempt=%s delay=%.3f url=%s",
                    normalized_provider_id,
                    status_code,
                    attempt,
                    delay,
                    safe_url,
                )
                await self._sleep(
                    delay,
                    cancellation_token=cancellation_token,
                )
                continue

            if raise_for_status and status_code >= 400:
                transient = retryable_status
                raise AsyncHttpStatusError(
                    _status_message(status_code, attempt),
                    url=safe_url,
                    provider_id=normalized_provider_id,
                    attempts=attempt,
                    transient=transient,
                    status_code=status_code,
                )

            LOGGER.info(
                "collector_http_success provider=%s status=%s "
                "attempt=%s bytes=%s url=%s",
                normalized_provider_id,
                status_code,
                attempt,
                len(response.content),
                safe_url,
            )
            return HttpResponse(
                url=str(response.url),
                status_code=status_code,
                headers={
                    key.casefold(): value
                    for key, value in response.headers.items()
                },
                body=response.content,
            )

        raise AsyncHttpTransportError(
            _transport_message(last_error or RuntimeError("unknown"), policy.max_attempts),
            url=safe_url,
            provider_id=normalized_provider_id,
            attempts=policy.max_attempts,
            transient=True,
        )

    async def _send_once(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None,
        params: Mapping[str, Any] | None,
        content: bytes | None,
        timeouts: AsyncHttpTimeouts,
        provider_id: str,
        cancellation_token: CollectorCancellationToken | None,
    ) -> httpx.Response:
        async def perform() -> httpx.Response:
            async with self._client.stream(
                method.upper(),
                url,
                headers=headers,
                params=params,
                content=content,
                timeout=timeouts.to_httpx(),
            ) as response:
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > self.config.max_response_bytes:
                        raise AsyncHttpResponseTooLargeError(
                            "HTTP-ответ превышает безопасный лимит размера.",
                            url=sanitize_url(url),
                            provider_id=provider_id,
                            attempts=1,
                            transient=False,
                            status_code=response.status_code,
                        )
                    chunks.append(chunk)
                return httpx.Response(
                    status_code=response.status_code,
                    headers=response.headers,
                    content=b"".join(chunks),
                    request=response.request,
                    extensions=response.extensions,
                )

        if cancellation_token is None:
            return await perform()

        request_task = asyncio.create_task(perform())
        cancel_task = asyncio.create_task(
            cancellation_token.wait_cancelled()
        )
        done, pending = await asyncio.wait(
            {request_task, cancel_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        if cancel_task in done:
            request_task.cancel()
            with suppress(asyncio.CancelledError):
                await request_task
            cancellation_token.throw_if_cancelled()
        cancel_task.cancel()
        return await request_task

    async def _retry_sleep(
        self,
        policy: AsyncRetryPolicy,
        attempt: int,
        *,
        cancellation_token: CollectorCancellationToken | None,
    ) -> None:
        await self._sleep(
            self._retry_delay(policy, attempt),
            cancellation_token=cancellation_token,
        )

    def _retry_delay(
        self,
        policy: AsyncRetryPolicy,
        attempt: int,
    ) -> float:
        base = min(
            policy.max_delay_seconds,
            policy.base_delay_seconds
            * (policy.backoff_multiplier ** max(0, attempt - 1)),
        )
        if base <= 0 or policy.jitter_ratio <= 0:
            return base
        spread = base * policy.jitter_ratio
        return max(0.0, base + self._random.uniform(-spread, spread))

    async def _sleep(
        self,
        seconds: float,
        *,
        cancellation_token: CollectorCancellationToken | None,
    ) -> None:
        if seconds <= 0:
            if cancellation_token is not None:
                cancellation_token.throw_if_cancelled()
            return
        if cancellation_token is None:
            await asyncio.sleep(seconds)
        else:
            await cancellation_token.sleep(seconds)


def parse_retry_after(value: str, *, now: datetime | None = None) -> float | None:
    normalized = value.strip()
    if not normalized:
        return None
    try:
        seconds = float(normalized)
    except ValueError:
        try:
            parsed = parsedate_to_datetime(normalized)
        except (TypeError, ValueError, OverflowError):
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        return max(0.0, (parsed - current).total_seconds())
    return max(0.0, seconds)


def sanitize_url(url: str) -> str:
    parsed = urlsplit(url)
    query = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        query.append(
            (key, "***" if _SENSITIVE_QUERY_NAMES.search(key) else value)
        )
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(query),
            "",
        )
    )


def _is_transient_httpx_error(error: httpx.HTTPError) -> bool:
    if _is_certificate_error(error):
        return False
    return isinstance(
        error,
        (
            httpx.TimeoutException,
            httpx.NetworkError,
            httpx.RemoteProtocolError,
            httpx.ProxyError,
        ),
    )


def _is_certificate_error(error: BaseException) -> bool:
    current: BaseException | None = error
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        if isinstance(current, ssl.SSLCertVerificationError):
            return True
        message = str(current).casefold()
        if any(
            marker in message
            for marker in (
                "certificate verify failed",
                "hostname mismatch",
                "unknown ca",
            )
        ):
            return True
        current = current.__cause__ or current.__context__
    return False


def _transport_message(error: BaseException, attempts: int) -> str:
    detail = str(error).strip() or type(error).__name__
    lowered = detail.casefold()
    if "handshake" in lowered and "timed out" in lowered:
        reason = "таймаут SSL-рукопожатия"
    elif "timed out" in lowered or "timeout" in lowered:
        reason = "сетевой таймаут"
    elif _is_certificate_error(error):
        reason = "ошибка проверки TLS-сертификата"
    else:
        reason = detail
    return f"HTTP-запрос не выполнен после {attempts} попыток: {reason}"


def _status_message(status_code: int, attempts: int) -> str:
    explanations = {
        403: "доступ запрещён источником",
        404: "ресурс не найден",
        429: "источник ограничил частоту запросов",
        500: "внутренняя ошибка источника",
        502: "ошибка шлюза источника",
        503: "источник временно недоступен",
        504: "таймаут шлюза источника",
    }
    detail = explanations.get(status_code, "ошибка HTTP")
    return f"HTTP {status_code}: {detail}; попыток: {attempts}"


__all__ = [
    "AsyncHttpClient",
    "AsyncHttpClientConfig",
    "AsyncHttpError",
    "AsyncHttpResponseTooLargeError",
    "AsyncHttpStatusError",
    "AsyncHttpTimeouts",
    "AsyncHttpTransportError",
    "AsyncRetryPolicy",
    "parse_retry_after",
    "sanitize_url",
]
