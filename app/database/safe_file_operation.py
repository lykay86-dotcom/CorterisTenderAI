"""
AIBOS Security
Commit #41
File: app/database/safe_file_operation.py

Utilities for safe file operations on Windows with retry logic.
"""

from __future__ import annotations

import gc
import hashlib
import logging
import os
import shutil
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class SafeFileOperation:
    """Safe file operations with retry support for Windows."""

    def __init__(self, retries: int = 10, delay: float = 0.2) -> None:
        self.retries = retries
        self.delay = delay

    def _retry(self, action, description: str):
        last_error = None
        for attempt in range(1, self.retries + 1):
            try:
                return action()
            except PermissionError as exc:
                last_error = exc
                logger.warning(
                    "%s failed (%d/%d): %s",
                    description,
                    attempt,
                    self.retries,
                    exc,
                )
                gc.collect()
                time.sleep(self.delay)
        raise last_error

    def wait_until_unlocked(self, path: Path) -> bool:
        path = Path(path)
        if not path.exists():
            return True

        def probe():
            with open(path, "ab"):
                return True

        try:
            self._retry(probe, f"wait unlock {path}")
            return True
        except PermissionError:
            return False

    def safe_copy(self, source: Path, target: Path) -> None:
        source = Path(source)
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)

        self._retry(
            lambda: shutil.copy2(source, target),
            f"copy {source} -> {target}",
        )

    def safe_move(self, source: Path, target: Path) -> None:
        source = Path(source)
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)

        self._retry(
            lambda: shutil.move(str(source), str(target)),
            f"move {source} -> {target}",
        )

    def safe_replace(self, source: Path, target: Path) -> None:
        source = Path(source)
        target = Path(target)

        self._retry(
            lambda: os.replace(source, target),
            f"replace {source} -> {target}",
        )

    def safe_delete(self, path: Path) -> None:
        path = Path(path)

        if not path.exists():
            return

        self._retry(
            lambda: path.unlink(),
            f"delete {path}",
        )

    @staticmethod
    def sha256(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(block)
        return h.hexdigest()

    def verify_copy(self, source: Path, target: Path) -> bool:
        return self.sha256(source) == self.sha256(target)
