"""RM-136 exact evidence admission contract."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.tenders.collector.manual_adapter import (
    CanonicalTenderField,
    FieldMappingSpec,
    ManualAdapterDataFormat,
    RecordSelectorSpec,
    SourceRequestSpec,
    create_manual_adapter_spec,
)

from app.tenders.collector.manual_provider_health import (
    HealthCheckBinding,
    ManualHealthAdmissionState,
    ManualHealthEvidence,
    ManualHealthOutcome,
    ManualHealthState,
    evaluate_manual_provider_admission,
)
from app.tenders.collector.manual_provider_protocol import (
    ManualProviderPayloadFormat,
    ManualProviderProtocolDraft,
    ManualProviderProtocolFamily,
    create_manual_provider_protocol_selection,
)
from app.tenders.collector.manual_provider_registration import (
    ManualProviderExecutionError,
    ManualProviderLifecycle,
    ManualProviderRegistration,
)
from app.tenders.collector.manual_probe_transport import (
    ManualProbeResponse,
    ManualProviderProbeTransport,
)
from app.tenders.collector.provider_control import CollectorProviderManager
from app.tenders.collector.provider_settings import ProviderEnablementRepository


NOW = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)
MANUAL_ID = f"manual_{'6' * 32}"
BINDING = HealthCheckBinding(MANUAL_ID, "a" * 64, 1, 1, "b" * 64, "none")
EVIDENCE = ManualHealthEvidence(
    check_id="check-1",
    binding=BINDING,
    outcome=ManualHealthOutcome.PASSED,
    health=ManualHealthState.HEALTHY,
    checked_at=NOW,
    valid_until=NOW + timedelta(minutes=15),
)


class _Resolver:
    async def resolve(self, hostname: str) -> tuple[str, ...]:
        return ("93.184.216.34",)


class _Http:
    async def get(self, target, pinned_address, cancellation_token, credentials):
        return ManualProbeResponse(
            200,
            "application/json",
            b'{"items": [{"title": "Tender"}]}',
        )


def test_admission_requires_explicit_enablement_and_exact_fresh_evidence() -> None:
    assert evaluate_manual_provider_admission(False, EVIDENCE, BINDING, NOW).state is (
        ManualHealthAdmissionState.NOT_ENABLED
    )
    assert evaluate_manual_provider_admission(True, EVIDENCE, BINDING, NOW).state is (
        ManualHealthAdmissionState.READY
    )
    changed = HealthCheckBinding(MANUAL_ID, "c" * 64, 1, 1, "b" * 64, "none")
    assert evaluate_manual_provider_admission(True, EVIDENCE, changed, NOW).state is (
        ManualHealthAdmissionState.STALE
    )


def test_ttl_boundary_and_clock_rollback_fail_closed() -> None:
    assert evaluate_manual_provider_admission(
        True, EVIDENCE, BINDING, EVIDENCE.valid_until
    ).state is (ManualHealthAdmissionState.STALE)
    assert (
        evaluate_manual_provider_admission(
            True, EVIDENCE, BINDING, NOW - timedelta(seconds=1)
        ).state
        is ManualHealthAdmissionState.CLOCK_ANOMALY
    )


def test_manager_requires_evidence_then_keeps_enablement_explicit(tmp_path) -> None:
    protocol = create_manual_provider_protocol_selection(
        ManualProviderProtocolDraft(
            family=ManualProviderProtocolFamily.API,
            endpoint_url="https://source.example.test/v1",
            payload_format=ManualProviderPayloadFormat.JSON,
        ),
        timestamp=NOW,
    )
    spec = create_manual_adapter_spec(
        provider_id=MANUAL_ID,
        protocol_family=ManualProviderProtocolFamily.API,
        source=SourceRequestSpec(ManualAdapterDataFormat.JSON),
        record_selector=RecordSelectorSpec(("items",)),
        field_mappings=(FieldMappingSpec(CanonicalTenderField.TITLE, ("title",), required=True),),
        revision=1,
        timestamp=NOW,
    )
    registration = ManualProviderRegistration(
        provider_id=MANUAL_ID,
        display_name="Площадка",
        homepage_url="https://example.test",
        lifecycle_state=ManualProviderLifecycle.CONNECTION_TEST_REQUIRED,
        protocol_selection=protocol,
        adapter_spec=spec,
        created_at=NOW,
        updated_at=NOW,
    )
    settings = ProviderEnablementRepository(tmp_path / "collector_provider_settings.json")
    settings.register_manual_provider(registration)
    manager = CollectorProviderManager(
        tmp_path,
        environment={},
        enablement_repository=settings,
        manual_provider_clock=lambda: NOW + timedelta(minutes=1),
        manual_probe_transport=ManualProviderProbeTransport(
            resolver=_Resolver(),
            http=_Http(),
        ),
    )

    with pytest.raises(ManualProviderExecutionError):
        manager.set_enabled(MANUAL_ID, True)

    result = asyncio.run(manager.test_manual_provider_connection(MANUAL_ID))
    assert result.outcome is ManualHealthOutcome.PASSED
    assert manager.check_repository.manual_evidence(MANUAL_ID) is not None

    ready = next(item for item in manager.states() if item.provider_id == MANUAL_ID)
    assert ready.enabled is False
    assert ready.status_text == "Готов к включению"
    assert MANUAL_ID not in manager.enabled_provider_ids()

    enabled = manager.set_enabled(MANUAL_ID, True)
    assert enabled.enabled is True
    assert manager.assert_runnable_provider_ids((MANUAL_ID,)) == (MANUAL_ID,)
