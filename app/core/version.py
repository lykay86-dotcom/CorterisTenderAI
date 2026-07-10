"""Версия и идентификаторы приложения."""

from __future__ import annotations

APP_NAME = "Corteris Tender AI"
APP_VERSION = "1.5.1"
APP_PUBLISHER = "ООО «КОРТЕРИС»"
APP_ID = "CorterisTenderAI"
CONFIG_SCHEMA_VERSION = 1


def version_string() -> str:
    """Возвращает строку для отображения в интерфейсе и журналах."""
    return f"{APP_NAME} {APP_VERSION}"
