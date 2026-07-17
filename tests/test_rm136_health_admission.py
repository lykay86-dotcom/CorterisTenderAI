"""RM-136 exact evidence admission contract."""

from datetime import datetime, timedelta, timezone

from app.tenders.collector.manual_provider_health import (
    HealthCheckBinding,
    ManualHealthAdmissionState,
    ManualHealthEvidence,
    ManualHealthOutcome,
    ManualHealthState,
    evaluate_manual_provider_admission,
)


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
