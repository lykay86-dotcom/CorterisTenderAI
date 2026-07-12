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
from app.tenders.collector.change_tracker import (
    TenderChange,
    TenderChangeSet,
    TenderChangeTracker,
    TenderChangeType,
)
from app.tenders.collector.checkpoint import CollectorCheckpoint
from app.tenders.collector.codec import (
    query_to_payload,
    stable_hash,
    stable_json,
    tender_from_payload,
    tender_to_payload,
)
from app.tenders.collector.collector_service import CollectorService
from app.tenders.collector.deduplicator import TenderDeduplicator
from app.tenders.collector.models import (
    CollectionPersistenceSummary,
    CollectionRunRecord,
    CollectionRunStatus,
    CollectorRunResult,
    CollectorSourceReference,
    DeduplicationGroup,
    DeduplicationMatchLevel,
    DeduplicationResult,
    NormalizedTender,
    TenderAliasType,
    TenderIdentityAlias,
    TenderObservationStatus,
)
from app.tenders.collector.normalizer import (
    TenderNormalizer,
    normalize_digits,
    normalize_identifier,
    normalize_text,
)
from app.tenders.collector.schema import (
    COLLECTOR_SCHEMA_VERSION,
    CollectorSchemaMigrator,
)
from app.tenders.collector.store import CollectorStateRepository
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
    "COLLECTOR_SCHEMA_VERSION",
    "CollectionPersistenceSummary",
    "CollectionRunRecord",
    "CollectionRunStatus",
    "CollectorCheckpoint",
    "CollectorRunResult",
    "CollectorSchemaMigrator",
    "CollectorService",
    "CollectorSourceReference",
    "CollectorStateRepository",
    "DeduplicationGroup",
    "DeduplicationMatchLevel",
    "DeduplicationResult",
    "NormalizedTender",
    "TenderAliasType",
    "TenderChange",
    "TenderChangeSet",
    "TenderChangeTracker",
    "TenderChangeType",
    "TenderDeduplicator",
    "TenderIdentityAlias",
    "TenderNormalizer",
    "TenderObservationStatus",
    "normalize_digits",
    "normalize_identifier",
    "normalize_text",
    "query_to_payload",
    "stable_hash",
    "stable_json",
    "tender_from_payload",
    "tender_to_payload",
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


from app.tenders.collector.provider_control import (
    CollectorProviderManager,
    ProviderCheckRecord,
    ProviderCheckRepository,
    ProviderDisplayState,
    ProviderUiState,
)
from app.tenders.collector.provider_settings import (
    ProviderEnablement,
    ProviderEnablementRepository,
)

__all__ += [
    "CollectorProviderManager",
    "ProviderCheckRecord",
    "ProviderCheckRepository",
    "ProviderDisplayState",
    "ProviderUiState",
    "ProviderEnablement",
    "ProviderEnablementRepository",
]

from app.tenders.collector.progress import (
    CollectorProgressCallback,
    CollectorProgressEvent,
    CollectorProgressPhase,
    emit_collector_progress,
)
from app.tenders.collector.run_session import CollectorRunSession

__all__ += [
    "CollectorProgressCallback",
    "CollectorProgressEvent",
    "CollectorProgressPhase",
    "CollectorRunSession",
    "emit_collector_progress",
]


from app.tenders.collector.notifications import (
    CollectorNotification,
    CollectorNotificationKind,
    CollectorNotificationRepository,
    CollectorNotificationService,
)
from app.tenders.collector.scheduler import (
    CollectorScheduleFrequency,
    CollectorScheduleRepository,
    CollectorScheduleSettings,
    CollectorScheduleState,
    CollectorScheduler,
    ScheduledCollectorRequest,
)

__all__ += [
    "CollectorNotification",
    "CollectorNotificationKind",
    "CollectorNotificationRepository",
    "CollectorNotificationService",
    "CollectorScheduleFrequency",
    "CollectorScheduleRepository",
    "CollectorScheduleSettings",
    "CollectorScheduleState",
    "CollectorScheduler",
    "ScheduledCollectorRequest",
]


from app.tenders.collector.participation_score import (
    CorterisCompanyProfile,
    CorterisParticipationRanker,
    CorterisParticipationScore,
    DEFAULT_CORTERIS_COMPANY_PROFILE,
    ParticipationRecommendation,
    ParticipationScoreComponent,
    ParticipationScoringContext,
)
from app.tenders.collector.participation_score_service import (
    CorterisParticipationScoreService,
)

__all__ += [
    "CorterisCompanyProfile",
    "CorterisParticipationRanker",
    "CorterisParticipationScore",
    "DEFAULT_CORTERIS_COMPANY_PROFILE",
    "ParticipationRecommendation",
    "ParticipationScoreComponent",
    "ParticipationScoringContext",
    "CorterisParticipationScoreService",
]
