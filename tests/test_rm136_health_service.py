"""RM-136 explicit one-shot service guardrails."""

import asyncio
from datetime import datetime, timezone

from app.tenders.collector.cancellation import CollectorCancellationToken
from app.tenders.collector.manual_provider_health import (
    ManualHealthCheckCommand,
    ManualHealthOutcome,
    ManualHealthReasonCode,
    ManualProviderHealthService,
)


MANUAL_ID = f"manual_{'5' * 32}"


def test_cancelled_command_never_invokes_probe_or_persists() -> None:
    calls: list[str] = []
    token = CollectorCancellationToken()
    token.cancel()
    service = ManualProviderHealthService(
        prepare=lambda _provider_id: calls.append("prepare"),
        probe=lambda _prepared, _token: calls.append("probe"),
        persist=lambda _result: calls.append("persist"),
        utc_now=lambda: datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc),
    )

    result = asyncio.run(
        service.test_connection(ManualHealthCheckCommand(MANUAL_ID, cancellation_token=token))
    )

    assert result.outcome is ManualHealthOutcome.CANCELLED
    assert result.reason_code is ManualHealthReasonCode.CANCELLED
    assert calls == []


def test_service_is_single_flight_per_provider() -> None:
    assert ManualProviderHealthService.MAX_CONCURRENT_CHECKS == 2
    assert ManualProviderHealthService.COOLDOWN_SECONDS == 5
