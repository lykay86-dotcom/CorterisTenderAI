from datetime import datetime, timezone

from app.tenders.collector.provider_control import ProviderDisplayState, ProviderUiState
from app.tenders.collector.scheduler import CollectorScheduleRepository
from app.tenders.collector.source_monitoring import SourceMonitoringService
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.collector.vertical_source_verification import VerticalSourceVerificationRepository


def test_passive_snapshot_does_not_create_files_or_call_network(tmp_path, monkeypatch) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("network runtime must not be created")

    monkeypatch.setattr(
        "app.tenders.collector.network_runtime.create_collector_network_runtime",
        forbidden,
    )
    state = ProviderDisplayState(
        provider_id="eis",
        display_name="ЕИС",
        enabled=True,
        ui_state=ProviderUiState.UNKNOWN,
        status_text="Не проверено",
        connection_mode="HTML",
        implementation_status="test",
        homepage_url="https://example.test/",
        last_checked_at="",
        last_success_at="",
        last_error="",
        latency_ms=None,
    )
    db = tmp_path / "registry.sqlite3"
    schedule = tmp_path / "schedule.json"
    service = SourceMonitoringService(
        state_repository=CollectorStateRepository(db),
        schedule_repository=CollectorScheduleRepository(schedule),
        verification_repository=VerticalSourceVerificationRepository(db),
    )
    service.snapshot((state,), observed_at=datetime(2026, 7, 18, 12, tzinfo=timezone.utc))
    assert not db.exists()
    assert not schedule.exists()
