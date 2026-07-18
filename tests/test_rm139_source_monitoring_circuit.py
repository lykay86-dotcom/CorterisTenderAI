import asyncio
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


def test_run_session_hydrates_persisted_circuit_before_dispatch(tmp_path) -> None:
    from app.tenders.collector.async_engine import (
        AsyncProviderSearchOutcome,
        AsyncProviderSearchStatus,
    )
    from app.tenders.collector.models import CollectionRunStatus
    from app.tenders.collector.run_session import CollectorRunSession
    from app.tenders.collector.search_errors import SearchErrorCategory
    from app.tenders.collector.store import CollectorStateRepository
    from app.tenders.provider_base import TenderSearchQuery

    repository = CollectorStateRepository(tmp_path / "tender_registry.sqlite3")
    completed = datetime.now(timezone.utc)
    for index in range(3):
        run_id = repository.start_run(
            TenderSearchQuery(),
            provider_ids=("eis",),
            started_at=(completed - timedelta(seconds=10 - index)).isoformat(),
        )
        repository.complete_run(
            run_id,
            status=CollectionRunStatus.FAILED,
            completed_at=(completed - timedelta(seconds=3 - index)).isoformat(),
            provider_outcomes=(
                AsyncProviderSearchOutcome(
                    provider_id="eis",
                    display_name="ЕИС",
                    status=AsyncProviderSearchStatus.FAILED,
                    elapsed_ms=100,
                    error_category=SearchErrorCategory.NETWORK,
                    error_code="provider_network_error",
                    error_message="Источник временно недоступен.",
                ),
            ),
        )

    class Runtime:
        def __init__(self) -> None:
            self.health_monitor = ProviderHealthMonitor(clock=lambda: 100.0)
            self.closed = False

        async def aclose(self) -> None:
            self.closed = True

    runtime = Runtime()

    class Service:
        async def collect(self, *_args, **_kwargs):
            return runtime.health_monitor.snapshot("eis")

    session = CollectorRunSession(
        tmp_path,
        runtime_factory=lambda: runtime,  # type: ignore[arg-type]
        service_factory=lambda *_args, **_kwargs: Service(),
    )
    snapshot = asyncio.run(session.run(TenderSearchQuery()))
    assert snapshot.status is ProviderOperationalStatus.COOLDOWN
    assert runtime.closed is True
