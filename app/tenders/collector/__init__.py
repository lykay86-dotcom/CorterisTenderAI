"""Corteris Tender Collector public integration namespace.

Imports are side-effect free: no network clients, schedulers or provider
checks are started until the composition root creates them explicitly.
"""

from app.tenders.collector.async_engine import (
    AsyncProviderBatchResult,
    AsyncProviderSearchEngine,
    AsyncProviderSearchOutcome,
    AsyncProviderSearchStatus,
)
from app.tenders.collector.async_http import (
    AsyncHttpClient,
    AsyncHttpClientConfig,
    AsyncHttpError,
    AsyncHttpResponseTooLargeError,
    AsyncHttpStatusError,
    AsyncHttpTimeouts,
    AsyncHttpTransportError,
    AsyncRetryPolicy,
    parse_retry_after,
    sanitize_url,
)
from app.tenders.collector.async_provider import (
    AsyncTenderProvider,
    LegacySyncProviderAdapter,
)
from app.tenders.collector.baseline import (
    COLLECTOR_ARCHITECTURE_VERSION,
    CollectorArchitectureBaseline,
    CollectorProviderBaseline,
    build_collector_baseline,
)
from app.tenders.collector.cancellation import (
    CancellationSnapshot,
    CollectorCancellationToken,
    CollectorCancelledError,
)
from app.tenders.collector.health_monitor import (
    ProviderCircuitOpenError,
    ProviderHealthMonitor,
    ProviderHealthPolicy,
    ProviderHealthSnapshot,
    ProviderOperationalStatus,
)
from app.tenders.collector.network_runtime import (
    CollectorNetworkRuntime,
    create_collector_network_runtime,
)
from app.tenders.collector.network_settings import (
    CollectorNetworkSettings,
    ProviderNetworkSettings,
    default_collector_network_settings,
)
from app.tenders.collector.rate_limiter import (
    AsyncRateLimiter,
    DailyRateLimitExceeded,
    RateLimitPolicy,
    RateLimitSnapshot,
)

__all__ = [
    "AsyncHttpClient",
    "AsyncHttpClientConfig",
    "AsyncHttpError",
    "AsyncHttpResponseTooLargeError",
    "AsyncHttpStatusError",
    "AsyncHttpTimeouts",
    "AsyncHttpTransportError",
    "AsyncProviderBatchResult",
    "AsyncProviderSearchEngine",
    "AsyncProviderSearchOutcome",
    "AsyncProviderSearchStatus",
    "AsyncRateLimiter",
    "AsyncRetryPolicy",
    "AsyncTenderProvider",
    "COLLECTOR_ARCHITECTURE_VERSION",
    "CancellationSnapshot",
    "CollectorArchitectureBaseline",
    "CollectorCancellationToken",
    "CollectorCancelledError",
    "CollectorNetworkRuntime",
    "CollectorNetworkSettings",
    "CollectorProviderBaseline",
    "DailyRateLimitExceeded",
    "LegacySyncProviderAdapter",
    "ProviderCircuitOpenError",
    "ProviderHealthMonitor",
    "ProviderHealthPolicy",
    "ProviderHealthSnapshot",
    "ProviderNetworkSettings",
    "ProviderOperationalStatus",
    "RateLimitPolicy",
    "RateLimitSnapshot",
    "build_collector_baseline",
    "create_collector_network_runtime",
    "default_collector_network_settings",
    "parse_retry_after",
    "sanitize_url",
]
