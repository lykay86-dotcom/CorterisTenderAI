"""Expected-red contracts for the Qt-free RM-151 operation episode core."""

from __future__ import annotations

from datetime import datetime, timezone
from importlib import import_module

import pytest


NOW = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)


def _modules():
    return (
        import_module("app.operations.contracts"),
        import_module("app.operations.transitions"),
    )


def _episode():
    contracts, _ = _modules()
    return contracts.OperationEpisode(
        episode_id=contracts.OperationEpisodeId("episode-151-a"),
        kind=contracts.OperationKind.TENDER_SEARCH,
        subject=contracts.OperationSubject(
            namespace="collector_run",
            value="run-151",
            label=contracts.SafeText("РџРѕРёСЃРє С‚РµРЅРґРµСЂРѕРІ"),
        ),
        state=contracts.OperationState.IDLE,
        attempt=1,
        generation=1,
        revision=1,
        progress=contracts.OperationProgress.none(),
        started_at=NOW,
        updated_at=NOW,
        finished_at=None,
        reason=None,
        summary=None,
        diagnostic_id=None,
        capabilities=contracts.OperationCapabilities(
            can_cancel=True,
            can_retry=False,
            can_close=True,
        ),
        parent_episode_id=None,
    )


def test_exhaustive_canonical_transition_table() -> None:
    contracts, transitions = _modules()
    state = contracts.OperationState
    allowed = {
        state.IDLE: {state.QUEUED, state.RUNNING, state.CLOSED},
        state.QUEUED: {
            state.RUNNING,
            state.CANCELLING,
            state.CANCELLED,
            state.FAILED,
            state.CLOSED,
        },
        state.RUNNING: {
            state.RUNNING,
            state.CANCELLING,
            state.PARTIAL,
            state.SUCCEEDED,
            state.FAILED,
            state.TIMED_OUT,
            state.CLOSED,
        },
        state.CANCELLING: {
            state.CANCELLED,
            state.PARTIAL,
            state.SUCCEEDED,
            state.FAILED,
            state.TIMED_OUT,
            state.CLOSED,
        },
        state.PARTIAL: {state.CLOSED},
        state.SUCCEEDED: {state.CLOSED},
        state.FAILED: {state.CLOSED},
        state.TIMED_OUT: {state.CLOSED},
        state.CANCELLED: {state.CLOSED},
        state.CLOSED: set(),
    }

    for source in state:
        for target in state:
            assert transitions.can_transition(source, target) is (target in allowed[source])


def test_terminal_is_immutable_and_stale_revision_is_ignored() -> None:
    contracts, transitions = _modules()
    running = transitions.transition_episode(
        _episode(),
        contracts.OperationEvent(
            state=contracts.OperationState.RUNNING,
            generation=1,
            revision=2,
            occurred_at=NOW,
        ),
    ).episode
    succeeded = transitions.transition_episode(
        running,
        contracts.OperationEvent(
            state=contracts.OperationState.SUCCEEDED,
            generation=1,
            revision=3,
            occurred_at=NOW,
            finished_at=NOW,
        ),
    ).episode

    late_failure = transitions.transition_episode(
        succeeded,
        contracts.OperationEvent(
            state=contracts.OperationState.FAILED,
            generation=1,
            revision=4,
            occurred_at=NOW,
            finished_at=NOW,
        ),
    )
    stale = transitions.transition_episode(
        running,
        contracts.OperationEvent(
            state=contracts.OperationState.RUNNING,
            generation=1,
            revision=1,
            occurred_at=NOW,
        ),
    )

    assert late_failure.disposition is contracts.TransitionDisposition.REJECTED_TERMINAL
    assert late_failure.episode is succeeded
    assert stale.disposition is contracts.TransitionDisposition.IGNORED_STALE
    assert stale.episode is running


def test_cancel_request_waits_for_owner_confirmation() -> None:
    contracts, transitions = _modules()
    running = transitions.transition_episode(
        _episode(),
        contracts.OperationEvent(
            state=contracts.OperationState.RUNNING,
            generation=1,
            revision=2,
            occurred_at=NOW,
        ),
    ).episode

    requested = transitions.request_cancellation(running, revision=3, occurred_at=NOW)
    confirmed = transitions.transition_episode(
        requested.episode,
        contracts.OperationEvent(
            state=contracts.OperationState.CANCELLED,
            generation=1,
            revision=4,
            occurred_at=NOW,
            finished_at=NOW,
            reason=contracts.OperationReasonCode.CANCELLED_BY_USER,
        ),
    )

    assert requested.episode.state is contracts.OperationState.CANCELLING
    assert requested.episode.finished_at is None
    assert confirmed.episode.state is contracts.OperationState.CANCELLED
    assert confirmed.episode.finished_at == NOW


def test_retry_creates_new_episode_and_never_mutates_parent() -> None:
    contracts, transitions = _modules()
    failed = transitions.transition_episode(
        transitions.transition_episode(
            _episode(),
            contracts.OperationEvent(
                state=contracts.OperationState.RUNNING,
                generation=1,
                revision=2,
                occurred_at=NOW,
            ),
        ).episode,
        contracts.OperationEvent(
            state=contracts.OperationState.FAILED,
            generation=1,
            revision=3,
            occurred_at=NOW,
            finished_at=NOW,
            reason=contracts.OperationReasonCode.SOURCE_UNAVAILABLE,
        ),
    ).episode

    retried = transitions.retry_episode(
        failed,
        new_episode_id=contracts.OperationEpisodeId("episode-151-b"),
        occurred_at=NOW,
    )

    assert failed.state is contracts.OperationState.FAILED
    assert retried.episode_id != failed.episode_id
    assert retried.parent_episode_id == failed.episode_id
    assert retried.attempt == failed.attempt + 1
    assert retried.state is contracts.OperationState.IDLE
    assert retried.generation == failed.generation + 1


def test_progress_and_aware_time_invariants_fail_closed() -> None:
    contracts, _ = _modules()

    progress = contracts.OperationProgress.bounded(
        current=25,
        total=100,
        completed=20,
        failed=3,
        skipped=2,
        phase="collect",
    )
    assert str(progress.percent) == "25.00"

    with pytest.raises(ValueError):
        contracts.OperationProgress.bounded(current=101, total=100)
    with pytest.raises(ValueError):
        contracts.OperationProgress.bounded(current=1, total=0)
    with pytest.raises(ValueError):
        contracts.OperationEpisode(
            **{
                **_episode().to_dict(native=True),
                "started_at": datetime(2026, 7, 20, 12, 0),
            }
        )


def test_fingerprint_and_serialization_are_deterministic_and_closed() -> None:
    contracts, _ = _modules()
    episode = _episode()

    assert episode.semantic_fingerprint() == episode.semantic_fingerprint()
    assert contracts.OperationEpisode.from_dict(episode.to_dict()).to_dict() == episode.to_dict()

    future = episode.to_dict()
    future["contract_version"] = 999
    with pytest.raises(ValueError):
        contracts.OperationEpisode.from_dict(future)
