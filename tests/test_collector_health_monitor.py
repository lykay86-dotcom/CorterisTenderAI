from __future__ import annotations

from datetime import datetime, timezone

from app.tenders.collector.health_monitor import (
    ProviderHealthMonitor,
    ProviderHealthPolicy,
    ProviderOperationalStatus,
)


class FakeClock:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        return self.value


def test_health_monitor_opens_and_recovers_circuit() -> None:
    clock = FakeClock()
    monitor = ProviderHealthMonitor(
        default_policy=ProviderHealthPolicy(
            failure_threshold=2,
            cooldown_seconds=30,
            unavailable_threshold=5,
        ),
        clock=clock,
        utcnow=lambda: datetime(2026, 7, 12, tzinfo=timezone.utc),
    )

    first = monitor.register_failure("eis", TimeoutError("timeout"))
    second = monitor.register_failure("eis", TimeoutError("timeout"))

    assert first.status == ProviderOperationalStatus.DEGRADED
    assert second.status == ProviderOperationalStatus.COOLDOWN
    assert not monitor.can_execute("eis")

    clock.value += 31
    assert monitor.can_execute("eis")
    assert monitor.snapshot("eis").status == ProviderOperationalStatus.DEGRADED

    success = monitor.register_success("eis", latency_ms=250)
    assert success.status == ProviderOperationalStatus.AVAILABLE
    assert success.consecutive_failures == 0
    assert success.average_latency_ms == 250


def test_health_monitor_supports_not_configured_and_user_disabled() -> None:
    monitor = ProviderHealthMonitor()
    missing = monitor.register_not_configured("b2b", "API key required")
    assert missing.status == ProviderOperationalStatus.NOT_CONFIGURED
    assert not monitor.can_execute("b2b")

    disabled = monitor.set_disabled("eis", True)
    assert disabled.status == ProviderOperationalStatus.DISABLED
    assert not monitor.can_execute("eis")
    assert monitor.set_disabled("eis", False).status == (ProviderOperationalStatus.UNKNOWN)


def test_unavailable_provider_is_rechecked_after_extended_cooldown() -> None:
    clock = FakeClock()
    monitor = ProviderHealthMonitor(
        default_policy=ProviderHealthPolicy(
            failure_threshold=1,
            cooldown_seconds=10,
            unavailable_threshold=2,
        ),
        clock=clock,
    )
    monitor.register_failure("eis", TimeoutError("one"))
    unavailable = monitor.register_failure("eis", TimeoutError("two"))
    assert unavailable.status == ProviderOperationalStatus.UNAVAILABLE
    assert not monitor.can_execute("eis")

    clock.value += 31
    assert monitor.can_execute("eis")
    assert monitor.snapshot("eis").status == ProviderOperationalStatus.DEGRADED
