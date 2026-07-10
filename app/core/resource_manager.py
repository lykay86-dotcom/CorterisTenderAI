"""Поиск, проверка и копирование ресурсов приложения."""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path

from .path_manager import PathManager


@dataclass(frozen=True, slots=True)
class ResourceInfo:
    path: Path
    size: int
    sha256: str


class ResourceManager:
    def __init__(self, paths: PathManager | None = None) -> None:
        self.paths = paths or PathManager.instance()

    def resolve(self, category: str, name: str, *, required: bool = True) -> Path:
        if not category or Path(category).is_absolute():
            raise ValueError("Категория ресурса должна быть относительным путём")
        if not name or Path(name).is_absolute():
            raise ValueError("Имя ресурса должно быть относительным путём")
        return self.paths.resource(category, name, must_exist=required)

    def logo(self, *, required: bool = False) -> Path:
        candidates = (
            "corteris_logo_cropped.png",
            "corteris_logo.png",
            "logo.png",
            "logo.svg",
        )
        for name in candidates:
            path = self.paths.paths.assets_dir / name
            if path.exists():
                return path
        if required:
            raise FileNotFoundError("Фирменный логотип не найден в assets")
        return self.paths.paths.assets_dir / candidates[0]

    def template(self, name: str, *, required: bool = True) -> Path:
        path = self.paths.paths.templates_dir / name
        if required and not path.exists():
            raise FileNotFoundError(f"Шаблон не найден: {path}")
        return path

    @staticmethod
    def inspect(path: Path) -> ResourceInfo:
        if not path.is_file():
            raise FileNotFoundError(path)
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return ResourceInfo(path=path, size=path.stat().st_size, sha256=digest.hexdigest())

    def copy_user_template(self, source: Path, target_name: str) -> Path:
        """Копирует пользовательский шаблон в writable-каталог без перезаписи ресурсов EXE."""
        if source.suffix.lower() != ".docx":
            raise ValueError("Поддерживаются только шаблоны DOCX")
        if not source.is_file():
            raise FileNotFoundError(source)
        target = self.paths.writable("templates", Path(target_name).name)
        shutil.copy2(source, target)
        return target
