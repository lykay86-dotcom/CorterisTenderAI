"""Инициализация инфраструктуры перед запуском интерфейса."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .config_manager import ConfigManager
from .log_manager import configure_logging
from .path_manager import AppPaths, PathManager
from .resource_manager import ResourceManager
from .version import APP_VERSION


@dataclass(slots=True)
class StartupContext:
    paths: AppPaths
    config: ConfigManager
    resources: ResourceManager


def initialize_core() -> StartupContext:
    manager = PathManager.instance()
    paths = manager.ensure_directories()
    configure_logging(log_dir=paths.log_dir)
    config = ConfigManager()
    resources = ResourceManager(manager)
    logging.getLogger(__name__).info(
        "Core инициализирован: версия=%s data_dir=%s", APP_VERSION, paths.data_dir
    )
    return StartupContext(paths=paths, config=config, resources=resources)
