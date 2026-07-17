"""RM-136 immutable manual-provider health contract."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.tenders.collector.manual_provider_health import (
    MANUAL_HEALTH_CONTRACT_VERSION,
    MANUAL_HEALTH_TTL,
    HealthCheckBinding,
    ManualHealthCheckResult,
    ManualHealthOutcome,
    ManualHealthReasonCode,
    ManualHealthStage,
    ManualHealthStageResult,
    ManualHealthState,
)


NOW = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)
MANUAL_ID = f"manual_{'1' * 32}"


def _binding() -> HealthCheckBinding:
    return HealthCheckBinding(
        provider_id=MANUAL_ID,
        protocol_fingerprint="a" * 64,
        adapter_spec_version=1,
        adapter_revision=2,
        adapter_fingerprint="b" * 64,
        credential_marker="c" * 64,
    )


def test_health_contract_is_closed_immutable_and_has_fixed_ttl() -> None:
    assert MANUAL_HEALTH_CONTRACT_VERSION == 1
    assert MANUAL_HEALTH_TTL == timedelta(minutes=15)
    result = ManualHealthCheckResult(
        check_id="check-1",
        binding=_binding(),
        outcome=ManualHealthOutcome.PASSED,
        health=ManualHealthState.HEALTHY,
        reason_code=ManualHealthReasonCode.OK,
        started_at=NOW,
        finished_at=NOW + timedelta(milliseconds=25),
        duration_ms=25,
        stages=(
            ManualHealthStageResult(
                stage=ManualHealthStage.PRECONDITIONS,
                health=ManualHealthState.HEALTHY,
                reason_code=ManualHealthReasonCode.OK,
                message="Предварительные условия выполнены.",
            ),
        ),
    )

    assert result.creates_evidence is True
    assert result.public_payload()["binding"]["provider_id"] == MANUAL_ID
    with pytest.raises(Exception):
        result.duration_ms = 1  # type: ignore[misc]


def test_health_result_rejects_naive_or_inverted_timestamps() -> None:
    kwargs = dict(
        check_id="check-2",
        binding=_binding(),
        outcome=ManualHealthOutcome.FAILED,
        health=ManualHealthState.UNHEALTHY,
        reason_code=ManualHealthReasonCode.PROTOCOL_ERROR,
        duration_ms=0,
        stages=(),
    )
    with pytest.raises(ValueError):
        ManualHealthCheckResult(started_at=NOW.replace(tzinfo=None), finished_at=NOW, **kwargs)
    with pytest.raises(ValueError):
        ManualHealthCheckResult(started_at=NOW, finished_at=NOW - timedelta(seconds=1), **kwargs)
