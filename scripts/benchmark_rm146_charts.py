"""Measure the bounded RM-146 chart path on deterministic synthetic fixtures."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import platform
import statistics
import sys
from time import perf_counter_ns
import tracemalloc

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import __version__ as pyside_version  # noqa: E402
from PySide6.QtGui import QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.ui.charts import (  # noqa: E402
    ChartAxis,
    ChartAxisScale,
    ChartKind,
    ChartPoint,
    ChartSeries,
    ChartSpec,
    ChartState,
    ChartViewport,
    export_chart_csv,
    export_chart_json,
    export_chart_png,
    export_chart_svg,
    normalize_chart,
)
from app.ui.charts.painter import paint_chart  # noqa: E402
from app.ui.theme.colors import DARK_PALETTE, LIGHT_PALETTE  # noqa: E402

POINT_COUNTS = (0, 1, 10, 100, 1_000, 10_000)
VIEWPORT = ChartViewport(800, 450)


def _spec(point_count: int) -> ChartSpec:
    points = tuple(
        ChartPoint(
            f"p-{index}",
            Decimal(index),
            None if index == 5 else Decimal(index) / Decimal("7"),
        )
        for index in range(point_count)
    )
    return ChartSpec(
        chart_id=f"benchmark-{point_count}",
        kind=ChartKind.LINE,
        title=f"Synthetic benchmark {point_count}",
        x_axis=ChartAxis(ChartAxisScale.NUMERIC),
        y_axis=ChartAxis(ChartAxisScale.NUMERIC, unit="units"),
        series=(ChartSeries("synthetic", "Synthetic", points),),
        state=ChartState.EMPTY if point_count == 0 else ChartState.READY,
    )


def _time_samples(callback, samples: int, warmup: int) -> tuple[float, float, float]:
    for _ in range(warmup):
        callback()
    values = []
    for _ in range(samples):
        started = perf_counter_ns()
        callback()
        values.append((perf_counter_ns() - started) / 1_000_000)
    ordered = sorted(values)
    p95_index = min(len(ordered) - 1, max(0, round(0.95 * len(ordered) + 0.5) - 1))
    return statistics.median(ordered), ordered[p95_index], max(ordered)


def _paint(plan) -> None:
    image = QImage(800, 450, QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(image)
    paint_chart(painter, plan)
    painter.end()


def _hit_test(plan) -> bool:
    if not plan.marks:
        return False
    center = plan.marks[len(plan.marks) // 2].hit_rect.center()
    return any(mark.hit_rect.contains(center.x, center.y) for mark in plan.marks)


def measure(samples: int, warmup: int) -> dict[str, object]:
    QApplication.instance() or QApplication([])
    cases = []
    tracemalloc.start()
    for theme_name, palette in (("dark", DARK_PALETTE), ("light", LIGHT_PALETTE)):
        for point_count in POINT_COUNTS:
            spec = _spec(point_count)
            plan = normalize_chart(spec, VIEWPORT, palette)
            operations = {
                "normalize": lambda: normalize_chart(spec, VIEWPORT, palette),
                "paint": lambda: _paint(plan),
                "hit_test": lambda: _hit_test(plan),
                "json": lambda: export_chart_json(spec),
                "csv": lambda: export_chart_csv(spec),
                "png": lambda: export_chart_png(spec, VIEWPORT, palette),
                "svg": lambda: export_chart_svg(spec, VIEWPORT, palette),
            }
            timings = {
                name: dict(
                    zip(("p50_ms", "p95_ms", "max_ms"), _time_samples(action, samples, warmup))
                )
                for name, action in operations.items()
            }
            png = export_chart_png(spec, VIEWPORT, palette)
            svg = export_chart_svg(spec, VIEWPORT, palette)
            cases.append(
                {
                    "theme": theme_name,
                    "points": point_count,
                    "series": 1,
                    "state": plan.state.value,
                    "marks": len(plan.marks),
                    "timings": timings,
                    "artifact_bytes": {
                        "json": len(export_chart_json(spec)),
                        "csv": len(export_chart_csv(spec)),
                        "png": len(png),
                        "svg": len(svg),
                    },
                }
            )
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "pyside6": pyside_version,
            "executable": str(Path(sys.executable).resolve()),
            "repository": str(ROOT),
            "offscreen": os.environ.get("QT_QPA_PLATFORM") == "offscreen",
        },
        "samples": samples,
        "warmup": warmup,
        "viewport": {"width": VIEWPORT.width, "height": VIEWPORT.height},
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "tracemalloc_peak_bytes": peak,
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--warmup", type=int, default=2)
    arguments = parser.parse_args()
    if arguments.samples < 1 or arguments.warmup < 0:
        parser.error("samples must be positive and warmup must be non-negative")
    print(json.dumps(measure(arguments.samples, arguments.warmup), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
