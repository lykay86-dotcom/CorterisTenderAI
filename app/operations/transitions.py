"""Deterministic fail-closed operation episode transitions."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from app.operations.contracts import (
    OperationCapabilities,
    OperationEpisode,
    OperationEpisodeId,
    OperationEvent,
    OperationProgress,
    OperationState,
    SafeText,
    TransitionDisposition,
)


_ALLOWED: dict[OperationState, frozenset[OperationState]] = {
    OperationState.IDLE: frozenset(
        {OperationState.QUEUED, OperationState.RUNNING, OperationState.CLOSED}
    ),
    OperationState.QUEUED: frozenset(
        {
            OperationState.RUNNING,
            OperationState.CANCELLING,
            OperationState.CANCELLED,
            OperationState.FAILED,
            OperationState.CLOSED,
        }
    ),
    OperationState.RUNNING: frozenset(
        {
            OperationState.RUNNING,
            OperationState.CANCELLING,
            OperationState.PARTIAL,
            OperationState.SUCCEEDED,
            OperationState.FAILED,
            OperationState.TIMED_OUT,
            OperationState.CLOSED,
        }
    ),
    OperationState.CANCELLING: frozenset(
        {
            OperationState.CANCELLED,
            OperationState.PARTIAL,
            OperationState.SUCCEEDED,
            OperationState.FAILED,
            OperationState.TIMED_OUT,
            OperationState.CLOSED,
        }
    ),
    OperationState.PARTIAL: frozenset({OperationState.CLOSED}),
    OperationState.SUCCEEDED: frozenset({OperationState.CLOSED}),
    OperationState.FAILED: frozenset({OperationState.CLOSED}),
    OperationState.TIMED_OUT: frozenset({OperationState.CLOSED}),
    OperationState.CANCELLED: frozenset({OperationState.CLOSED}),
    OperationState.CLOSED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class TransitionOutcome:
    episode: OperationEpisode
    disposition: TransitionDisposition
    diagnostic_reason: SafeText | None = None

    @property
    def accepted(self) -> bool:
        return self.disposition is TransitionDisposition.ACCEPTED


def can_transition(source: OperationState, target: OperationState) -> bool:
    return target in _ALLOWED[source]


def _same_event(current: OperationEpisode, event: OperationEvent) -> bool:
    return (
        current.state is event.state
        and current.generation == event.generation
        and current.revision == event.revision
        and (event.progress is None or current.progress == event.progress)
        and (event.reason is None or current.reason is event.reason)
        and (event.summary is None or current.summary == event.summary)
        and (event.diagnostic_id is None or current.diagnostic_id == event.diagnostic_id)
        and (event.capabilities is None or current.capabilities == event.capabilities)
        and (event.finished_at is None or current.finished_at == event.finished_at)
    )


def transition_episode(current: OperationEpisode, event: OperationEvent) -> TransitionOutcome:
    if event.generation < current.generation or (
        event.generation == current.generation and event.revision < current.revision
    ):
        return TransitionOutcome(current, TransitionDisposition.IGNORED_STALE)
    if event.generation > current.generation:
        return TransitionOutcome(
            current,
            TransitionDisposition.REJECTED_INVALID,
            SafeText("РЎРјРµРЅР° generation С‚СЂРµР±СѓРµС‚ РЅРѕРІРѕРіРѕ episode."),
        )
    if event.revision == current.revision:
        return TransitionOutcome(
            current,
            (
                TransitionDisposition.IGNORED_DUPLICATE
                if _same_event(current, event)
                else TransitionDisposition.REJECTED_CONFLICT
            ),
        )
    if current.state is OperationState.CLOSED or (
        current.state.result_terminal and event.state is not OperationState.CLOSED
    ):
        return TransitionOutcome(current, TransitionDisposition.REJECTED_TERMINAL)
    if not can_transition(current.state, event.state):
        return TransitionOutcome(current, TransitionDisposition.REJECTED_TRANSITION)

    progress = event.progress if event.progress is not None else current.progress
    if (
        current.progress.mode == progress.mode
        and current.progress.phase == progress.phase
        and progress.current < current.progress.current
    ):
        return TransitionOutcome(
            current,
            TransitionDisposition.REJECTED_INVALID,
            SafeText("РџСЂРѕРіСЂРµСЃСЃ РѕРїРµСЂР°С†РёРё РЅРµ РјРѕР¶РµС‚ СѓРјРµРЅСЊС€Р°С‚СЊСЃСЏ."),
        )

    try:
        candidate = replace(
            current,
            state=event.state,
            revision=event.revision,
            progress=progress,
            updated_at=event.occurred_at,
            finished_at=event.finished_at,
            reason=event.reason if event.reason is not None else current.reason,
            summary=event.summary if event.summary is not None else current.summary,
            diagnostic_id=(
                event.diagnostic_id if event.diagnostic_id is not None else current.diagnostic_id
            ),
            capabilities=(
                event.capabilities if event.capabilities is not None else current.capabilities
            ),
        )
    except (TypeError, ValueError):
        return TransitionOutcome(current, TransitionDisposition.REJECTED_INVALID)
    return TransitionOutcome(candidate, TransitionDisposition.ACCEPTED)


def request_cancellation(
    current: OperationEpisode,
    *,
    revision: int,
    occurred_at: datetime,
) -> TransitionOutcome:
    if current.state is OperationState.CANCELLING:
        return TransitionOutcome(current, TransitionDisposition.IGNORED_DUPLICATE)
    if not current.capabilities.can_cancel:
        return TransitionOutcome(current, TransitionDisposition.REJECTED_TRANSITION)
    return transition_episode(
        current,
        OperationEvent(
            state=OperationState.CANCELLING,
            generation=current.generation,
            revision=revision,
            occurred_at=occurred_at,
            capabilities=replace(current.capabilities, can_cancel=False),
        ),
    )


def retry_episode(
    current: OperationEpisode,
    *,
    new_episode_id: OperationEpisodeId,
    occurred_at: datetime,
) -> OperationEpisode:
    if not current.state.result_terminal:
        raise ValueError("only a result-terminal episode can be retried")
    if new_episode_id == current.episode_id:
        raise ValueError("retry requires a new episode id")
    return OperationEpisode(
        episode_id=new_episode_id,
        kind=current.kind,
        subject=current.subject,
        state=OperationState.IDLE,
        attempt=current.attempt + 1,
        generation=current.generation + 1,
        revision=1,
        progress=OperationProgress.none(),
        started_at=occurred_at,
        updated_at=occurred_at,
        finished_at=None,
        reason=None,
        summary=None,
        diagnostic_id=None,
        capabilities=OperationCapabilities(can_close=True),
        parent_episode_id=current.episode_id,
    )


__all__ = [
    "TransitionOutcome",
    "can_transition",
    "request_cancellation",
    "retry_episode",
    "transition_episode",
]
