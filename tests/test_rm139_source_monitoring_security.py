from datetime import datetime, timezone

from app.tenders.collector.provider_control import ProviderDisplayState, ProviderUiState
from app.tenders.collector.scheduler import CollectorScheduleRepository
from app.tenders.collector.source_monitoring import SourceMonitoringService
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.collector.vertical_source_verification import VerticalSourceVerificationRepository


def test_raw_provider_error_is_not_copied_to_monitoring_snapshot(tmp_path) -> None:
    sentinel = "RM139_SECRET https://user:pass@example.test/?token=secret"
    state = ProviderDisplayState(
        provider_id="eis",
        display_name="ЕИС",
        enabled=True,
        ui_state=ProviderUiState.ERROR,
        status_text="Ошибка",
        connection_mode="HTML",
        implementation_status="test",
        homepage_url="https://example.test/",
        last_checked_at="2026-07-18T11:00:00+00:00",
        last_success_at="",
        last_error=sentinel,
        latency_ms=None,
    )
    service = SourceMonitoringService(
        state_repository=CollectorStateRepository(tmp_path / "registry.sqlite3"),
        schedule_repository=CollectorScheduleRepository(tmp_path / "schedule.json"),
        verification_repository=VerticalSourceVerificationRepository(tmp_path / "registry.sqlite3"),
    )
    snapshot = service.snapshot(
        (state,), observed_at=datetime(2026, 7, 18, 12, tzinfo=timezone.utc)
    )
    assert sentinel not in repr(snapshot)
    assert "token=secret" not in repr(snapshot)
