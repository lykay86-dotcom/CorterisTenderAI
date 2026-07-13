"""Надёжное хранение JSON-конфигурации с атомарной записью."""

from __future__ import annotations

import copy
import json
import os
import tempfile
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .path_manager import PathManager
from .version import CONFIG_SCHEMA_VERSION

DEFAULT_SETTINGS: dict[str, Any] = {
    "schema_version": CONFIG_SCHEMA_VERSION,
    "first_run_completed": False,
    "company": {
        "name": "ООО «КОРТЕРИС»",
        "director": "Лукин Юрий Юрьевич",
        "inn": "9701327346",
        "kpp": "770101001",
        "ogrn": "1267700130092",
        "email": "info@corteris.ru",
        "phone": "+7 (495) 150-04-03",
        "site": "www.corteris.ru",
    },
    "finance": {
        "vat_rate": 22.0,
        "profit_mode": "markup",
        "profit_percent": 30.0,
        "risk_reserve_percent": 5.0,
    },
    "ui": {"theme": "system", "language": "ru-RU"},
    "licenses": [],
    "ai": {
        "provider": "disabled",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4.1-mini",
    },
}


def _deep_merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


class ConfigError(RuntimeError):
    """Ошибка чтения или сохранения конфигурации."""


class ConfigManager:
    """Потокобезопасный менеджер пользовательской конфигурации."""

    def __init__(
        self,
        path: Path | None = None,
        *,
        defaults: Mapping[str, Any] | None = None,
    ) -> None:
        paths = PathManager.instance().ensure_directories()
        self.path = path or (paths.config_dir / "settings.json")
        self.defaults = copy.deepcopy(dict(defaults or DEFAULT_SETTINGS))
        self._lock = threading.RLock()
        self._data: dict[str, Any] = {}
        self.load()

    def load(self) -> dict[str, Any]:
        with self._lock:
            if not self.path.exists():
                self._data = copy.deepcopy(self.defaults)
                self.save()
                return self.snapshot()
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return self._reset_corrupt_config()
            except OSError as exc:
                raise ConfigError(f"Не удалось прочитать конфигурацию {self.path}: {exc}") from exc
            if not isinstance(raw, dict):
                return self._reset_corrupt_config()
            self._data = _deep_merge(self.defaults, raw)
            return self.snapshot()

    def _reset_corrupt_config(self) -> dict[str, Any]:
        """Replace unreadable user JSON with safe defaults without blocking startup."""

        self._data = copy.deepcopy(self.defaults)
        try:
            self.save()
        except ConfigError:
            # Read-only storage still gets a safe in-memory configuration.
            pass
        return self.snapshot()

    def save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(self._data, ensure_ascii=False, indent=2, sort_keys=True)
            fd, temp_name = tempfile.mkstemp(
                prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temp_name, self.path)
            except OSError as exc:
                try:
                    Path(temp_name).unlink(missing_ok=True)
                finally:
                    raise ConfigError(f"Не удалось сохранить конфигурацию: {exc}") from exc

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._data)

    def get(self, dotted_key: str, default: Any = None) -> Any:
        with self._lock:
            current: Any = self._data
            for part in dotted_key.split("."):
                if not isinstance(current, dict) or part not in current:
                    return default
                current = current[part]
            return copy.deepcopy(current)

    def set(self, dotted_key: str, value: Any, *, save: bool = True) -> None:
        if not dotted_key.strip():
            raise ValueError("Ключ конфигурации не может быть пустым")
        with self._lock:
            parts = dotted_key.split(".")
            current = self._data
            for part in parts[:-1]:
                child = current.get(part)
                if not isinstance(child, dict):
                    child = {}
                    current[part] = child
                current = child
            current[parts[-1]] = copy.deepcopy(value)
            if save:
                self.save()

    def update(self, values: Mapping[str, Any], *, save: bool = True) -> None:
        with self._lock:
            self._data = _deep_merge(self._data, values)
            if save:
                self.save()

    def reset(self, *, save: bool = True) -> None:
        with self._lock:
            self._data = copy.deepcopy(self.defaults)
            if save:
                self.save()
