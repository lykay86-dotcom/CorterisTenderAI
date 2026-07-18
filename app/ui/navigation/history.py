"""Bounded in-memory navigation history."""

from __future__ import annotations

from collections import deque

from app.ui.navigation.contracts import NavigationSnapshot


DEFAULT_HISTORY_LIMIT = 32


class NavigationHistory:
    """Store immutable snapshots without persistence or runtime objects."""

    def __init__(self, *, limit: int = DEFAULT_HISTORY_LIMIT) -> None:
        if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
            raise ValueError("Navigation history limit must be a positive integer")
        self._entries: deque[NavigationSnapshot] = deque(maxlen=limit)

    @property
    def limit(self) -> int:
        return self._entries.maxlen or DEFAULT_HISTORY_LIMIT

    @property
    def entries(self) -> tuple[NavigationSnapshot, ...]:
        return tuple(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def push(self, snapshot: NavigationSnapshot) -> bool:
        if not isinstance(snapshot, NavigationSnapshot):
            raise TypeError("Navigation history accepts snapshots only")
        if self._entries and self._entries[-1] == snapshot:
            return False
        self._entries.append(snapshot)
        return True

    def pop(self) -> NavigationSnapshot | None:
        if not self._entries:
            return None
        return self._entries.pop()

    def clear(self) -> None:
        self._entries.clear()


__all__ = ["DEFAULT_HISTORY_LIMIT", "NavigationHistory"]
