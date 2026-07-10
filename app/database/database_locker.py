"""Освобождение SQLAlchemy-сессий и SQLite-файлов перед восстановлением."""

from __future__ import annotations

import gc
import logging
import time
from collections.abc import Callable

from sqlalchemy import Engine
from sqlalchemy.orm import close_all_sessions

logger = logging.getLogger(__name__)


class DatabaseLocker:
    """Закрывает сессии и освобождает пул соединений SQLAlchemy."""

    def __init__(
        self,
        engine_factory: Callable[[], Engine],
        *,
        retries: int = 5,
        delay: float = 0.2,
    ) -> None:
        self._engine_factory = engine_factory
        self._retries = retries
        self._delay = delay

    def release(self) -> None:
        """Закрывает ORM-сессии и освобождает соединения Engine."""
        try:
            close_all_sessions()
        except Exception:
            logger.exception("Не удалось закрыть все SQLAlchemy-сессии")

        last_error: Exception | None = None
        for attempt in range(1, self._retries + 1):
            try:
                engine = self._engine_factory()
                engine.dispose(close=True)
                gc.collect()
                if self._delay:
                    time.sleep(self._delay)
                logger.info("Соединения с базой данных освобождены")
                return
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Освобождение Engine: попытка %d/%d: %s",
                    attempt,
                    self._retries,
                    exc,
                )
                gc.collect()
                if self._delay:
                    time.sleep(self._delay)

        if last_error is not None:
            raise last_error
