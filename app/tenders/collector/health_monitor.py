"""Circuit-breaker and health state for tender providers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from threading import RLock
from time import monotonic
from typing import Callable


class ProviderOperationalStatus(StrEnum):
    UNKNOWN = "unknown"
    AVAILABLE = "available"
    DEGRADED = "degraded"
    COOLDOWN = "cooldown"
    UNAVAILABLE = "unavailable"
    NOT_CONFIGURED = "not_configured"
    DISABLED = "disabled"


class ProviderCircuitOpenError(RuntimeError):
    """Raised when a provider is temporarily blocked after failures."""


@dataclass(frozen=True, slots=True)
class ProviderHealthPolicy:
    failure_threshold: int = 3
    cooldown_seconds: float = 300.0
    unavailable_threshold: int = 8

    def __post_init__(self) -> None:
        if self.failure_threshold < 1:
            raise ValueError("failure_threshold must be at least 1")
        if self.cooldown_seconds < 0:
            raise ValueError("cooldown_seconds must be non-negative")
        if self.unavailable_threshold < self.failure_threshold:
            raise ValueError("unavailable_threshold cannot be below failure_threshold")


@dataclass(frozen=True, slots=True)
class ProviderHealthSnapshot:
    provider_id: str
    status: ProviderOperationalStatus
    checked_at: str
    last_success_at: str
    consecutive_failures: int
    total_successes: int
    total_failures: int
    average_latency_ms: int | None
    last_latency_ms: int | None
    last_error_type: str
    last_error_message: str
    last_status_code: int | None
    connection_mode: str
    parser_version: str
    cooldown_remaining_seconds: float
    disabled_by_user: bool


@dataclass(frozen=True, slots=True)
class ProviderHealthRestoreState:
    """Validated wall-clock state restored into the existing monotonic monitor."""

    provider_id: str
    status: ProviderOperationalStatus
    checked_at: str = ""
    last_success_at: str = ""
    consecutive_failures: int = 0
    total_successes: int = 0
    total_failures: int = 0
    last_error_type: str = ""
    last_error_message: str = ""
    cooldown_remaining_seconds: float = 0.0

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id must not be empty")
        if min(self.consecutive_failures, self.total_successes, self.total_failures) < 0:
            raise ValueError("health counters must be non-negative")
        if self.cooldown_remaining_seconds < 0:
            raise ValueError("cooldown remaining must be non-negative")


@dataclass(slots=True)
class _ProviderHealthState:
    provider_id: str
    status: ProviderOperationalStatus = ProviderOperationalStatus.UNKNOWN
    checked_at: str = ""
    last_success_at: str = ""
    consecutive_failures: int = 0
    total_successes: int = 0
    total_failures: int = 0
    total_latency_ms: int = 0
    latency_samples: int = 0
    last_latency_ms: int | None = None
    last_error_type: str = ""
    last_error_message: str = ""
    last_status_code: int | None = None
    connection_mode: str = ""
    parser_version: str = ""
    cooldown_until: float = 0.0
    disabled_by_user: bool = False


class ProviderHealthMonitor:
    """Track provider failures and open a temporary circuit when needed."""

    def __init__(
        self,
        *,
        default_policy: ProviderHealthPolicy | None = None,
        policies: dict[str, ProviderHealthPolicy] | None = None,
        clock: Callable[[], float] = monotonic,
        utcnow: Callable[[], datetime] | None = None,
    ) -> None:
        self.default_policy = default_policy or ProviderHealthPolicy()
        self._policies = {key.strip().casefold(): value for key, value in (policies or {}).items()}
        self._clock = clock
        self._utcnow = utcnow or (lambda: datetime.now(timezone.utc))
        self._states: dict[str, _ProviderHealthState] = {}
        self._lock = RLock()

    def policy_for(self, provider_id: str) -> ProviderHealthPolicy:
        normalized = self._normalize_id(provider_id)
        return self._policies.get(normalized, self.default_policy)

    def can_execute(self, provider_id: str) -> bool:
        with self._lock:
            state = self._state(provider_id)
            self._refresh_cooldown(state)
            return state.status not in {
                ProviderOperationalStatus.COOLDOWN,
                ProviderOperationalStatus.UNAVAILABLE,
                ProviderOperationalStatus.NOT_CONFIGURED,
                ProviderOperationalStatus.DISABLED,
            }

    def ensure_available(self, provider_id: str) -> None:
        if not self.can_execute(provider_id):
            snapshot = self.snapshot(provider_id)
            raise ProviderCircuitOpenError(
                f"Провайдер {provider_id} недоступен: {snapshot.status.value}"
            )

    def register_success(
        self,
        provider_id: str,
        *,
        latency_ms: int | None = None,
        connection_mode: str = "",
        parser_version: str = "",
    ) -> ProviderHealthSnapshot:
        if latency_ms is not None and latency_ms < 0:
            raise ValueError("latency_ms must be non-negative")
        with self._lock:
            state = self._state(provider_id)
            state.status = ProviderOperationalStatus.AVAILABLE
            state.checked_at = self._timestamp()
            state.last_success_at = state.checked_at
            state.consecutive_failures = 0
            state.total_successes += 1
            state.cooldown_until = 0.0
            state.last_error_type = ""
            state.last_error_message = ""
            state.last_status_code = None
            state.last_latency_ms = latency_ms
            if latency_ms is not None:
                state.total_latency_ms += latency_ms
                state.latency_samples += 1
            if connection_mode:
                state.connection_mode = connection_mode
            if parser_version:
                state.parser_version = parser_version
            return self._snapshot(state)

    def register_failure(
        self,
        provider_id: str,
        error: BaseException | str,
        *,
        latency_ms: int | None = None,
        status_code: int | None = None,
        connection_mode: str = "",
        parser_version: str = "",
    ) -> ProviderHealthSnapshot:
        if latency_ms is not None and latency_ms < 0:
            raise ValueError("latency_ms must be non-negative")
        with self._lock:
            state = self._state(provider_id)
            policy = self.policy_for(provider_id)
            state.checked_at = self._timestamp()
            state.consecutive_failures += 1
            state.total_failures += 1
            state.last_latency_ms = latency_ms
            if latency_ms is not None:
                state.total_latency_ms += latency_ms
                state.latency_samples += 1
            if isinstance(error, BaseException):
                state.last_error_type = type(error).__name__
                state.last_error_message = str(error)
            else:
                state.last_error_type = "ProviderError"
                state.last_error_message = str(error)
            state.last_status_code = status_code
            if connection_mode:
                state.connection_mode = connection_mode
            if parser_version:
                state.parser_version = parser_version

            if state.consecutive_failures >= policy.unavailable_threshold:
                state.status = ProviderOperationalStatus.UNAVAILABLE
                state.cooldown_until = self._clock() + policy.cooldown_seconds * 3
            elif state.consecutive_failures >= policy.failure_threshold:
                state.status = ProviderOperationalStatus.COOLDOWN
                state.cooldown_until = self._clock() + policy.cooldown_seconds
            else:
                state.status = ProviderOperationalStatus.DEGRADED
            return self._snapshot(state)

    def register_not_configured(
        self,
        provider_id: str,
        message: str,
    ) -> ProviderHealthSnapshot:
        with self._lock:
            state = self._state(provider_id)
            state.status = ProviderOperationalStatus.NOT_CONFIGURED
            state.checked_at = self._timestamp()
            state.last_error_type = "ProviderNotConfiguredError"
            state.last_error_message = message.strip()
            return self._snapshot(state)

    def set_disabled(
        self,
        provider_id: str,
        disabled: bool,
    ) -> ProviderHealthSnapshot:
        with self._lock:
            state = self._state(provider_id)
            state.disabled_by_user = bool(disabled)
            state.checked_at = self._timestamp()
            if disabled:
                state.status = ProviderOperationalStatus.DISABLED
            elif state.status == ProviderOperationalStatus.DISABLED:
                state.status = ProviderOperationalStatus.UNKNOWN
            return self._snapshot(state)

    def reset(self, provider_id: str) -> ProviderHealthSnapshot:
        with self._lock:
            normalized = self._normalize_id(provider_id)
            previous = self._states.get(normalized)
            parser_version = previous.parser_version if previous else ""
            connection_mode = previous.connection_mode if previous else ""
            state = _ProviderHealthState(
                provider_id=normalized,
                parser_version=parser_version,
                connection_mode=connection_mode,
            )
            self._states[normalized] = state
            return self._snapshot(state)

    def snapshot(self, provider_id: str) -> ProviderHealthSnapshot:
        with self._lock:
            state = self._state(provider_id)
            self._refresh_cooldown(state)
            return self._snapshot(state)

    def snapshots(self) -> tuple[ProviderHealthSnapshot, ...]:
        with self._lock:
            for state in self._states.values():
                self._refresh_cooldown(state)
            return tuple(self._snapshot(self._states[key]) for key in sorted(self._states))

    def restore(self, value: ProviderHealthRestoreState) -> ProviderHealthSnapshot:
        """Replace one state from validated persisted evidence without network activity."""

        if not isinstance(value, ProviderHealthRestoreState):
            raise TypeError("value must be ProviderHealthRestoreState")
        normalized = self._normalize_id(value.provider_id)
        with self._lock:
            state = _ProviderHealthState(
                provider_id=normalized,
                status=value.status,
                checked_at=value.checked_at,
                last_success_at=value.last_success_at,
                consecutive_failures=value.consecutive_failures,
                total_successes=value.total_successes,
                total_failures=value.total_failures,
                last_error_type=value.last_error_type,
                last_error_message=value.last_error_message,
                cooldown_until=(
                    self._clock() + value.cooldown_remaining_seconds
                    if value.cooldown_remaining_seconds > 0
                    else 0.0
                ),
                disabled_by_user=value.status is ProviderOperationalStatus.DISABLED,
            )
            self._states[normalized] = state
            self._refresh_cooldown(state)
            return self._snapshot(state)

    def _state(self, provider_id: str) -> _ProviderHealthState:
        normalized = self._normalize_id(provider_id)
        state = self._states.get(normalized)
        if state is None:
            state = _ProviderHealthState(provider_id=normalized)
            self._states[normalized] = state
        return state

    def _refresh_cooldown(self, state: _ProviderHealthState) -> None:
        if (
            state.status
            in {
                ProviderOperationalStatus.COOLDOWN,
                ProviderOperationalStatus.UNAVAILABLE,
            }
            and state.cooldown_until > 0
            and self._clock() >= state.cooldown_until
        ):
            state.status = ProviderOperationalStatus.DEGRADED
            state.cooldown_until = 0.0

    def _snapshot(
        self,
        state: _ProviderHealthState,
    ) -> ProviderHealthSnapshot:
        average = None
        if state.latency_samples:
            average = round(state.total_latency_ms / state.latency_samples)
        return ProviderHealthSnapshot(
            provider_id=state.provider_id,
            status=state.status,
            checked_at=state.checked_at,
            last_success_at=state.last_success_at,
            consecutive_failures=state.consecutive_failures,
            total_successes=state.total_successes,
            total_failures=state.total_failures,
            average_latency_ms=average,
            last_latency_ms=state.last_latency_ms,
            last_error_type=state.last_error_type,
            last_error_message=state.last_error_message,
            last_status_code=state.last_status_code,
            connection_mode=state.connection_mode,
            parser_version=state.parser_version,
            cooldown_remaining_seconds=max(
                0.0,
                state.cooldown_until - self._clock(),
            ),
            disabled_by_user=state.disabled_by_user,
        )

    def _timestamp(self) -> str:
        return self._utcnow().isoformat(timespec="seconds")

    @staticmethod
    def _normalize_id(provider_id: str) -> str:
        normalized = provider_id.strip().casefold()
        if not normalized:
            raise ValueError("provider_id must not be empty")
        return normalized


__all__ = [
    "ProviderCircuitOpenError",
    "ProviderHealthMonitor",
    "ProviderHealthPolicy",
    "ProviderHealthRestoreState",
    "ProviderHealthSnapshot",
    "ProviderOperationalStatus",
]
