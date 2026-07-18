from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from app.tenders.collector.provider_control import ProviderDisplayState, ProviderUiState
from app.tenders.collector.source_monitoring import (
    SourceMonitoringPolicy,
    SourceMonitoringService,
)
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.collector.scheduler import CollectorScheduleRepository
from app.tenders.collector.vertical_source_verification import VerticalSourceVerificationRepository


def _state(provider_id: str, *, priority_name: str) -> ProviderDisplayState:
    return ProviderDisplayState(
        provider_id=provider_id,
        display_name=priority_name,
        enabled=True,
        ui_state=ProviderUiState.UNKNOWN,
        status_text="Состояние не проверено",
        connection_mode="Тест",
        implementation_status="test",
        homepage_url="https://example.test/",
        last_checked_at="",
        last_success_at="",
        last_error="",
        latency_ms=None,
    )


def _service(tmp_path) -> SourceMonitoringService:
    return SourceMonitoringService(
        state_repository=CollectorStateRepository(tmp_path / "tender_registry.sqlite3"),
        schedule_repository=CollectorScheduleRepository(tmp_path / "collector_schedule.json"),
        verification_repository=VerticalSourceVerificationRepository(
            tmp_path / "tender_registry.sqlite3"
        ),
    )


def test_snapshot_is_ordered_immutable_and_revisioned(tmp_path) -> None:
    service = _service(tmp_path)
    observed = datetime(2026, 7, 18, 12, tzinfo=timezone.utc)
    states = (_state("zeta", priority_name="Я"), _state("alpha", priority_name="А"))

    first = service.snapshot(states, observed_at=observed)
    second = service.snapshot(reversed(states), observed_at=observed)

    assert first.policy_version == SourceMonitoringPolicy().policy_version
    assert tuple(item.provider_id for item in first.sources) == ("alpha", "zeta")
    assert tuple(item.provider_id for item in second.sources) == ("alpha", "zeta")
    assert second.revision == first.revision + 1
    with pytest.raises(FrozenInstanceError):
        first.revision = 99  # type: ignore[misc]


def test_dimensions_do_not_invent_success(tmp_path) -> None:
    snapshot = _service(tmp_path).snapshot(
        (_state("eis", priority_name="ЕИС"),),
        observed_at=datetime(2026, 7, 18, 12, tzinfo=timezone.utc),
    )
    source = snapshot.sources[0]
    assert source.readiness.enabled is True
    assert source.connection.status.value == "unknown"
    assert source.operational.status.value == "unknown"
    assert source.checkpoint.freshness.value in {"not_applicable", "unknown"}
    assert source.verification.qualifies_as_working is False
