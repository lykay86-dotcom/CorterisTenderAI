"""Small generation-safe state owner for the displayed analytics snapshot."""

from __future__ import annotations

from app.tenders.analytics.contracts import AnalyticsState, TenderAnalyticsSnapshot


class TenderAnalyticsViewModel:
    def __init__(self) -> None:
        self._generation = 0
        self._state = AnalyticsState.LOADING
        self._displayed_snapshot: TenderAnalyticsSnapshot | None = None
        self._reason_code = ""

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def state(self) -> AnalyticsState:
        return self._state

    @property
    def displayed_snapshot(self) -> TenderAnalyticsSnapshot | None:
        return self._displayed_snapshot

    @property
    def reason_code(self) -> str:
        return self._reason_code

    def begin(self, generation: int) -> bool:
        if generation <= self._generation:
            return False
        self._generation = generation
        self._state = AnalyticsState.LOADING
        self._reason_code = ""
        return True

    def accept(self, snapshot: TenderAnalyticsSnapshot, *, generation: int) -> bool:
        if generation < self._generation:
            return False
        self._generation = generation
        self._displayed_snapshot = snapshot
        self._state = snapshot.state
        self._reason_code = ""
        return True

    def fail(self, *, generation: int, reason_code: str) -> bool:
        if generation < self._generation:
            return False
        self._generation = generation
        self._reason_code = reason_code
        self._state = (
            AnalyticsState.STALE if self._displayed_snapshot is not None else AnalyticsState.ERROR
        )
        return True


__all__ = ["TenderAnalyticsViewModel"]
