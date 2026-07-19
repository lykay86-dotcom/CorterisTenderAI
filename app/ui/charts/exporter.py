"""Deterministic exact-data and bounded visual chart exports."""

from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal
from io import StringIO
import json
from typing import Final

from PySide6.QtCore import QBuffer, QIODevice, QRect, QSize
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgGenerator

from app.ui.charts.contracts import ChartSpec, ChartViewport, ChartXValue
from app.ui.charts.painter import paint_chart
from app.ui.charts.render_plan import normalize_chart
from app.ui.theme.colors import ThemePalette


MIN_EXPORT_WIDTH: Final = 320
MIN_EXPORT_HEIGHT: Final = 200
MAX_EXPORT_DIMENSION: Final = 4096
MAX_DEVICE_SCALE: Final = 4.0
MAX_PHYSICAL_PIXELS: Final = 16_777_216

_CSV_HEADER: Final = (
    "contract_version",
    "chart_id",
    "chart_state",
    "series_id",
    "series_label",
    "point_id",
    "point_order",
    "x_kind",
    "x_value",
    "y_value",
    "y_missing",
    "unit",
)


def _x_kind(value: ChartXValue) -> str:
    if isinstance(value, datetime):
        return "datetime"
    if isinstance(value, Decimal):
        return "decimal"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    return "category"


def _exact_scalar(value: ChartXValue | Decimal | None) -> str | int | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _evidence_dict(evidence) -> dict[str, object]:
    return {
        "source_id": evidence.source_id,
        "generation": evidence.generation,
        "observed_at": evidence.observed_at.isoformat(),
        "record_count": evidence.record_count,
        "contributor_ids": list(evidence.contributor_ids),
        "complete": evidence.complete,
        "refresh_failed": evidence.refresh_failed,
        "reason": evidence.reason,
        "demo": evidence.demo,
    }


def export_chart_json(spec: ChartSpec) -> bytes:
    """Export the exact immutable chart model as deterministic UTF-8 JSON."""
    payload = {
        "contract_version": spec.contract_version,
        "chart_id": spec.chart_id,
        "kind": spec.kind.value,
        "title": spec.title,
        "description": spec.description,
        "state": spec.state.value,
        "state_detail": spec.state_detail,
        "axes": {
            "x": {
                "scale": spec.x_axis.scale.value,
                "title": spec.x_axis.title,
                "unit": spec.x_axis.unit,
            },
            "y": {
                "scale": spec.y_axis.scale.value,
                "title": spec.y_axis.title,
                "unit": spec.y_axis.unit,
            },
        },
        "source_evidence": [_evidence_dict(item) for item in spec.source_evidence],
        "series": [
            {
                "series_id": series.series_id,
                "label": series.label,
                "color_role": series.color_role.value,
                "line_style": series.line_style.value,
                "marker": series.marker.value,
                "points": [
                    {
                        "point_id": point.point_id,
                        "label": point.label,
                        "x_kind": _x_kind(point.x),
                        "x": _exact_scalar(point.x),
                        "y": _exact_scalar(point.y),
                    }
                    for point in series.points
                ],
            }
            for series in spec.series
        ],
    }
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return f"{text}\n".encode()


def _safe_csv_text(value: object) -> object:
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


def export_chart_csv(spec: ChartSpec) -> bytes:
    """Export one exact source-order row per point."""
    target = StringIO(newline="")
    writer = csv.writer(target, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(_CSV_HEADER)
    for series in spec.series:
        for point_order, point in enumerate(series.points):
            writer.writerow(
                (
                    spec.contract_version,
                    spec.chart_id,
                    spec.state.value,
                    series.series_id,
                    _safe_csv_text(series.label),
                    point.point_id,
                    point_order,
                    _x_kind(point.x),
                    _safe_csv_text(_exact_scalar(point.x)),
                    "" if point.y is None else str(point.y),
                    str(point.y is None).lower(),
                    _safe_csv_text(spec.y_axis.unit),
                )
            )
    return target.getvalue().encode("utf-8")


def _validate_visual_viewport(viewport: ChartViewport) -> tuple[int, int]:
    if not MIN_EXPORT_WIDTH <= viewport.width <= MAX_EXPORT_DIMENSION:
        raise ValueError(
            f"Export width must be between {MIN_EXPORT_WIDTH} and {MAX_EXPORT_DIMENSION}"
        )
    if not MIN_EXPORT_HEIGHT <= viewport.height <= MAX_EXPORT_DIMENSION:
        raise ValueError(
            f"Export height must be between {MIN_EXPORT_HEIGHT} and {MAX_EXPORT_DIMENSION}"
        )
    if not 1.0 <= viewport.device_scale <= MAX_DEVICE_SCALE:
        raise ValueError(f"Export device scale must be between 1.0 and {MAX_DEVICE_SCALE}")
    physical_width = round(viewport.width * viewport.device_scale)
    physical_height = round(viewport.height * viewport.device_scale)
    if physical_width * physical_height > MAX_PHYSICAL_PIXELS:
        raise ValueError(f"Export exceeds the {MAX_PHYSICAL_PIXELS:,} pixel budget")
    return physical_width, physical_height


def _require_gui_application() -> None:
    if QGuiApplication.instance() is None:
        raise RuntimeError("Visual chart export requires an active QGuiApplication")


def export_chart_png(spec: ChartSpec, viewport: ChartViewport, palette: ThemePalette) -> bytes:
    """Paint a bounded PNG from the shared semantic plan."""
    _require_gui_application()
    physical_width, physical_height = _validate_visual_viewport(viewport)
    plan = normalize_chart(spec, viewport, palette)
    image = QImage(
        physical_width,
        physical_height,
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    if image.isNull():
        raise RuntimeError("Could not allocate bounded PNG image")
    image.setDevicePixelRatio(float(viewport.device_scale))
    painter = QPainter(image)
    if not painter.isActive():
        raise RuntimeError("Could not start PNG painter")
    paint_chart(painter, plan)
    painter.end()
    buffer = QBuffer()
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly) or not image.save(buffer, "PNG"):
        raise RuntimeError("Could not encode PNG")
    return bytes(buffer.data())


def export_chart_svg(spec: ChartSpec, viewport: ChartViewport, palette: ThemePalette) -> bytes:
    """Paint a bounded self-contained SVG from the shared semantic plan."""
    _require_gui_application()
    _validate_visual_viewport(viewport)
    plan = normalize_chart(spec, viewport, palette)
    buffer = QBuffer()
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        raise RuntimeError("Could not open SVG buffer")
    generator = QSvgGenerator()
    generator.setOutputDevice(buffer)
    generator.setSize(QSize(viewport.width, viewport.height))
    generator.setViewBox(QRect(0, 0, viewport.width, viewport.height))
    generator.setTitle(spec.title)
    generator.setDescription(spec.description)
    painter = QPainter(generator)
    if not painter.isActive():
        raise RuntimeError("Could not start SVG painter")
    paint_chart(painter, plan)
    painter.end()
    return bytes(buffer.data())


__all__ = [
    "MAX_DEVICE_SCALE",
    "MAX_EXPORT_DIMENSION",
    "MAX_PHYSICAL_PIXELS",
    "MIN_EXPORT_HEIGHT",
    "MIN_EXPORT_WIDTH",
    "export_chart_csv",
    "export_chart_json",
    "export_chart_png",
    "export_chart_svg",
]
