"""Централизованная настройка журналирования."""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

from .path_manager import PathManager
from .version import version_string

_CONFIGURED = False


class SensitiveDataFilter(logging.Filter):
    """Не позволяет случайно писать известные маркеры секретов в журнал."""

    TOKENS = ("sk-", "api_key", "apikey", "authorization: bearer", "password=")

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage().lower()
        if any(token in message for token in self.TOKENS):
            record.msg = "[СЕКРЕТНЫЕ ДАННЫЕ СКРЫТЫ]"
            record.args = ()
        return True


def configure_logging(
    *,
    level: str = "INFO",
    log_dir: Path | None = None,
    force: bool = False,
) -> Path:
    """Настраивает консольный и ротационный файловый журнал."""
    global _CONFIGURED
    if _CONFIGURED and not force:
        return (log_dir or PathManager.instance().paths.log_dir) / "app.log"

    directory = log_dir or PathManager.instance().ensure_directories().log_dir
    directory.mkdir(parents=True, exist_ok=True)
    log_file = directory / "app.log"

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root = logging.getLogger()
    if force:
        for handler in list(root.handlers):
            root.removeHandler(handler)
            handler.close()

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    secret_filter = SensitiveDataFilter()

    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(secret_filter)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(secret_filter)

    root.setLevel(numeric_level)
    root.addHandler(file_handler)
    root.addHandler(console_handler)
    _CONFIGURED = True

    logging.getLogger(__name__).info("Запуск %s", version_string())
    return log_file


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
