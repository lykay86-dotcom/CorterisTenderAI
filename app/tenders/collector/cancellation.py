"""Cooperative cancellation primitives for collector operations."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from threading import Event, RLock
from typing import Awaitable, Callable


class CollectorCancelledError(asyncio.CancelledError):
    """Raised when a collector operation is cancelled by the user."""

    def __init__(self, reason: str = "Операция отменена пользователем.") -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class CancellationSnapshot:
    cancelled: bool
    reason: str


class CollectorCancellationToken:
    """Thread-safe cancellation token usable from Qt and asyncio code."""

    def __init__(self) -> None:
        self._event = Event()
        self._lock = RLock()
        self._reason = ""

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    @property
    def reason(self) -> str:
        with self._lock:
            return self._reason

    def cancel(self, reason: str = "Операция отменена пользователем.") -> bool:
        """Request cancellation once and return whether state changed."""

        normalized = reason.strip() or "Операция отменена пользователем."
        with self._lock:
            if self._event.is_set():
                return False
            self._reason = normalized
            self._event.set()
            return True

    def snapshot(self) -> CancellationSnapshot:
        return CancellationSnapshot(
            cancelled=self.is_cancelled,
            reason=self.reason,
        )

    def throw_if_cancelled(self) -> None:
        if self.is_cancelled:
            raise CollectorCancelledError(self.reason)

    async def wait_cancelled(self, *, poll_interval: float = 0.05) -> str:
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        while not self.is_cancelled:
            await asyncio.sleep(poll_interval)
        return self.reason

    async def sleep(
        self,
        seconds: float,
        *,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
        quantum: float = 0.05,
    ) -> None:
        """Sleep while remaining responsive to cancellation."""

        if seconds < 0:
            raise ValueError("seconds must be non-negative")
        if quantum <= 0:
            raise ValueError("quantum must be positive")
        self.throw_if_cancelled()
        remaining = float(seconds)
        while remaining > 0:
            interval = min(quantum, remaining)
            await sleeper(interval)
            remaining -= interval
            self.throw_if_cancelled()


__all__ = [
    "CancellationSnapshot",
    "CollectorCancellationToken",
    "CollectorCancelledError",
]
