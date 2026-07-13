"""Explicit composition root for collector network services."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.tenders.collector.async_http import (
    AsyncHttpClient,
    AsyncHttpClientConfig,
)
from app.tenders.collector.health_monitor import ProviderHealthMonitor
from app.tenders.collector.network_settings import (
    CollectorNetworkSettings,
    default_collector_network_settings,
)
from app.tenders.collector.rate_limiter import AsyncRateLimiter, RateLimitPolicy


@dataclass(slots=True)
class CollectorNetworkRuntime:
    """Owned network objects shared by all asynchronous providers."""

    settings: CollectorNetworkSettings
    rate_limiter: AsyncRateLimiter
    health_monitor: ProviderHealthMonitor
    http_client: AsyncHttpClient

    async def aclose(self) -> None:
        await self.http_client.aclose()

    async def __aenter__(self) -> "CollectorNetworkRuntime":
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        await self.aclose()


def create_collector_network_runtime(
    *,
    settings: CollectorNetworkSettings | None = None,
    http_config: AsyncHttpClientConfig | None = None,
    client: httpx.AsyncClient | None = None,
) -> CollectorNetworkRuntime:
    """Build shared services without making any external request."""

    effective_settings = settings or default_collector_network_settings()
    rate_limiter = AsyncRateLimiter(
        default_policy=RateLimitPolicy(
            requests_per_second=1.0,
            max_concurrent=2,
            min_interval_seconds=0.5,
        ),
        domain_policies=effective_settings.domain_rate_limits,
    )
    health_monitor = ProviderHealthMonitor(
        policies=effective_settings.health_policies,
    )
    # Official collector sources use a direct route by default. This prevents
    # an inherited system proxy from silently breaking TLS negotiation.
    effective_http_config = http_config or AsyncHttpClientConfig(trust_env=False)
    http_client = AsyncHttpClient(
        config=effective_http_config,
        rate_limiter=rate_limiter,
        client=client,
    )
    return CollectorNetworkRuntime(
        settings=effective_settings,
        rate_limiter=rate_limiter,
        health_monitor=health_monitor,
        http_client=http_client,
    )


__all__ = [
    "CollectorNetworkRuntime",
    "create_collector_network_runtime",
]
