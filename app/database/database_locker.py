"""
AIBOS Security
Commit #42
File: app/database/database_locker.py

Closes SQLAlchemy sessions and releases SQLite locks before
backup/restore operations.
"""

from __future__ import annotations

import gc
import logging
import time
from typing import Callable

from sqlalchemy.orm import close_all_sessions

logger = logging.getLogger(__name__)


class DatabaseLocker:
    """Utility for safely releasing database resources."""

    def __init__(
        self,
        engine_factory: Callable,
        retries: int = 5,
        delay: float = 0.25,
    ) -> None:
        self._engine_factory = engine_factory
        self._retries = retries
        self._delay = delay

    def release(self) -> None:
        """Close all sessions and dispose engine."""
        logger.info("Releasing database resources...")

        try:
            close_all_sessions()
        except Exception:
            logger.exception("Unable to close SQLAlchemy sessions")

        last_error = None

        for attempt in range(1, self._retries + 1):
            try:
                engine = self._engine_factory()
                engine.dispose()
                gc.collect()
                time.sleep(self._delay)
                logger.info("Database released.")
                return
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Dispose failed (%d/%d): %s",
                    attempt,
                    self._retries,
                    exc,
                )
                gc.collect()
                time.sleep(self._delay)

        if last_error:
            raise last_error

    def restart(self):
        """
        Recreate SQLAlchemy engine after restore.
        """
        self.release()
        engine = self._engine_factory()
        engine.dispose()
        return engine
