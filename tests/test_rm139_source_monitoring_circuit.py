from datetime import datetime, timedelta, timezone

from app.tenders.collector.health_monitor import ProviderHealthMonitor, ProviderOperationalStatus
from app.tenders.collector.models import ProviderRunOutcomeRecord
from app.tenders.collector.source_monitoring import hydrate_health_monitor


NOW = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)


def _failure(index: int) -> ProviderRunOutcomeRecord:
    return ProviderRunOutcomeRecord(
        run_id=f"run-{index}",
        provider_id="eis",
        status="timed_out",
        completed_at=(NOW - timedelta(seconds=3 - index)).isoformat(),
        error_code="provider_timeout",
        error_message="Источник превысил лимит времени.",
        item_count=0,
        elapsed_ms=1000,
    )


def test_three_persisted_failures_restore_cooldown_in_fresh_monitor() -> None:
    first = ProviderHealthMonitor(clock=lambda: 100.0, utcnow=lambda: NOW)
    hydrate_health_monitor(first, (_failure(1), _failure(2), _failure(3)), observed_at=NOW)
    snapshot = first.snapshot("eis")
    assert snapshot.status is ProviderOperationalStatus.COOLDOWN
    assert 0 < snapshot.cooldown_remaining_seconds <= 300

    second = ProviderHealthMonitor(clock=lambda: 500.0, utcnow=lambda: NOW)
    hydrate_health_monitor(second, (_failure(1), _failure(2), _failure(3)), observed_at=NOW)
    assert second.snapshot("eis").status is ProviderOperationalStatus.COOLDOWN


def test_cancelled_and_unsupported_do_not_count_as_remote_failures() -> None:
    records = tuple(
        ProviderRunOutcomeRecord(
            run_id=f"run-{status}",
            provider_id="eis",
            status=status,
            completed_at=NOW.isoformat(),
            error_code="",
            error_message="",
            item_count=0,
            elapsed_ms=0,
        )
        for status in ("cancelled", "unsupported")
    )
    monitor = ProviderHealthMonitor(clock=lambda: 100.0, utcnow=lambda: NOW)
    hydrate_health_monitor(monitor, records, observed_at=NOW)
    assert monitor.snapshot("eis").consecutive_failures == 0
