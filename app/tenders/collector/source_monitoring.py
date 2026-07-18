"""Deterministic read-only projection of existing tender source state."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from threading import RLock

from app.tenders.collector.checkpoint import CollectorCheckpoint
from app.tenders.collector.health_monitor import (
    ProviderHealthMonitor,
    ProviderHealthPolicy,
    ProviderHealthRestoreState,
    ProviderOperationalStatus,
)
from app.tenders.collector.models import ProviderRunOutcomeRecord
from app.tenders.collector.network_settings import default_collector_network_settings
from app.tenders.collector.provider_control import (
    ProviderCheckRepository,
    ProviderDisplayState,
    ProviderUiState,
)
from app.tenders.collector.scheduler import (
    CollectorScheduleFrequency,
    CollectorScheduleRepository,
    CollectorScheduleSettings,
)
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.collector.vertical_source_verification import (
    VerticalSourceStatus,
    VerticalSourceVerificationRepository,
)


class SourceFreshness(StrEnum):
    CURRENT = "current"
    STALE = "stale"
    UNKNOWN = "unknown"
    INVALID = "invalid"
    NOT_APPLICABLE = "not_applicable"


class SourceAttentionLevel(StrEnum):
    NONE = "none"
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class SourceConnectionStatus(StrEnum):
    UNKNOWN = "unknown"
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    NOT_CONFIGURED = "not_configured"


class SourceOperationalStatus(StrEnum):
    UNKNOWN = "unknown"
    AVAILABLE = "available"
    DEGRADED = "degraded"
    COOLDOWN = "cooldown"
    UNAVAILABLE = "unavailable"
    NOT_CONFIGURED = "not_configured"
    DISABLED = "disabled"


class SourceMonitoringTransitionKind(StrEnum):
    OPERATIONAL_DEGRADED = "operational_degraded"
    OPERATIONAL_RECOVERED = "operational_recovered"
    CHECKPOINT_STALE = "checkpoint_stale"
    VERIFICATION_LOST = "verification_lost"
    EVIDENCE_INVALID = "evidence_invalid"


@dataclass(frozen=True, slots=True)
class SourceMonitoringPolicy:
    policy_version: str = "source-monitoring-v1"
    connection_ttl: timedelta = timedelta(hours=24)
    inactive_checkpoint_ttl: timedelta = timedelta(hours=24)
    verification_ttl: timedelta = timedelta(days=30)
    max_future_skew: timedelta = timedelta(minutes=5)
    minimum_checkpoint_ttl: timedelta = timedelta(hours=1)
    maximum_checkpoint_ttl: timedelta = timedelta(hours=48)

    def __post_init__(self) -> None:
        values = (
            self.connection_ttl,
            self.inactive_checkpoint_ttl,
            self.verification_ttl,
            self.max_future_skew,
            self.minimum_checkpoint_ttl,
            self.maximum_checkpoint_ttl,
        )
        if not self.policy_version.strip() or any(value < timedelta(0) for value in values):
            raise ValueError("source monitoring policy values must be non-negative")


@dataclass(frozen=True, slots=True)
class SourceReason:
    code: str
    message: str
    level: SourceAttentionLevel


@dataclass(frozen=True, slots=True)
class SourceReadiness:
    enabled: bool
    runnable: bool
    configured: bool


@dataclass(frozen=True, slots=True)
class SourceConnectionState:
    status: SourceConnectionStatus
    checked_at: datetime | None
    last_success_at: datetime | None
    freshness: SourceFreshness


@dataclass(frozen=True, slots=True)
class SourceOperationalState:
    status: SourceOperationalStatus
    last_run_id: str = ""
    observed_at: datetime | None = None
    last_success_at: datetime | None = None
    consecutive_failures: int = 0
    cooldown_until: datetime | None = None
    cooldown_remaining_seconds: float = 0.0
    reason_code: str = ""
    reason_message: str = ""


@dataclass(frozen=True, slots=True)
class SourceCheckpointState:
    supported: bool
    present: bool
    scope_key: str = ""
    cursor_present: bool = False
    watermark: str = ""
    updated_at: datetime | None = None
    freshness: SourceFreshness = SourceFreshness.UNKNOWN


@dataclass(frozen=True, slots=True)
class SourceVerificationState:
    status: VerticalSourceStatus
    verification_id: str = ""
    observed_at: datetime | None = None
    qualifies_as_working: bool = False
    freshness: SourceFreshness = SourceFreshness.UNKNOWN


@dataclass(frozen=True, slots=True)
class SourceScheduleState:
    active: bool
    next_due_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class SourceMonitoringState:
    provider_id: str
    display_name: str
    readiness: SourceReadiness
    connection: SourceConnectionState
    operational: SourceOperationalState
    checkpoint: SourceCheckpointState
    verification: SourceVerificationState
    schedule: SourceScheduleState
    attention: SourceAttentionLevel
    reasons: tuple[SourceReason, ...]
    last_successful_collection_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class SourceMonitoringSnapshot:
    observed_at: datetime
    revision: int
    policy_version: str
    sources: tuple[SourceMonitoringState, ...]


@dataclass(frozen=True, slots=True)
class SourceMonitoringTransition:
    provider_id: str
    kind: SourceMonitoringTransitionKind
    evidence_id: str
    observed_at: datetime

    def __post_init__(self) -> None:
        if not self.provider_id.strip() or not self.evidence_id.strip():
            raise ValueError("monitoring transition identity is required")
        if self.observed_at.tzinfo is None:
            raise ValueError("monitoring transition time must be aware")


def parse_aware_utc(value: str) -> datetime | None:
    if not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def classify_freshness(
    value: str,
    observed_at: datetime,
    ttl: timedelta,
    *,
    max_future_skew: timedelta = timedelta(minutes=5),
) -> SourceFreshness:
    observed = _aware_utc(observed_at)
    parsed = parse_aware_utc(value)
    if parsed is None:
        return SourceFreshness.INVALID if value.strip() else SourceFreshness.UNKNOWN
    if parsed > observed + max_future_skew:
        return SourceFreshness.INVALID
    return SourceFreshness.CURRENT if observed - parsed < ttl else SourceFreshness.STALE


def hydrate_health_monitor(
    monitor: ProviderHealthMonitor,
    records: Sequence[ProviderRunOutcomeRecord],
    *,
    observed_at: datetime | None = None,
) -> None:
    """Hydrate the existing monitor from compatible accepted run evidence."""

    observed = _aware_utc(observed_at or datetime.now(timezone.utc))
    grouped: dict[str, list[ProviderRunOutcomeRecord]] = defaultdict(list)
    for record in records:
        if parse_aware_utc(record.completed_at) is not None:
            grouped[record.provider_id.strip().casefold()].append(record)
    for provider_id, provider_records in grouped.items():
        state = _operational_from_records(
            provider_records,
            observed,
            monitor.policy_for(provider_id),
        )
        monitor.restore(
            ProviderHealthRestoreState(
                provider_id=provider_id,
                status=ProviderOperationalStatus(state.status.value),
                checked_at=state.observed_at.isoformat(timespec="seconds")
                if state.observed_at
                else "",
                last_success_at=state.last_success_at.isoformat(timespec="seconds")
                if state.last_success_at
                else "",
                consecutive_failures=state.consecutive_failures,
                total_successes=sum(item.status in _SUCCESS for item in provider_records),
                total_failures=sum(item.status in _REMOTE_FAILURE for item in provider_records),
                last_error_type=state.reason_code,
                last_error_message=state.reason_message,
                cooldown_remaining_seconds=state.cooldown_remaining_seconds,
            )
        )


class SourceMonitoringService:
    """Aggregate existing facts without writing state or starting network work."""

    def __init__(
        self,
        *,
        state_repository: CollectorStateRepository,
        schedule_repository: CollectorScheduleRepository,
        verification_repository: VerticalSourceVerificationRepository,
        check_repository: ProviderCheckRepository | None = None,
        policy: SourceMonitoringPolicy | None = None,
        health_policies: Mapping[str, ProviderHealthPolicy] | None = None,
    ) -> None:
        self.state_repository = state_repository
        self.schedule_repository = schedule_repository
        self.verification_repository = verification_repository
        self.check_repository = check_repository
        self.policy = policy or SourceMonitoringPolicy()
        self._health_policies = dict(
            health_policies or default_collector_network_settings().health_policies
        )
        self._default_health_policy = ProviderHealthPolicy()
        self._revision = 0
        self._lock = RLock()

    def snapshot(
        self,
        provider_states: Iterable[ProviderDisplayState],
        *,
        observed_at: datetime | None = None,
    ) -> SourceMonitoringSnapshot:
        observed = _aware_utc(observed_at or datetime.now(timezone.utc))
        states = tuple(sorted(provider_states, key=lambda item: item.provider_id.casefold()))
        outcomes = self.state_repository.list_provider_outcomes(limit=1000)
        outcome_map: dict[str, list[ProviderRunOutcomeRecord]] = defaultdict(list)
        for outcome in outcomes:
            outcome_map[outcome.provider_id].append(outcome)
        checkpoint_map: dict[str, list[CollectorCheckpoint]] = defaultdict(list)
        for checkpoint in self.state_repository.list_checkpoints():
            checkpoint_map[checkpoint.provider_id].append(checkpoint)
        schedule_settings, schedule_state = self.schedule_repository.load()
        sources = tuple(
            self._source(
                state,
                outcome_map.get(state.provider_id, ()),
                checkpoint_map.get(state.provider_id, ()),
                schedule_settings,
                schedule_state.next_run_at,
                observed,
            )
            for state in states
        )
        with self._lock:
            self._revision += 1
            revision = self._revision
        return SourceMonitoringSnapshot(
            observed_at=observed,
            revision=revision,
            policy_version=self.policy.policy_version,
            sources=sources,
        )

    def _source(
        self,
        state: ProviderDisplayState,
        outcomes: Sequence[ProviderRunOutcomeRecord],
        checkpoints: Sequence[CollectorCheckpoint],
        settings: CollectorScheduleSettings,
        next_run_at: str,
        observed: datetime,
    ) -> SourceMonitoringState:
        readiness = SourceReadiness(
            enabled=state.enabled,
            runnable=state.runnable,
            configured=state.protocol_configured and state.adapter_compiled,
        )
        connection = self._connection(state, observed)
        operational = _operational_from_records(
            outcomes,
            observed,
            self._health_policies.get(state.provider_id, self._default_health_policy),
        )
        if not readiness.enabled:
            operational = SourceOperationalState(SourceOperationalStatus.DISABLED)
        active = settings.enabled and state.provider_id in settings.provider_ids
        schedule = SourceScheduleState(
            active=active,
            next_due_at=parse_aware_utc(next_run_at) if active else None,
        )
        checkpoint = self._checkpoint(state, checkpoints, settings, active, observed)
        verification = self._verification(state.provider_id, observed)
        reasons = _attention_reasons(readiness, connection, operational, checkpoint, verification)
        attention = max(
            (reason.level for reason in reasons),
            key=_attention_rank,
            default=SourceAttentionLevel.NONE,
        )
        return SourceMonitoringState(
            provider_id=state.provider_id.strip().casefold(),
            display_name=state.display_name,
            readiness=readiness,
            connection=connection,
            operational=operational,
            checkpoint=checkpoint,
            verification=verification,
            schedule=schedule,
            attention=attention,
            reasons=reasons,
            last_successful_collection_at=operational.last_success_at,
        )

    def _connection(
        self,
        state: ProviderDisplayState,
        observed: datetime,
    ) -> SourceConnectionState:
        record = (
            self.check_repository.load().get(state.provider_id) if self.check_repository else None
        )
        manual = (
            self.check_repository.manual_evidence(state.provider_id)
            if self.check_repository and state.registration_only
            else None
        )
        if manual is not None:
            checked = _aware_datetime(manual.checked_at)
            valid_until = _aware_datetime(manual.valid_until)
            freshness = (
                SourceFreshness.INVALID
                if checked is None
                or valid_until is None
                or valid_until > observed + timedelta(days=1)
                else SourceFreshness.CURRENT
                if observed < valid_until
                else SourceFreshness.STALE
            )
            status = SourceConnectionStatus.AVAILABLE
            return SourceConnectionState(
                status, checked, checked if status.value == "available" else None, freshness
            )
        if record is not None:
            status = SourceConnectionStatus(record.status.value)
            freshness = classify_freshness(
                record.checked_at,
                observed,
                self.policy.connection_ttl,
                max_future_skew=self.policy.max_future_skew,
            )
            return SourceConnectionState(
                status,
                parse_aware_utc(record.checked_at),
                parse_aware_utc(record.last_success_at),
                freshness,
            )
        status = {
            ProviderUiState.WORKING: SourceConnectionStatus.AVAILABLE,
            ProviderUiState.UNVERIFIED: SourceConnectionStatus.AVAILABLE,
            ProviderUiState.LIMITED: SourceConnectionStatus.DEGRADED,
            ProviderUiState.ERROR: SourceConnectionStatus.UNAVAILABLE,
            ProviderUiState.NOT_CONFIGURED: SourceConnectionStatus.NOT_CONFIGURED,
        }.get(state.ui_state, SourceConnectionStatus.UNKNOWN)
        return SourceConnectionState(
            status,
            parse_aware_utc(state.last_checked_at),
            parse_aware_utc(state.last_success_at),
            classify_freshness(
                state.last_checked_at,
                observed,
                self.policy.connection_ttl,
                max_future_skew=self.policy.max_future_skew,
            ),
        )

    def _checkpoint(
        self,
        state: ProviderDisplayState,
        values: Sequence[CollectorCheckpoint],
        settings: CollectorScheduleSettings,
        active: bool,
        observed: datetime,
    ) -> SourceCheckpointState:
        if not state.checkpoint_supported:
            return SourceCheckpointState(False, False, freshness=SourceFreshness.NOT_APPLICABLE)
        latest = max(
            values,
            key=lambda item: (
                parse_aware_utc(item.updated_at) or datetime.min.replace(tzinfo=timezone.utc)
            ),
            default=None,
        )
        if latest is None:
            return SourceCheckpointState(True, False)
        ttl = _checkpoint_ttl(settings, active, self.policy)
        return SourceCheckpointState(
            supported=True,
            present=True,
            scope_key=latest.scope_key,
            cursor_present=bool(latest.cursor),
            watermark=latest.watermark,
            updated_at=parse_aware_utc(latest.updated_at),
            freshness=classify_freshness(
                latest.updated_at,
                observed,
                ttl,
                max_future_skew=self.policy.max_future_skew,
            ),
        )

    def _verification(self, provider_id: str, observed: datetime) -> SourceVerificationState:
        value = self.verification_repository.latest(provider_id)
        if value is None:
            return SourceVerificationState(VerticalSourceStatus.UNVERIFIED)
        freshness = classify_freshness(
            value.completed_at,
            observed,
            self.policy.verification_ttl,
            max_future_skew=self.policy.max_future_skew,
        )
        qualifies = bool(
            value.status is VerticalSourceStatus.WORKING
            and value.qualifies_as_working
            and freshness is SourceFreshness.CURRENT
        )
        return SourceVerificationState(
            status=value.status,
            verification_id=value.verification_id,
            observed_at=parse_aware_utc(value.completed_at),
            qualifies_as_working=qualifies,
            freshness=freshness,
        )


_SUCCESS = frozenset({"success", "empty"})
_REMOTE_FAILURE = frozenset({"failed", "timed_out"})
_NEUTRAL = frozenset({"cancelled", "unsupported", "skipped", "circuit_open"})


def _operational_from_records(
    values: Sequence[ProviderRunOutcomeRecord],
    observed: datetime,
    policy: ProviderHealthPolicy,
) -> SourceOperationalState:
    ordered = sorted(
        (item for item in values if parse_aware_utc(item.completed_at) is not None),
        key=lambda item: (parse_aware_utc(item.completed_at), item.run_id),
        reverse=True,
    )
    if not ordered:
        return SourceOperationalState(SourceOperationalStatus.UNKNOWN)
    meaningful = next((item for item in ordered if item.status not in _NEUTRAL), None)
    if meaningful is None:
        return SourceOperationalState(SourceOperationalStatus.UNKNOWN)
    last_success_record = next((item for item in ordered if item.status in _SUCCESS), None)
    last_success = (
        parse_aware_utc(last_success_record.completed_at) if last_success_record else None
    )
    consecutive = 0
    for item in ordered:
        if item.status in _NEUTRAL:
            continue
        if item.status in _REMOTE_FAILURE:
            consecutive += 1
            continue
        break
    completed = parse_aware_utc(meaningful.completed_at)
    if meaningful.status in _SUCCESS:
        status = SourceOperationalStatus.AVAILABLE
    elif meaningful.status == "not_configured":
        status = SourceOperationalStatus.NOT_CONFIGURED
    elif meaningful.status in _REMOTE_FAILURE:
        if consecutive >= policy.unavailable_threshold:
            status = SourceOperationalStatus.UNAVAILABLE
            duration = policy.cooldown_seconds * 3
        elif consecutive >= policy.failure_threshold:
            status = SourceOperationalStatus.COOLDOWN
            duration = policy.cooldown_seconds
        else:
            status = SourceOperationalStatus.DEGRADED
            duration = 0.0
        cooldown_until = completed + timedelta(seconds=duration) if completed and duration else None
        remaining = max(0.0, (cooldown_until - observed).total_seconds()) if cooldown_until else 0.0
        maximum = max(0.0, policy.cooldown_seconds * 3)
        remaining = min(remaining, maximum)
        if (
            status in {SourceOperationalStatus.COOLDOWN, SourceOperationalStatus.UNAVAILABLE}
            and not remaining
        ):
            status = SourceOperationalStatus.DEGRADED
        return SourceOperationalState(
            status=status,
            last_run_id=meaningful.run_id,
            observed_at=completed,
            last_success_at=last_success,
            consecutive_failures=consecutive,
            cooldown_until=cooldown_until,
            cooldown_remaining_seconds=remaining,
            reason_code=_safe_code(meaningful.error_code),
            reason_message="Источник завершил сбор с безопасно скрытой ошибкой.",
        )
    else:
        status = SourceOperationalStatus.UNKNOWN
    return SourceOperationalState(
        status=status,
        last_run_id=meaningful.run_id,
        observed_at=completed,
        last_success_at=last_success,
        consecutive_failures=consecutive,
    )


def monitoring_transitions(
    previous: SourceMonitoringSnapshot,
    current: SourceMonitoringSnapshot,
) -> tuple[SourceMonitoringTransition, ...]:
    before = {item.provider_id: item for item in previous.sources}
    result: list[SourceMonitoringTransition] = []
    degraded = {
        SourceOperationalStatus.DEGRADED,
        SourceOperationalStatus.COOLDOWN,
        SourceOperationalStatus.UNAVAILABLE,
    }
    for source in current.sources:
        old = before.get(source.provider_id)
        if old is None:
            continue
        if (
            old.operational.status is SourceOperationalStatus.AVAILABLE
            and source.operational.status in degraded
        ):
            result.append(
                SourceMonitoringTransition(
                    source.provider_id,
                    SourceMonitoringTransitionKind.OPERATIONAL_DEGRADED,
                    f"{source.operational.last_run_id}:{source.operational.status.value}",
                    current.observed_at,
                )
            )
        elif (
            old.operational.status in degraded
            and source.operational.status is SourceOperationalStatus.AVAILABLE
        ):
            result.append(
                SourceMonitoringTransition(
                    source.provider_id,
                    SourceMonitoringTransitionKind.OPERATIONAL_RECOVERED,
                    f"{source.operational.last_run_id}:available",
                    current.observed_at,
                )
            )
        if (
            old.checkpoint.freshness is SourceFreshness.CURRENT
            and source.checkpoint.freshness is SourceFreshness.STALE
        ):
            result.append(
                SourceMonitoringTransition(
                    source.provider_id,
                    SourceMonitoringTransitionKind.CHECKPOINT_STALE,
                    (
                        f"{source.provider_id}:{source.checkpoint.scope_key}:"
                        f"{source.checkpoint.updated_at}"
                    ),
                    current.observed_at,
                )
            )
        if old.verification.qualifies_as_working and not source.verification.qualifies_as_working:
            result.append(
                SourceMonitoringTransition(
                    source.provider_id,
                    SourceMonitoringTransitionKind.VERIFICATION_LOST,
                    (f"{source.verification.verification_id}:{source.verification.status.value}"),
                    current.observed_at,
                )
            )
        if _has_invalid(source) and not _has_invalid(old):
            result.append(
                SourceMonitoringTransition(
                    source.provider_id,
                    SourceMonitoringTransitionKind.EVIDENCE_INVALID,
                    (
                        f"{source.provider_id}:{source.connection.status.value}:"
                        f"{source.operational.last_run_id}:{source.checkpoint.scope_key}:"
                        f"{source.verification.verification_id}"
                    ),
                    current.observed_at,
                )
            )
    return tuple(result)


def _attention_reasons(
    readiness: SourceReadiness,
    connection: SourceConnectionState,
    operational: SourceOperationalState,
    checkpoint: SourceCheckpointState,
    verification: SourceVerificationState,
) -> tuple[SourceReason, ...]:
    result: list[SourceReason] = []
    if SourceFreshness.INVALID in {
        connection.freshness,
        checkpoint.freshness,
        verification.freshness,
    }:
        result.append(
            SourceReason(
                "invalid_evidence_time",
                "Время наблюдения некорректно.",
                SourceAttentionLevel.CRITICAL,
            )
        )
    if not readiness.enabled:
        result.append(
            SourceReason(
                "source_disabled", "Источник отключён пользователем.", SourceAttentionLevel.INFO
            )
        )
    elif not readiness.configured or not readiness.runnable:
        result.append(
            SourceReason(
                "source_not_runnable",
                "Источник пока не готов к запуску.",
                SourceAttentionLevel.WARNING,
            )
        )
    if operational.status is SourceOperationalStatus.UNAVAILABLE:
        result.append(
            SourceReason(
                "operational_unavailable",
                "Источник недоступен после повторных ошибок.",
                SourceAttentionLevel.CRITICAL,
            )
        )
    elif operational.status in {SourceOperationalStatus.DEGRADED, SourceOperationalStatus.COOLDOWN}:
        result.append(
            SourceReason(
                "operational_degraded",
                "Сбор из источника требует внимания.",
                SourceAttentionLevel.WARNING,
            )
        )
    if (
        connection.status is SourceConnectionStatus.UNAVAILABLE
        or connection.freshness is SourceFreshness.STALE
    ):
        result.append(
            SourceReason(
                "connection_attention",
                "Проверка подключения требует обновления.",
                SourceAttentionLevel.WARNING,
            )
        )
    if checkpoint.freshness is SourceFreshness.STALE:
        result.append(
            SourceReason(
                "checkpoint_stale", "Checkpoint источника устарел.", SourceAttentionLevel.WARNING
            )
        )
    if (
        verification.status is VerticalSourceStatus.FAILED
        or verification.freshness is SourceFreshness.STALE
    ):
        result.append(
            SourceReason(
                "c19_attention",
                "Полная проверка C19 требует внимания.",
                SourceAttentionLevel.WARNING,
            )
        )
    elif verification.status is VerticalSourceStatus.UNVERIFIED:
        result.append(
            SourceReason(
                "c19_unverified", "Полная проверка C19 ещё не выполнена.", SourceAttentionLevel.INFO
            )
        )
    return tuple(sorted(result, key=lambda item: (-_attention_rank(item.level), item.code)))


def _checkpoint_ttl(
    settings: CollectorScheduleSettings,
    active: bool,
    policy: SourceMonitoringPolicy,
) -> timedelta:
    if not active:
        return policy.inactive_checkpoint_ttl
    interval = {
        CollectorScheduleFrequency.EVERY_30_MINUTES: timedelta(minutes=30),
        CollectorScheduleFrequency.HOURLY: timedelta(hours=1),
        CollectorScheduleFrequency.EVERY_3_HOURS: timedelta(hours=3),
        CollectorScheduleFrequency.DAILY: timedelta(days=1),
    }[settings.frequency]
    candidate = interval * 2 + timedelta(minutes=5)
    return min(policy.maximum_checkpoint_ttl, max(policy.minimum_checkpoint_ttl, candidate))


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("monitoring time must be timezone-aware")
    return value.astimezone(timezone.utc)


def _aware_datetime(value: datetime) -> datetime | None:
    if value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _safe_code(value: str) -> str:
    normalized = value.strip().casefold()
    if (
        normalized
        and len(normalized) <= 64
        and all(char.isalnum() or char in "_-" for char in normalized)
    ):
        return normalized
    return "provider_error"


def _attention_rank(value: SourceAttentionLevel) -> int:
    return {
        SourceAttentionLevel.NONE: 0,
        SourceAttentionLevel.INFO: 1,
        SourceAttentionLevel.WARNING: 2,
        SourceAttentionLevel.CRITICAL: 3,
    }[value]


def _has_invalid(value: SourceMonitoringState) -> bool:
    return SourceFreshness.INVALID in {
        value.connection.freshness,
        value.checkpoint.freshness,
        value.verification.freshness,
    }


__all__ = [
    "SourceAttentionLevel",
    "SourceConnectionState",
    "SourceConnectionStatus",
    "SourceFreshness",
    "SourceMonitoringPolicy",
    "SourceMonitoringService",
    "SourceMonitoringSnapshot",
    "SourceMonitoringState",
    "SourceMonitoringTransition",
    "SourceMonitoringTransitionKind",
    "SourceOperationalState",
    "SourceOperationalStatus",
    "classify_freshness",
    "hydrate_health_monitor",
    "monitoring_transitions",
    "parse_aware_utc",
]
