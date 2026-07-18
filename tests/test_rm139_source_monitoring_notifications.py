from datetime import datetime, timezone

from app.tenders.collector.notifications import CollectorNotificationService
from app.tenders.collector.scheduler import CollectorScheduleSettings
from app.tenders.collector.source_monitoring import (
    SourceMonitoringTransition,
    SourceMonitoringTransitionKind,
)


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
    assert CollectorNotificationService().for_monitoring_transitions(
        (transition,), CollectorScheduleSettings(notify_failures=False)
    ) == ()
