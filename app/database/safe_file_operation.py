"""Надёжные файловые операции с повторными попытками для Windows."""

from __future__ import annotations

import gc
import hashlib
import logging
import os
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class SafeFileOperation:
    """Выполняет файловые операции с повтором при временной блокировке Windows."""

    def __init__(
        self,
        retries: int = 15,
        delay: float = 0.15,
        backoff: float = 1.25,
    ) -> None:
        if retries < 1:
            raise ValueError("retries должно быть не меньше 1")
        if delay < 0:
            raise ValueError("delay не может быть отрицательным")
        if backoff < 1:
            raise ValueError("backoff должно быть не меньше 1")
        self.retries = retries
        self.delay = delay
        self.backoff = backoff

    @staticmethod
    def _is_lock_error(exc: OSError) -> bool:
        return isinstance(exc, PermissionError) or getattr(exc, "winerror", None) in {
            5,
            32,
            33,
        }

    def _retry(self, action: Callable[[], T], description: str) -> T:
        last_error: OSError | None = None
        pause = self.delay

        for attempt in range(1, self.retries + 1):
            try:
                return action()
            except OSError as exc:
                if not self._is_lock_error(exc):
                    raise
                last_error = exc
                logger.warning(
                    "%s: попытка %d/%d не выполнена: %s",
                    description,
                    attempt,
                    self.retries,
                    exc,
                )
                gc.collect()
                if pause:
                    time.sleep(pause)
                pause *= self.backoff

        assert last_error is not None
        raise last_error

    def wait_until_unlocked(self, path: Path | str) -> bool:
        target = Path(path)
        if not target.exists():
            return True

        def probe() -> bool:
            with target.open("rb"):
                return True

        try:
            return self._retry(probe, f"Ожидание освобождения {target}")
        except OSError:
            return False

    def safe_copy(self, source: Path | str, target: Path | str) -> Path:
        src = Path(source)
        dst = Path(target)
        if not src.is_file():
            raise FileNotFoundError(src)
        dst.parent.mkdir(parents=True, exist_ok=True)

        self._retry(
            lambda: shutil.copy2(src, dst),
            f"Копирование {src} -> {dst}",
        )
        return dst

    def safe_move(self, source: Path | str, target: Path | str) -> Path:
        src = Path(source)
        dst = Path(target)
        if not src.exists():
            raise FileNotFoundError(src)
        dst.parent.mkdir(parents=True, exist_ok=True)

        self._retry(
            lambda: shutil.move(str(src), str(dst)),
            f"Перемещение {src} -> {dst}",
        )
        return dst

    def safe_replace(self, source: Path | str, target: Path | str) -> Path:
        src = Path(source)
        dst = Path(target)
        if not src.is_file():
            raise FileNotFoundError(src)
        dst.parent.mkdir(parents=True, exist_ok=True)

        self._retry(
            lambda: os.replace(src, dst),
            f"Атомарная замена {src} -> {dst}",
        )
        return dst

    def safe_delete(self, path: Path | str, *, missing_ok: bool = True) -> None:
        target = Path(path)
        if not target.exists():
            if missing_ok:
                return
            raise FileNotFoundError(target)

        self._retry(
            target.unlink,
            f"Удаление {target}",
        )

    def safe_write_text(
        self,
        path: Path | str,
        content: str,
        *,
        encoding: str = "utf-8",
    ) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")

        try:
            self._retry(
                lambda: temporary.write_text(content, encoding=encoding),
                f"Запись временного файла {temporary}",
            )
            self.safe_replace(temporary, target)
        finally:
            if temporary.exists():
                self.safe_delete(temporary)

        return target

    @staticmethod
    def sha256(path: Path | str) -> str:
        target = Path(path)
        digest = hashlib.sha256()
        with target.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def verify_copy(self, source: Path | str, target: Path | str) -> bool:
        src = Path(source)
        dst = Path(target)
        return (
            src.is_file()
            and dst.is_file()
            and src.stat().st_size == dst.stat().st_size
            and self.sha256(src) == self.sha256(dst)
        )
