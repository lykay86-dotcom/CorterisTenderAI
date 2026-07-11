"""Packaged Excel template service for mass workflow import."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import sys
from typing import Iterable


@dataclass(frozen=True, slots=True)
class WorkflowTemplateCopyResult:
    source: Path
    path: Path
    size_bytes: int


class WorkflowExcelTemplateService:
    """Locate and copy the bundled CORTERIS import template."""

    DEFAULT_FILENAME = (
        "CORTERIS_Шаблон_массового_импорта.xlsx"
    )

    def __init__(
        self,
        template_path: str | Path | None = None,
    ) -> None:
        self._explicit_template_path = (
            Path(template_path)
            if template_path is not None
            else None
        )

    @property
    def template_path(self) -> Path:
        for candidate in self._candidate_paths():
            if candidate.is_file():
                return candidate
        searched = "\n".join(
            f"• {candidate}"
            for candidate in self._candidate_paths()
        )
        raise FileNotFoundError(
            "Не найден встроенный Excel-шаблон импорта.\n"
            f"Проверенные пути:\n{searched}"
        )

    def copy_to(
        self,
        target: str | Path,
    ) -> WorkflowTemplateCopyResult:
        source = self.template_path
        destination = Path(target).expanduser()

        if destination.suffix.lower() != ".xlsx":
            destination = destination.with_suffix(".xlsx")

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

        return WorkflowTemplateCopyResult(
            source=source,
            path=destination,
            size_bytes=destination.stat().st_size,
        )

    def _candidate_paths(self) -> tuple[Path, ...]:
        if self._explicit_template_path is not None:
            return (self._explicit_template_path,)

        candidates: list[Path] = []
        relative = (
            Path("templates")
            / "workflow"
            / self.DEFAULT_FILENAME
        )

        # Source checkout.
        project_root = Path(__file__).resolve().parents[2]
        candidates.append(project_root / relative)

        # PyInstaller one-file/one-folder bundle.
        bundle_root = getattr(sys, "_MEIPASS", None)
        if bundle_root:
            candidates.append(Path(bundle_root) / relative)

        # Portable application folder beside the executable.
        candidates.append(Path(sys.executable).resolve().parent / relative)

        return self._unique(candidates)

    @staticmethod
    def _unique(paths: Iterable[Path]) -> tuple[Path, ...]:
        result: list[Path] = []
        seen: set[str] = set()
        for path in paths:
            normalized = str(path.resolve(strict=False))
            if normalized in seen:
                continue
            seen.add(normalized)
            result.append(path)
        return tuple(result)


__all__ = [
    "WorkflowExcelTemplateService",
    "WorkflowTemplateCopyResult",
]
