"""Typed network settings for Corteris Tender Collector."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from app.tenders.collector.async_http import (
    AsyncHttpTimeouts,
    AsyncRetryPolicy,
)
from app.tenders.collector.health_monitor import ProviderHealthPolicy
from app.tenders.collector.rate_limiter import RateLimitPolicy


@dataclass(frozen=True, slots=True)
class ProviderNetworkSettings:
    provider_id: str
    domains: tuple[str, ...]
    timeouts: AsyncHttpTimeouts
    retry: AsyncRetryPolicy
    rate_limit: RateLimitPolicy
    health: ProviderHealthPolicy

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id must not be empty")
        if not self.domains:
            raise ValueError("domains must not be empty")


@dataclass(frozen=True, slots=True)
class CollectorNetworkSettings:
    providers: Mapping[str, ProviderNetworkSettings] = field(
        default_factory=dict
    )

    def get(self, provider_id: str) -> ProviderNetworkSettings:
        normalized = provider_id.strip().casefold()
        try:
            return self.providers[normalized]
        except KeyError as exc:
            raise KeyError(
                f"Network settings are not defined for {provider_id}"
            ) from exc

    @property
    def domain_rate_limits(self) -> dict[str, RateLimitPolicy]:
        result: dict[str, RateLimitPolicy] = {}
        for settings in self.providers.values():
            for domain in settings.domains:
                result[domain] = settings.rate_limit
        return result

    @property
    def health_policies(self) -> dict[str, ProviderHealthPolicy]:
        return {
            provider_id: settings.health
            for provider_id, settings in self.providers.items()
        }


def default_collector_network_settings() -> CollectorNetworkSettings:
    """Conservative defaults; providers may override them explicitly."""

    generic_timeouts = AsyncHttpTimeouts(
        connect_seconds=10,
        read_seconds=30,
        write_seconds=30,
        pool_seconds=10,
    )
    generic_retry = AsyncRetryPolicy(
        max_attempts=3,
        base_delay_seconds=0.75,
        max_delay_seconds=15,
    )
    generic_rate = RateLimitPolicy(
        requests_per_second=1.0,
        max_concurrent=2,
        min_interval_seconds=0.5,
        max_retries=2,
        block_after_429_seconds=60,
    )
    generic_health = ProviderHealthPolicy(
        failure_threshold=3,
        cooldown_seconds=300,
        unavailable_threshold=8,
    )

    providers = {
        "eis": ProviderNetworkSettings(
            provider_id="eis",
            domains=("zakupki.gov.ru",),
            timeouts=AsyncHttpTimeouts(
                connect_seconds=20,
                read_seconds=45,
                write_seconds=30,
                pool_seconds=15,
            ),
            retry=AsyncRetryPolicy(
                max_attempts=3,
                base_delay_seconds=1.0,
                max_delay_seconds=20,
            ),
            rate_limit=RateLimitPolicy(
                requests_per_second=0.5,
                max_concurrent=1,
                min_interval_seconds=2.0,
                max_retries=2,
                block_after_429_seconds=120,
            ),
            health=ProviderHealthPolicy(
                failure_threshold=3,
                cooldown_seconds=600,
                unavailable_threshold=8,
            ),
        ),
        "mos_supplier": ProviderNetworkSettings(
            provider_id="mos_supplier",
            domains=("zakupki.mos.ru",),
            timeouts=generic_timeouts,
            retry=generic_retry,
            rate_limit=generic_rate,
            health=generic_health,
        ),
    }
    return CollectorNetworkSettings(providers=providers)


__all__ = [
    "CollectorNetworkSettings",
    "ProviderNetworkSettings",
    "default_collector_network_settings",
]
