from dataclasses import replace
from datetime import datetime, timezone

from app.tenders.collector.notifications import CollectorNotificationService
from app.tenders.collector.scheduler import CollectorScheduleSettings
from app.tenders.collector.source_monitoring import (
    SourceMonitoringTransition,
    SourceMonitoringTransitionKind,
    SourceOperationalState,
    SourceOperationalStatus,
    SourceVerificationState,
    monitoring_transitions,
)
from app.tenders.collector.vertical_source_verification import VerticalSourceStatus


def test_monitoring_transition_notification_id_is_deterministic() -> None:
    transition = SourceMonitoringTransition(
        provider_id="eis",
        kind=SourceMonitoringTransitionKind.OPERATIONAL_DEGRADED,
        evidence_id="run-42:failed",
        observed_at=datetime(2026, 7, 18, 12, tzinfo=timezone.utc),
    )
    service = CollectorNotificationService()
    settings = CollectorScheduleSettings(notify_failures=True)
    first = service.for_monitoring_transitions((transition,), settings)
    second = service.for_monitoring_transitions((transition,), settings)
    assert len(first) == 1
    assert first[0].id == second[0].id
    assert "run-42" not in first[0].message


def test_monitoring_warnings_respect_notify_failures() -> None:
    transition = SourceMonitoringTransition(
        provider_id="eis",
        kind=SourceMonitoringTransitionKind.CHECKPOINT_STALE,
        evidence_id="checkpoint-1",
        observed_at=datetime(2026, 7, 18, 12, tzinfo=timezone.utc),
    )
    assert (
        CollectorNotificationService().for_monitoring_transitions(
            (transition,), CollectorScheduleSettings(notify_failures=False)
        )
        == ()
    )


def test_operational_and_c19_transitions_are_both_preserved(tmp_path) -> None:
    from app.tenders.collector.provider_control import ProviderDisplayState, ProviderUiState
    from app.tenders.collector.scheduler import CollectorScheduleRepository
    from app.tenders.collector.source_monitoring import SourceMonitoringService
    from app.tenders.collector.store import CollectorStateRepository
    from app.tenders.collector.vertical_source_verification import (
        VerticalSourceVerificationRepository,
    )

    provider = ProviderDisplayState(
        "eis",
        "ЕИС",
        True,
        ProviderUiState.UNKNOWN,
        "Не проверено",
        "HTML",
        "test",
        "https://example.test/",
        "",
        "",
        "",
        None,
    )
    service = SourceMonitoringService(
        state_repository=CollectorStateRepository(tmp_path / "registry.sqlite3"),
        schedule_repository=CollectorScheduleRepository(tmp_path / "schedule.json"),
        verification_repository=VerticalSourceVerificationRepository(tmp_path / "registry.sqlite3"),
    )
    base = service.snapshot(
        (provider,),
        observed_at=datetime(2026, 7, 18, 12, tzinfo=timezone.utc),
    )
    before_source = replace(
        base.sources[0],
        operational=SourceOperationalState(
            SourceOperationalStatus.AVAILABLE,
            last_run_id="run-ok",
        ),
        verification=SourceVerificationState(
            VerticalSourceStatus.WORKING,
            verification_id="verification-1",
            qualifies_as_working=True,
        ),
    )
    after_source = replace(
        before_source,
        operational=SourceOperationalState(
            SourceOperationalStatus.DEGRADED,
            last_run_id="run-failed",
        ),
        verification=SourceVerificationState(
            VerticalSourceStatus.FAILED,
            verification_id="verification-2",
            qualifies_as_working=False,
        ),
    )
    previous = replace(base, sources=(before_source,))
    current = replace(base, revision=base.revision + 1, sources=(after_source,))

    assert {item.kind for item in monitoring_transitions(previous, current)} == {
        SourceMonitoringTransitionKind.OPERATIONAL_DEGRADED,
        SourceMonitoringTransitionKind.VERIFICATION_LOST,
    }
