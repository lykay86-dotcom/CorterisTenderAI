"""Tests for collector notification persistence and rendering."""

from __future__ import annotations

from app.tenders.collector.async_engine import (
    AsyncProviderBatchResult,
)
from app.tenders.collector.models import (
    CollectionPersistenceSummary,
    CollectionRunStatus,
    CollectorRunResult,
    DeduplicationResult,
)
from app.tenders.collector.notifications import (
    CollectorNotificationRepository,
    CollectorNotificationService,
)
from app.tenders.collector.scheduler import (
    CollectorScheduleSettings,
)


def _result(
    *,
    new_count=2,
    changed_count=1,
    status=CollectionRunStatus.COMPLETED,
):
    return CollectorRunResult(
        run_id="run-notify",
        status=status,
        batch_result=AsyncProviderBatchResult(
            results=(),
            outcomes=(),
            started_at="2026-07-12T10:00:00+00:00",
            completed_at="2026-07-12T10:00:01+00:00",
            elapsed_ms=1000,
        ),
        deduplication=DeduplicationResult(
            items=(),
            groups=(),
            raw_count=0,
        ),
        persistence=CollectionPersistenceSummary(
            run_id="run-notify",
            new_count=new_count,
            unchanged_count=0,
            changed_count=changed_count,
            merged_count=new_count + changed_count,
            duplicate_count=0,
            change_count=changed_count,
            version_count=changed_count,
        ),
    )


def _settings():
    return CollectorScheduleSettings()


def test_service_builds_new_and_changed_notifications() -> None:
    items = CollectorNotificationService().for_result(
        _result(),
        _settings(),
    )

    assert len(items) == 2
    assert "2" in items[0].message
    assert "1" in items[1].message


def test_partial_run_creates_warning() -> None:
    items = CollectorNotificationService().for_result(
        _result(
            new_count=0,
            changed_count=0,
            status=CollectionRunStatus.PARTIAL,
        ),
        _settings(),
    )

    assert len(items) == 1
    assert items[0].kind.value == "warning"


def test_repository_deduplicates_by_notification_id(
    tmp_path,
) -> None:
    repository = CollectorNotificationRepository(tmp_path / "notifications.json")
    items = CollectorNotificationService().for_result(
        _result(),
        _settings(),
    )

    repository.add_many(items)
    repository.add_many(items)

    assert len(repository.list_notifications()) == 2
    assert repository.unread_count() == 2


def test_mark_all_read(tmp_path) -> None:
    repository = CollectorNotificationRepository(tmp_path / "notifications.json")
    repository.add_many(
        CollectorNotificationService().for_result(
            _result(),
            _settings(),
        )
    )

    changed = repository.mark_all_read()

    assert changed == 2
    assert repository.unread_count() == 0
