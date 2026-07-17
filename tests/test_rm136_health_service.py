"""RM-136 explicit one-shot service guardrails."""

import asyncio
from datetime import datetime, timedelta, timezone

from app.tenders.collector.cancellation import CollectorCancellationToken
from app.tenders.collector.manual_adapter import (
    CanonicalTenderField,
    FieldMappingSpec,
    ManualAdapterDataFormat,
    ManualAdapterDependencies,
    RecordSelectorSpec,
    SourceRequestSpec,
    compile_manual_adapter,
    create_manual_adapter_spec,
)
from app.tenders.collector.manual_provider_health import (
    ManualHealthCheckCommand,
    ManualHealthCheckResult,
    ManualHealthOutcome,
    ManualHealthReasonCode,
    ManualHealthState,
    ManualProviderHealthService,
    HealthCheckBinding,
)
from app.tenders.collector.manual_provider_protocol import (
    ManualProviderPayloadFormat,
    ManualProviderProtocolDraft,
    ManualProviderProtocolFamily,
    create_manual_provider_protocol_selection,
)
from app.tenders.collector.manual_provider_registration import (
    ManualProviderLifecycle,
    ManualProviderRegistration,
)
from app.tenders.provider_base import ProviderHealth, ProviderHealthStatus


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


def test_success_is_persisted_once_and_immediate_repeat_is_rate_limited() -> None:
    now = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)
    binding = HealthCheckBinding(MANUAL_ID, "a" * 64, 1, 1, "b" * 64, "none")
    passed = ManualHealthCheckResult(
        check_id="check-success",
        binding=binding,
        outcome=ManualHealthOutcome.PASSED,
        health=ManualHealthState.HEALTHY,
        reason_code=ManualHealthReasonCode.OK,
        started_at=now,
        finished_at=now + timedelta(milliseconds=5),
        duration_ms=5,
        stages=(),
    )
    persisted: list[ManualHealthCheckResult] = []
    service = ManualProviderHealthService(
        prepare=lambda provider_id: provider_id,
        probe=lambda _prepared, _token: passed,
        persist=persisted.append,
        utc_now=lambda: now,
        monotonic=lambda: 100.0,
    )

    async def execute():
        first = await service.test_connection(ManualHealthCheckCommand(MANUAL_ID))
        second = await service.test_connection(ManualHealthCheckCommand(MANUAL_ID))
        return first, second

    first, second = asyncio.run(execute())
    assert first is passed
    assert second.reason_code is ManualHealthReasonCode.RATE_LIMITED
    assert persisted == [passed]


def test_compiled_adapter_delegates_only_explicit_health_probe_dependency() -> None:
    now = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)
    protocol = create_manual_provider_protocol_selection(
        ManualProviderProtocolDraft(
            ManualProviderProtocolFamily.API,
            "https://source.example.test/v1",
            ManualProviderPayloadFormat.JSON,
        ),
        timestamp=now,
    )
    spec = create_manual_adapter_spec(
        provider_id=MANUAL_ID,
        protocol_family=ManualProviderProtocolFamily.API,
        source=SourceRequestSpec(ManualAdapterDataFormat.JSON),
        record_selector=RecordSelectorSpec(("items",)),
        field_mappings=(FieldMappingSpec(CanonicalTenderField.TITLE, ("title",), required=True),),
        revision=1,
        timestamp=now,
    )
    registration = ManualProviderRegistration(
        MANUAL_ID,
        "Площадка",
        "https://example.test",
        lifecycle_state=ManualProviderLifecycle.CONNECTION_TEST_REQUIRED,
        protocol_selection=protocol,
        adapter_spec=spec,
        created_at=now,
        updated_at=now,
    )

    class _Probe:
        async def check_health(self, received_registration, received_spec, cancellation_token):
            assert received_registration is registration
            assert received_spec is spec
            return ProviderHealth(
                MANUAL_ID,
                ProviderHealthStatus.AVAILABLE,
                now.isoformat(),
                "Проверка пройдена.",
                5,
            )

    compiled = compile_manual_adapter(
        registration,
        spec,
        dependencies=ManualAdapterDependencies(health_probe=_Probe()),
    )
    assert compiled.adapter is not None
    health = asyncio.run(compiled.adapter.check_health())
    assert health.status is ProviderHealthStatus.AVAILABLE
