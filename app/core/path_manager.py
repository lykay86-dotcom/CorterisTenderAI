"""Единое управление путями в исходниках и собранном EXE."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from platformdirs import user_cache_dir, user_config_dir, user_data_dir, user_log_dir

from .version import APP_ID, APP_PUBLISHER


@dataclass(frozen=True, slots=True)
class AppPaths:
    """Набор путей приложения.

    ``bundle_dir`` содержит ресурсы, упакованные PyInstaller. ``data_dir`` и
    соседние каталоги принадлежат пользователю и доступны для записи.
    """

    bundle_dir: Path
    project_dir: Path
    data_dir: Path
    config_dir: Path
    log_dir: Path
    cache_dir: Path
    projects_dir: Path
    backups_dir: Path
    exports_dir: Path
    temp_dir: Path
    templates_dir: Path
    assets_dir: Path
    catalog_dir: Path
    database_file: Path


class PathManager:
    """Определяет и создаёт все пути приложения.

    Корневые каталоги можно переопределить переменными окружения:
    ``CORTERIS_DATA_DIR``, ``CORTERIS_CONFIG_DIR``, ``CORTERIS_LOG_DIR``.
    Это удобно для тестов и переносной установки.
    """

    _instance: ClassVar["PathManager | None"] = None

    def __init__(self, *, project_dir: Path | None = None) -> None:
        self._project_dir = (project_dir or self._detect_project_dir()).resolve()
        self._bundle_dir = self._detect_bundle_dir().resolve()
        self._paths = self._build_paths()

    @classmethod
    def instance(cls) -> "PathManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Сбрасывает singleton. Предназначено для тестов."""
        cls._instance = None

    @staticmethod
    def is_frozen() -> bool:
        return bool(getattr(sys, "frozen", False))

    @staticmethod
    def _detect_bundle_dir() -> Path:
        if getattr(sys, "frozen", False):
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                return Path(meipass)
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parents[2]

    @staticmethod
    def _detect_project_dir() -> Path:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parents[2]

    @staticmethod
    def _env_path(name: str, fallback: str) -> Path:
        value = os.getenv(name)
        return Path(value).expanduser() if value else Path(fallback)

    def _build_paths(self) -> AppPaths:
        data_dir = self._env_path(
            "CORTERIS_DATA_DIR", user_data_dir(APP_ID, APP_PUBLISHER)
        ).resolve()
        config_dir = self._env_path(
            "CORTERIS_CONFIG_DIR", user_config_dir(APP_ID, APP_PUBLISHER)
        ).resolve()
        log_dir = self._env_path("CORTERIS_LOG_DIR", user_log_dir(APP_ID, APP_PUBLISHER)).resolve()
        cache_dir = self._env_path(
            "CORTERIS_CACHE_DIR", user_cache_dir(APP_ID, APP_PUBLISHER)
        ).resolve()

        resource_root = self._bundle_dir
        return AppPaths(
            bundle_dir=self._bundle_dir,
            project_dir=self._project_dir,
            data_dir=data_dir,
            config_dir=config_dir,
            log_dir=log_dir,
            cache_dir=cache_dir,
            projects_dir=data_dir / "projects",
            backups_dir=data_dir / "backups",
            exports_dir=data_dir / "exports",
            temp_dir=cache_dir / "temp",
            templates_dir=resource_root / "templates",
            assets_dir=resource_root / "assets",
            catalog_dir=data_dir / "catalog",
            database_file=data_dir / "corteris_tender_ai.db",
        )

    @property
    def paths(self) -> AppPaths:
        return self._paths

    def ensure_directories(self) -> AppPaths:
        """Создаёт только каталоги, которые должны быть доступны для записи."""
        writable = (
            self._paths.data_dir,
            self._paths.config_dir,
            self._paths.log_dir,
            self._paths.cache_dir,
            self._paths.projects_dir,
            self._paths.backups_dir,
            self._paths.exports_dir,
            self._paths.temp_dir,
            self._paths.catalog_dir,
        )
        for directory in writable:
            directory.mkdir(parents=True, exist_ok=True)
        return self._paths

    def resource(self, *parts: str, must_exist: bool = True) -> Path:
        """Возвращает путь к ресурсу внутри пакета/проекта."""
        candidate = self._paths.bundle_dir.joinpath(*parts).resolve()
        if must_exist and not candidate.exists():
            raise FileNotFoundError(f"Ресурс не найден: {candidate}")
        return candidate

    def writable(self, *parts: str, create_parent: bool = True) -> Path:
        """Возвращает путь внутри пользовательского каталога данных."""
        candidate = self._paths.data_dir.joinpath(*parts).resolve()
        if create_parent:
            candidate.parent.mkdir(parents=True, exist_ok=True)
        return candidate

    def diagnostic(self) -> dict[str, str | bool]:
        """Возвращает безопасный диагностический снимок путей."""
        return {
            "frozen": self.is_frozen(),
            "bundle_dir": str(self._paths.bundle_dir),
            "project_dir": str(self._paths.project_dir),
            "data_dir": str(self._paths.data_dir),
            "config_dir": str(self._paths.config_dir),
            "log_dir": str(self._paths.log_dir),
            "templates_exists": self._paths.templates_dir.exists(),
            "assets_exists": self._paths.assets_dir.exists(),
        }
