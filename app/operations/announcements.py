"""Deterministic bounded operation announcement coalescing."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from decimal import Decimal

from app.operations.contracts import (
    OperationEpisode,
    OperationEpisodeId,
    ProgressMode,
    SafeText,
)


@dataclass(frozen=True, slots=True)
class OperationAnnouncement:
    episode_id: OperationEpisodeId
    text: SafeText
    terminal: bool


@dataclass(frozen=True, slots=True)
class _ActiveState:
    generation: int
    revision: int
    fingerprint: str
    phase: str
    bucket: int | None
    failed: int


class AnnouncementCoalescer:
    def __init__(self, *, bucket_percent: int = 10, terminal_history: int = 256) -> None:
        if bucket_percent < 1 or bucket_percent > 100:
            raise ValueError("bucket_percent must be within 1..100")
        if terminal_history < 1:
            raise ValueError("terminal_history must be positive")
        self.bucket_percent = int(bucket_percent)
        self.terminal_history = int(terminal_history)
        self._active: dict[OperationEpisodeId, _ActiveState] = {}
        self._terminals: OrderedDict[OperationEpisodeId, str] = OrderedDict()

    @property
    def active_count(self) -> int:
        return len(self._active)

    def offer(self, episode: OperationEpisode) -> OperationAnnouncement | None:
        fingerprint = episode.semantic_fingerprint()
        if episode.state.terminal:
            if self._terminals.get(episode.episode_id) == fingerprint:
                return None
            self._active.pop(episode.episode_id, None)
            self._terminals[episode.episode_id] = fingerprint
            while len(self._terminals) > self.terminal_history:
                self._terminals.popitem(last=False)
            return OperationAnnouncement(
                episode_id=episode.episode_id,
                text=_announcement_text(episode),
                terminal=True,
            )

        previous = self._active.get(episode.episode_id)
        bucket = _bucket(episode, self.bucket_percent)
        current = _ActiveState(
            generation=episode.generation,
            revision=episode.revision,
            fingerprint=fingerprint,
            phase=episode.progress.phase,
            bucket=bucket,
            failed=episode.progress.failed,
        )
        if previous is not None:
            if episode.generation < previous.generation or (
                episode.generation == previous.generation and episode.revision <= previous.revision
            ):
                return None
            eligible = (
                current.phase != previous.phase
                or current.bucket != previous.bucket
                or current.failed > previous.failed
            )
            self._active[episode.episode_id] = current
            if not eligible:
                return None
        else:
            self._active[episode.episode_id] = current
        return OperationAnnouncement(
            episode_id=episode.episode_id,
            text=_announcement_text(episode),
            terminal=False,
        )


def _bucket(episode: OperationEpisode, bucket_percent: int) -> int | None:
    if episode.progress.mode is not ProgressMode.BOUNDED or episode.progress.percent is None:
        return None
    return int(episode.progress.percent // Decimal(bucket_percent))


def _announcement_text(episode: OperationEpisode) -> SafeText:
    if episode.summary is not None:
        base = episode.summary.value
    elif episode.subject.label is not None:
        base = episode.subject.label.value
    else:
        base = "РћР±РЅРѕРІР»РµРЅРёРµ РѕРїРµСЂР°С†РёРё"
    if episode.progress.mode is ProgressMode.BOUNDED and episode.progress.percent is not None:
        base = f"{base}. {episode.progress.percent}%"
    return SafeText(base[: SafeText.MAX_LENGTH])


__all__ = ["AnnouncementCoalescer", "OperationAnnouncement"]
