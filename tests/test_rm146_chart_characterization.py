"""Passing characterization of presentation owners inherited by RM-146."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timezone
import os
from pathlib import Path
import tomllib

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgGenerator

from app.ui.theme.colors import DARK_PALETTE, LIGHT_PALETTE
from app.ui.viewmodels.dashboard_viewmodel import DashboardSourceEvidence


ROOT = Path(__file__).parents[1]
CHART_ROLES = (
    "chart_1",
    "chart_2",
    "chart_3",
    "chart_4",
    "chart_5",
    "chart_6",
    "chart_grid",
    "chart_axis",
)
EXTERNAL_CHART_PACKAGES = {
    "matplotlib",
    "numpy",
    "plotly",
    "pyqtgraph",
}


def _project_dependencies() -> tuple[str, ...]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    return tuple(
        str(item).split("[", 1)[0].split("<", 1)[0].split(">", 1)[0].split("=", 1)[0]
        for item in project["dependencies"]
    )


def test_rm143_owns_complete_light_and_dark_chart_palette_roles() -> None:
    dark_fields = tuple(item.name for item in fields(DARK_PALETTE))
    light_fields = tuple(item.name for item in fields(LIGHT_PALETTE))

    assert dark_fields == light_fields
    assert all(role in dark_fields for role in CHART_ROLES)
    assert all(getattr(DARK_PALETTE, role).startswith("#") for role in CHART_ROLES)
    assert all(getattr(LIGHT_PALETTE, role).startswith("#") for role in CHART_ROLES)
    assert tuple(getattr(DARK_PALETTE, role) for role in CHART_ROLES) != tuple(
        getattr(LIGHT_PALETTE, role) for role in CHART_ROLES
    )


def test_rm145_source_evidence_is_frozen_and_requires_aware_time() -> None:
    evidence = DashboardSourceEvidence(
        source_id="synthetic",
        generation=1,
        observed_at=datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc),
        record_count=2,
        contributor_ids=("point-1", "point-2"),
    )

    assert evidence.contributor_ids == ("point-1", "point-2")
    with pytest.raises(FrozenInstanceError):
        evidence.record_count = 3  # type: ignore[misc]
    with pytest.raises(ValueError, match="timezone-aware"):
        DashboardSourceEvidence(
            source_id="synthetic",
            generation=1,
            observed_at=datetime(2026, 7, 19, 12, 0),
            record_count=0,
        )


def test_dependency_manifests_have_no_external_chart_framework() -> None:
    dependencies = {item.lower() for item in _project_dependencies()}
    runtime_requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    build_requirements = (ROOT / "requirements-build.txt").read_text(encoding="utf-8").lower()

    assert "pyside6" in dependencies
    assert dependencies.isdisjoint(EXTERNAL_CHART_PACKAGES)
    assert all(package not in runtime_requirements for package in EXTERNAL_CHART_PACKAGES)
    assert all(package not in build_requirements for package in EXTERNAL_CHART_PACKAGES)


def test_frozen_build_has_no_external_chart_collection_or_hidden_import() -> None:
    spec = (ROOT / "installer" / "corteris_tender_ai.spec").read_text(encoding="utf-8").lower()

    assert 'entry_point = root / "app" / "main.py"' in spec
    assert "analysis(" in spec
    assert all(package not in spec for package in EXTERNAL_CHART_PACKAGES)
    assert "pyside6.qtcharts" not in spec
    assert "pyside6.qtgraphs" not in spec


def test_selected_existing_qt_primitives_render_offscreen_png_and_svg() -> None:
    image = QImage(32, 24, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    assert painter.isActive()
    painter.drawLine(0, 0, 31, 23)
    painter.end()

    png_buffer = QBuffer()
    assert png_buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(png_buffer, "PNG")
    assert bytes(png_buffer.data()).startswith(b"\x89PNG\r\n\x1a\n")

    svg_buffer = QBuffer()
    assert svg_buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    generator = QSvgGenerator()
    generator.setOutputDevice(svg_buffer)
    generator.setSize(image.size())
    svg_painter = QPainter(generator)
    assert svg_painter.isActive()
    svg_painter.drawLine(0, 0, 31, 23)
    svg_painter.end()
    assert b"<svg" in bytes(svg_buffer.data())


def test_no_existing_application_consumer_imports_a_chart_package() -> None:
    consumers = []
    for path in (ROOT / "app").rglob("*.py"):
        if path.parts[-2:] == ("charts", "__init__.py") or "charts" in path.parts:
            continue
        source = path.read_text(encoding="utf-8").lower()
        if "app.ui.charts" in source or "qtcharts" in source or "qtgraphs" in source:
            consumers.append(path.relative_to(ROOT).as_posix())

    assert consumers == []
