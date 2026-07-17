"""Revision-bound one-shot health contracts for manual tender providers.

The module is deliberately independent from Qt, sockets, keyring and Collector
persistence.  It owns the immutable result/evidence vocabulary and the pure
admission decision used by every runtime entry point.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
import hashlib
import inspect
import json
import time
from typing import Any

from app.tenders.collector.cancellation import CollectorCancellationToken


MANUAL_HEALTH_CONTRACT_VERSION = 1
MANUAL_HEALTH_TTL = timedelta(minutes=15)
TARGET_POLICY_VERSION = "manual-target-policy-v1"
TRANSPORT_POLICY_VERSION = "manual-probe-transport-v1"
_MAX_SAFE_MESSAGE = 240


class ManualHealthStage(StrEnum):
    PRECONDITIONS = "preconditions"
    TARGET_POLICY = "target_policy"
    CREDENTIAL_AVAILABILITY = "credential_availability"
    DNS_RESOLUTION = "dns_resolution"
    CONNECT = "connect"
    TLS = "tls"
    AUTHENTICATION = "authentication"
    PROTOCOL = "protocol"
    PAYLOAD_COMPATIBILITY = "payload_compatibility"
    MAPPING_COMPATIBILITY = "mapping_compatibility"
    FINALIZE = "finalize"


class ManualHealthOutcome(StrEnum):
    PASSED = "passed"
    DEGRADED = "degraded"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class ManualHealthState(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ManualHealthReasonCode(StrEnum):
    OK = "ok"
    CANCELLED = "cancelled"
    ALREADY_RUNNING = "already_running"
    RATE_LIMITED = "rate_limited"
    INVALID_CONFIGURATION = "invalid_configuration"
    TARGET_BLOCKED = "target_blocked"
    CREDENTIAL_MISSING = "credential_missing"
    DNS_BLOCKED = "dns_blocked"
    CONNECT_FAILED = "connect_failed"
    TLS_FAILED = "tls_failed"
    AUTHENTICATION_FAILED = "authentication_failed"
    PROTOCOL_ERROR = "protocol_error"
    PAYLOAD_INCOMPATIBLE = "payload_incompatible"
    MAPPING_INCOMPATIBLE = "mapping_incompatible"
    INSUFFICIENT_SAMPLE = "insufficient_sample"
    PLAINTEXT_TRANSPORT = "plaintext_transport"
    STALE_COMPLETION = "stale_completion"
    OPERATION_FAILED_SAFE = "operation_failed_safe"


_SAFE_REASON_MESSAGES = {
    ManualHealthReasonCode.OK: "Предварительные условия выполнены.",
    ManualHealthReasonCode.CANCELLED: "Проверка отменена пользователем.",
    ManualHealthReasonCode.ALREADY_RUNNING: "Проверка этого источника уже выполняется.",
    ManualHealthReasonCode.RATE_LIMITED: "Повторите проверку через несколько секунд.",
    ManualHealthReasonCode.INVALID_CONFIGURATION: "Настройка источника неполна.",
    ManualHealthReasonCode.TARGET_BLOCKED: "Endpoint отклонён политикой безопасности.",
    ManualHealthReasonCode.CREDENTIAL_MISSING: "Требуемый credential не настроен.",
    ManualHealthReasonCode.DNS_BLOCKED: "DNS-ответ отклонён политикой безопасности.",
    ManualHealthReasonCode.CONNECT_FAILED: "Безопасное соединение не установлено.",
    ManualHealthReasonCode.TLS_FAILED: "Проверка TLS не пройдена.",
    ManualHealthReasonCode.AUTHENTICATION_FAILED: "Аутентификация не пройдена.",
    ManualHealthReasonCode.PROTOCOL_ERROR: "Протокол источника вернул безопасную ошибку.",
    ManualHealthReasonCode.PAYLOAD_INCOMPATIBLE: "Формат ответа не соответствует настройке.",
    ManualHealthReasonCode.MAPPING_INCOMPATIBLE: "Mapping ответа не подтверждён.",
    ManualHealthReasonCode.INSUFFICIENT_SAMPLE: "Недостаточно данных для подтверждения.",
    ManualHealthReasonCode.PLAINTEXT_TRANSPORT: "Plaintext FTP не создаёт healthy evidence.",
    ManualHealthReasonCode.STALE_COMPLETION: "Настройка изменилась во время проверки.",
    ManualHealthReasonCode.OPERATION_FAILED_SAFE: "Проверка завершилась безопасной ошибкой.",
}


@dataclass(frozen=True, slots=True)
class HealthCheckBinding:
    provider_id: str
    protocol_fingerprint: str
    adapter_spec_version: int
    adapter_revision: int
    adapter_fingerprint: str
    credential_marker: str
    target_policy_version: str = TARGET_POLICY_VERSION
    transport_policy_version: str = TRANSPORT_POLICY_VERSION
    contract_version: int = MANUAL_HEALTH_CONTRACT_VERSION

    def __post_init__(self) -> None:
        provider_id = _manual_provider_id(self.provider_id)
        if self.adapter_spec_version < 1 or self.adapter_revision < 1:
            raise ValueError("manual health binding is invalid")
        for value in (
            self.protocol_fingerprint,
            self.adapter_fingerprint,
            self.credential_marker,
            self.target_policy_version,
            self.transport_policy_version,
        ):
            if not isinstance(value, str) or not value or len(value) > 128:
                raise ValueError("manual health binding is invalid")
        if self.contract_version != MANUAL_HEALTH_CONTRACT_VERSION:
            raise ValueError("manual health binding contract is unsupported")
        object.__setattr__(self, "provider_id", provider_id)

    def public_payload(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "protocol_fingerprint": self.protocol_fingerprint,
            "adapter_spec_version": self.adapter_spec_version,
            "adapter_revision": self.adapter_revision,
            "adapter_fingerprint": self.adapter_fingerprint,
            "credential_marker": self.credential_marker,
            "target_policy_version": self.target_policy_version,
            "transport_policy_version": self.transport_policy_version,
            "contract_version": self.contract_version,
        }


@dataclass(frozen=True, slots=True)
class ManualHealthStageResult:
    stage: ManualHealthStage
    health: ManualHealthState
    reason_code: ManualHealthReasonCode
    message: str

    def __post_init__(self) -> None:
        _safe_message(self.message)
        if self.message != safe_manual_health_message(self.reason_code):
            raise ValueError("manual health message must use the safe reason catalog")

    def public_payload(self) -> dict[str, str]:
        return {
            "stage": self.stage.value,
            "health": self.health.value,
            "reason_code": self.reason_code.value,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class ManualHealthCheckResult:
    check_id: str
    binding: HealthCheckBinding
    outcome: ManualHealthOutcome
    health: ManualHealthState
    reason_code: ManualHealthReasonCode
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    stages: tuple[ManualHealthStageResult, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.check_id, str) or not self.check_id or len(self.check_id) > 128:
            raise ValueError("manual health check id is invalid")
        _aware(self.started_at)
        _aware(self.finished_at)
        if self.finished_at < self.started_at or self.duration_ms < 0:
            raise ValueError("manual health check timing is invalid")
        order = {stage: index for index, stage in enumerate(ManualHealthStage)}
        positions = [order[item.stage] for item in self.stages]
        if positions != sorted(set(positions)):
            raise ValueError("manual health stages are invalid")

    @property
    def creates_evidence(self) -> bool:
        return (
            self.outcome is ManualHealthOutcome.PASSED and self.health is ManualHealthState.HEALTHY
        )

    def public_payload(self) -> dict[str, object]:
        return {
            "contract_version": MANUAL_HEALTH_CONTRACT_VERSION,
            "check_id": self.check_id,
            "binding": self.binding.public_payload(),
            "outcome": self.outcome.value,
            "health": self.health.value,
            "reason_code": self.reason_code.value,
            "started_at": _iso(self.started_at),
            "finished_at": _iso(self.finished_at),
            "duration_ms": self.duration_ms,
            "stages": [item.public_payload() for item in self.stages],
        }


@dataclass(frozen=True, slots=True)
class ManualHealthEvidence:
    check_id: str
    binding: HealthCheckBinding
    outcome: ManualHealthOutcome
    health: ManualHealthState
    checked_at: datetime
    valid_until: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.check_id, str) or not self.check_id:
            raise ValueError("manual health evidence is invalid")
        _aware(self.checked_at)
        _aware(self.valid_until)
        if (
            self.outcome is not ManualHealthOutcome.PASSED
            or self.health is not ManualHealthState.HEALTHY
            or self.valid_until != self.checked_at + MANUAL_HEALTH_TTL
        ):
            raise ValueError("manual health evidence is invalid")

    @classmethod
    def from_result(cls, result: ManualHealthCheckResult) -> "ManualHealthEvidence":
        if not result.creates_evidence:
            raise ValueError("manual health result cannot create evidence")
        return cls(
            check_id=result.check_id,
            binding=result.binding,
            outcome=result.outcome,
            health=result.health,
            checked_at=result.finished_at,
            valid_until=result.finished_at + MANUAL_HEALTH_TTL,
        )

    def public_payload(self) -> dict[str, object]:
        return {
            "check_id": self.check_id,
            "binding": self.binding.public_payload(),
            "outcome": self.outcome.value,
            "health": self.health.value,
            "checked_at": _iso(self.checked_at),
            "valid_until": _iso(self.valid_until),
        }


class ManualHealthAdmissionState(StrEnum):
    READY = "ready"
    NOT_ENABLED = "not_enabled"
    UNVERIFIED = "unverified"
    STALE = "stale"
    CLOCK_ANOMALY = "clock_anomaly"


@dataclass(frozen=True, slots=True)
class ManualHealthAdmission:
    state: ManualHealthAdmissionState
    message: str

    @property
    def allowed(self) -> bool:
        return self.state is ManualHealthAdmissionState.READY


@dataclass(frozen=True, slots=True)
class ManualProbeCompatibility:
    health: ManualHealthState
    reason_code: ManualHealthReasonCode
    record_count: int


def evaluate_manual_probe_payload(spec: object, payload: bytes) -> ManualProbeCompatibility:
    """Reuse the RM-135 bounded parser/mapping without creating production tenders."""

    from app.tenders.collector.manual_adapter import (
        ManualAdapterSpec,
        preview_manual_adapter,
    )

    if not isinstance(spec, ManualAdapterSpec) or not isinstance(payload, bytes):
        raise TypeError("manual probe compatibility input is invalid")
    preview = preview_manual_adapter(spec, payload)
    if preview.has_errors:
        return ManualProbeCompatibility(
            ManualHealthState.UNHEALTHY,
            ManualHealthReasonCode.MAPPING_INCOMPATIBLE,
            0,
        )
    if not preview.records:
        return ManualProbeCompatibility(
            ManualHealthState.DEGRADED,
            ManualHealthReasonCode.INSUFFICIENT_SAMPLE,
            0,
        )
    return ManualProbeCompatibility(
        ManualHealthState.HEALTHY,
        ManualHealthReasonCode.OK,
        len(preview.records),
    )


def build_health_check_binding(
    *,
    provider_id: str,
    protocol_payload: Mapping[str, object],
    adapter_spec_version: int,
    adapter_revision: int,
    adapter_fingerprint: str,
    credential_marker: str,
) -> HealthCheckBinding:
    protocol_json = json.dumps(
        protocol_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return HealthCheckBinding(
        provider_id=_manual_provider_id(provider_id),
        protocol_fingerprint=hashlib.sha256(protocol_json.encode("utf-8")).hexdigest(),
        adapter_spec_version=adapter_spec_version,
        adapter_revision=adapter_revision,
        adapter_fingerprint=adapter_fingerprint,
        credential_marker=credential_marker,
    )


def safe_manual_health_message(reason: ManualHealthReasonCode) -> str:
    if not isinstance(reason, ManualHealthReasonCode):
        raise ValueError("manual health reason is invalid")
    return _SAFE_REASON_MESSAGES[reason]


def evaluate_manual_provider_admission(
    enabled: bool,
    evidence: ManualHealthEvidence | None,
    current_binding: HealthCheckBinding,
    now: datetime,
) -> ManualHealthAdmission:
    _aware(now)
    if not enabled:
        return ManualHealthAdmission(
            ManualHealthAdmissionState.NOT_ENABLED, "Провайдер не включён пользователем."
        )
    if evidence is None:
        return ManualHealthAdmission(
            ManualHealthAdmissionState.UNVERIFIED, "Требуется проверка подключения."
        )
    if now < evidence.checked_at:
        return ManualHealthAdmission(
            ManualHealthAdmissionState.CLOCK_ANOMALY, "Время проверки некорректно."
        )
    if evidence.binding != current_binding or now >= evidence.valid_until:
        return ManualHealthAdmission(
            ManualHealthAdmissionState.STALE, "Проверка подключения устарела."
        )
    return ManualHealthAdmission(ManualHealthAdmissionState.READY, "Провайдер готов к запуску.")


@dataclass(frozen=True, slots=True)
class ManualHealthCheckCommand:
    provider_id: str
    cancellation_token: CollectorCancellationToken = field(
        default_factory=CollectorCancellationToken, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_id", _manual_provider_id(self.provider_id))


class ManualProviderHealthService:
    """Small injected one-shot coordinator; transports remain behind a probe port."""

    MAX_CONCURRENT_CHECKS = 2
    COOLDOWN_SECONDS = 5

    def __init__(
        self,
        *,
        prepare: Callable[[str], Any],
        probe: Callable[[Any, CollectorCancellationToken], Any | Awaitable[Any]],
        persist: Callable[[ManualHealthCheckResult], Any],
        utc_now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._prepare = prepare
        self._probe = probe
        self._persist = persist
        self._utc_now = utc_now
        self._monotonic = monotonic
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_CHECKS)
        self._active: set[str] = set()
        self._last_finished: dict[str, float] = {}
        self._guard = asyncio.Lock()

    async def test_connection(self, command: ManualHealthCheckCommand) -> ManualHealthCheckResult:
        started = self._utc_now()
        if command.cancellation_token.is_cancelled:
            return _terminal_result(
                command.provider_id,
                started,
                ManualHealthOutcome.CANCELLED,
                ManualHealthState.UNKNOWN,
                ManualHealthReasonCode.CANCELLED,
                finished=self._utc_now(),
            )
        async with self._guard:
            if command.provider_id in self._active:
                return _terminal_result(
                    command.provider_id,
                    started,
                    ManualHealthOutcome.BLOCKED,
                    ManualHealthState.UNKNOWN,
                    ManualHealthReasonCode.ALREADY_RUNNING,
                    finished=self._utc_now(),
                )
            last_finished = self._last_finished.get(command.provider_id)
            if (
                last_finished is not None
                and self._monotonic() - last_finished < self.COOLDOWN_SECONDS
            ):
                return _terminal_result(
                    command.provider_id,
                    started,
                    ManualHealthOutcome.BLOCKED,
                    ManualHealthState.UNKNOWN,
                    ManualHealthReasonCode.RATE_LIMITED,
                    finished=self._utc_now(),
                )
            self._active.add(command.provider_id)
        try:
            async with self._semaphore:
                prepared = self._prepare(command.provider_id)
                value = self._probe(prepared, command.cancellation_token)
                result = await value if inspect.isawaitable(value) else value
                if not isinstance(result, ManualHealthCheckResult):
                    raise TypeError("manual health probe returned an invalid result")
                if result.creates_evidence:
                    self._persist(result)
                return result
        except asyncio.CancelledError:
            return _terminal_result(
                command.provider_id,
                started,
                ManualHealthOutcome.CANCELLED,
                ManualHealthState.UNKNOWN,
                ManualHealthReasonCode.CANCELLED,
                finished=self._utc_now(),
            )
        except Exception:
            return _terminal_result(
                command.provider_id,
                started,
                ManualHealthOutcome.FAILED,
                ManualHealthState.UNHEALTHY,
                ManualHealthReasonCode.OPERATION_FAILED_SAFE,
                finished=self._utc_now(),
            )
        finally:
            async with self._guard:
                self._active.discard(command.provider_id)
                self._last_finished[command.provider_id] = self._monotonic()


def _terminal_result(
    provider_id: str,
    started: datetime,
    outcome: ManualHealthOutcome,
    health: ManualHealthState,
    reason: ManualHealthReasonCode,
    *,
    finished: datetime,
) -> ManualHealthCheckResult:
    if finished < started:
        finished = started
    return ManualHealthCheckResult(
        check_id=f"{provider_id}:{int(started.timestamp() * 1_000_000)}",
        binding=HealthCheckBinding(provider_id, "unavailable", 1, 1, "unavailable", "none"),
        outcome=outcome,
        health=health,
        reason_code=reason,
        started_at=started,
        finished_at=finished,
        duration_ms=max(0, int((finished - started).total_seconds() * 1000)),
        stages=(),
    )


def _manual_provider_id(value: object) -> str:
    normalized = str(value).strip().casefold()
    if (
        len(normalized) != 39
        or not normalized.startswith("manual_")
        or any(character not in "0123456789abcdef" for character in normalized[7:])
    ):
        raise ValueError("manual provider id is invalid")
    return normalized


def _aware(value: object) -> None:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("manual health timestamp must be timezone-aware")


def _safe_message(value: object) -> None:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > _MAX_SAFE_MESSAGE
        or any(ord(character) < 32 for character in value)
    ):
        raise ValueError("manual health message is invalid")


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


__all__ = [
    "MANUAL_HEALTH_CONTRACT_VERSION",
    "MANUAL_HEALTH_TTL",
    "HealthCheckBinding",
    "ManualHealthAdmission",
    "ManualHealthAdmissionState",
    "ManualHealthCheckCommand",
    "ManualHealthCheckResult",
    "ManualHealthEvidence",
    "ManualHealthOutcome",
    "ManualHealthReasonCode",
    "ManualHealthStage",
    "ManualHealthStageResult",
    "ManualHealthState",
    "ManualProviderHealthService",
    "ManualProbeCompatibility",
    "build_health_check_binding",
    "evaluate_manual_provider_admission",
    "evaluate_manual_probe_payload",
    "safe_manual_health_message",
]
