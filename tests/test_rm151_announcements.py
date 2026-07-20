"""Expected-red deterministic announcement coalescing contracts."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from importlib import import_module


NOW = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)


def _modules():
    return (
        import_module("app.operations.announcements"),
        import_module("app.operations.contracts"),
    )


def _running_episode(total: int):
    _, contracts = _modules()
    return contracts.OperationEpisode(
        episode_id=contracts.OperationEpisodeId("episode-announcement-151"),
        kind=contracts.OperationKind.TENDER_SEARCH,
        subject=contracts.OperationSubject("collector_run", "run-151"),
        state=contracts.OperationState.RUNNING,
        attempt=1,
        generation=1,
        revision=1,
        progress=contracts.OperationProgress.bounded(
            current=0,
            total=total,
            phase="collect",
        ),
        started_at=NOW,
        updated_at=NOW,
        finished_at=None,
        reason=None,
        summary=contracts.SafeText("РџРѕРёСЃРє РІС‹РїРѕР»РЅСЏРµС‚СЃСЏ"),
        diagnostic_id=None,
        capabilities=contracts.OperationCapabilities(can_cancel=True),
        parent_episode_id=None,
    )


def test_ten_thousand_progress_events_produce_at_most_twelve_announcements() -> None:
    announcements, contracts = _modules()
    coalescer = announcements.AnnouncementCoalescer(bucket_percent=10)
    base = _running_episode(10_000)
    emitted = []

    for current in range(10_001):
        snapshot = replace(
            base,
            revision=current + 1,
            progress=contracts.OperationProgress.bounded(
                current=current,
                total=10_000,
                phase="collect",
            ),
        )
        announcement = coalescer.offer(snapshot)
        if announcement is not None:
            emitted.append(announcement)

    terminal = replace(
        snapshot,
        state=contracts.OperationState.SUCCEEDED,
        revision=snapshot.revision + 1,
        finished_at=NOW,
        capabilities=contracts.OperationCapabilities(can_close=True),
    )
    emitted.append(coalescer.offer(terminal))

    assert all(item is not None for item in emitted)
    assert len(emitted) <= 12
    assert emitted[-1].terminal
    assert coalescer.active_count == 0


def test_one_thousand_duplicates_are_suppressed_but_terminal_is_never_suppressed() -> None:
    announcements, contracts = _modules()
    coalescer = announcements.AnnouncementCoalescer(bucket_percent=10)
    running = _running_episode(100)

    emitted = [coalescer.offer(running) for _ in range(1_000)]
    terminal = replace(
        running,
        state=contracts.OperationState.FAILED,
        revision=2,
        finished_at=NOW,
        reason=contracts.OperationReasonCode.INTERNAL_ERROR,
        capabilities=contracts.OperationCapabilities(can_retry=True, can_close=True),
    )

    first_terminal = coalescer.offer(terminal)
    duplicate_terminal = coalescer.offer(terminal)

    assert sum(item is not None for item in emitted) == 1
    assert first_terminal is not None
    assert first_terminal.terminal
    assert duplicate_terminal is None
    assert coalescer.active_count == 0


def test_phase_change_and_severity_escalation_are_announced_without_markup() -> None:
    announcements, contracts = _modules()
    coalescer = announcements.AnnouncementCoalescer(bucket_percent=10)
    running = _running_episode(100)
    assert coalescer.offer(running) is not None

    changed = replace(
        running,
        revision=2,
        progress=contracts.OperationProgress.bounded(
            current=1,
            total=100,
            failed=1,
            phase="persist",
        ),
        summary=contracts.SafeText("Р§Р°СЃС‚СЊ РёСЃС‚РѕС‡РЅРёРєРѕРІ РЅРµРґРѕСЃС‚СѓРїРЅР°"),
    )
    announcement = coalescer.offer(changed)

    assert announcement is not None
    assert "<" not in announcement.text.value
    assert ">" not in announcement.text.value
    assert announcement.episode_id == running.episode_id
