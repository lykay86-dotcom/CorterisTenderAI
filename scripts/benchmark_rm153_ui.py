"""Reproducible offline RM-153 full-shell UI performance measurements."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from contextlib import ExitStack
from dataclasses import asdict, dataclass
from decimal import Decimal
import json
import os
from pathlib import Path
from platform import platform, python_version
import statistics
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import active_count
from time import perf_counter_ns
import tracemalloc
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6 import __version__ as pyside_version  # noqa: E402
from PySide6.QtCore import QObject, QThread, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.config.user_settings import UserPreferences  # noqa: E402
from app.repositories.business_metrics import BusinessMetricsRepository  # noqa: E402
from app.ui.business_workflow.model import (  # noqa: E402
    WorkflowArchiveMode,
    WorkflowFilterProxyModel,
    WorkflowTableModel,
)
from app.ui.charts import (  # noqa: E402
    ChartAxis,
    ChartAxisScale,
    ChartKind,
    ChartPoint,
    ChartSeries,
    ChartSpec,
    ChartState,
)
from app.ui.charts.widget import ChartCanvas  # noqa: E402
from app.ui.modern_main_window import ModernMainWindow  # noqa: E402
from app.ui.navigation import NavigationCause, RouteId, RouteRequest  # noqa: E402
from app.ui.theme.colors import DARK_PALETTE, ThemeName  # noqa: E402
from app.ui.viewmodels.dashboard_viewmodel import RecentTender  # noqa: E402
from scripts.benchmark_rm150_tables import _workflow_records  # noqa: E402


def _git_head() -> str:
    return subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


class _TenderRepository:
    def list(self) -> list[object]:
        return []


class _SettingsStore:
    def load(self) -> UserPreferences:
        return UserPreferences()


class _PriceCatalog:
    def search(self, _query: str, _limit: int) -> list[object]:
        return []


class _PriceOfferRepository:
    def __init__(self, _path: object) -> None:
        self.offers: list[object] = []

    def load(self) -> list[object]:
        return []


class _MemorySettings:
    """Minimal QSettings substitute that cannot touch the Windows registry."""

    def __init__(self, _organization: str, _application: str) -> None:
        self._values: dict[str, object] = {}

    def value(self, key: str, default: object = None) -> object:
        return self._values.get(key, default)

    def setValue(self, key: str, value: object) -> None:  # noqa: N802 - Qt API parity
        self._values[key] = value


@dataclass(frozen=True, slots=True)
class Measurement:
    scenario: str
    samples: int
    p50_ms: float
    p95_ms: float
    minimum_ms: float
    maximum_ms: float


@dataclass(frozen=True, slots=True)
class ShellLifecycleSample:
    construct_ms: float
    first_paint_ms: float
    shutdown_ms: float


def _percentile_95(values: Sequence[float]) -> float:
    ordered = sorted(values)
    rank = max(0, int(len(ordered) * 0.95 + 0.999999) - 1)
    return ordered[rank]


def _measure(
    scenario: str,
    operation: Callable[[], None],
    *,
    warmups: int,
    samples: int,
) -> Measurement:
    for _ in range(warmups):
        operation()
    durations: list[float] = []
    for _ in range(samples):
        started = perf_counter_ns()
        operation()
        durations.append((perf_counter_ns() - started) / 1_000_000)
    return Measurement(
        scenario=scenario,
        samples=samples,
        p50_ms=round(statistics.median(durations), 3),
        p95_ms=round(_percentile_95(durations), 3),
        minimum_ms=round(min(durations), 3),
        maximum_ms=round(max(durations), 3),
    )


def _summarize(scenario: str, durations: Sequence[float]) -> Measurement:
    return Measurement(
        scenario=scenario,
        samples=len(durations),
        p50_ms=round(statistics.median(durations), 3),
        p95_ms=round(_percentile_95(durations), 3),
        minimum_ms=round(min(durations), 3),
        maximum_ms=round(max(durations), 3),
    )


def _recent_tenders(size: int) -> list[RecentTender]:
    return [
        RecentTender(
            number=f"T-{index:05d}",
            title=f"Synthetic tender {index:05d}",
            customer=f"Customer {index % 100}",
            deadline="31.12.2026",
            score=index % 101,
            recommendation="owner-supplied",
            nmck=str(Decimal(index) * Decimal("10000.25")),
            status="ready",
        )
        for index in range(size)
    ]


def _chart_spec(points: int) -> ChartSpec:
    return ChartSpec(
        chart_id="rm153-chart",
        kind=ChartKind.LINE,
        title="RM-153 synthetic chart",
        x_axis=ChartAxis(ChartAxisScale.NUMERIC),
        y_axis=ChartAxis(ChartAxisScale.NUMERIC, unit="items"),
        series=(
            ChartSeries(
                "series",
                "Synthetic",
                tuple(
                    ChartPoint(f"point-{index}", Decimal(index), Decimal(index % 17))
                    for index in range(points)
                ),
            ),
        ),
        state=ChartState.EMPTY if points == 0 else ChartState.READY,
    )


def _resource_counts(root: QObject) -> dict[str, int]:
    timers = root.findChildren(QTimer)
    return {
        "qobject": len(root.findChildren(QObject)),
        "qthread": len(root.findChildren(QThread)),
        "qtimer": len(timers),
        "active_qtimer": sum(timer.isActive() for timer in timers),
        "python_threads": active_count(),
    }


def _window(root: Path) -> ModernMainWindow:
    stack = ExitStack()
    stack.enter_context(
        patch("app.ui.pages.tender_workspace_page.TenderRepository", _TenderRepository)
    )
    stack.enter_context(
        patch("app.ui.pages.tender_workspace_page.UserSettingsStore", _SettingsStore)
    )
    stack.enter_context(
        patch("app.ui.pages.tender_workspace_page.PriceCatalog", lambda _path: _PriceCatalog())
    )
    stack.enter_context(
        patch("app.ui.pages.tender_workspace_page.PriceOfferRepository", _PriceOfferRepository)
    )
    stack.enter_context(
        patch(
            "app.ui.pages.tender_workspace_page.AiProviderSettingsWidget.load", lambda _self: None
        )
    )
    stack.enter_context(
        patch("app.ui.modern_main_window.DashboardController.start", lambda _self: None)
    )
    stack.enter_context(patch("app.ui.modern_main_window.QSettings", _MemorySettings))
    stack.enter_context(
        patch(
            "app.ui.pages.business_workflow_page.SystemHealthMonitor.request_refresh",
            lambda _self: False,
        )
    )
    stack.enter_context(
        patch(
            "app.ui.modern_main_window.BusinessMetricsRepository",
            lambda: BusinessMetricsRepository(root / "workflow.json"),
        )
    )
    window = ModernMainWindow()
    window._rm153_patch_stack = stack  # type: ignore[attr-defined]
    return window


def _dispose(window: ModernMainWindow, app: QApplication) -> None:
    if not window.close():
        raise RuntimeError("synthetic shell refused bounded close")
    window.deleteLater()
    app.processEvents()
    stack = window._rm153_patch_stack  # type: ignore[attr-defined]
    stack.close()


def _sample_shell_lifecycle(root: Path, app: QApplication) -> ShellLifecycleSample:
    started = perf_counter_ns()
    window = _window(root)
    construct_ms = (perf_counter_ns() - started) / 1_000_000

    started = perf_counter_ns()
    window.show()
    app.processEvents()
    first_paint_ms = (perf_counter_ns() - started) / 1_000_000

    started = perf_counter_ns()
    _dispose(window, app)
    shutdown_ms = (perf_counter_ns() - started) / 1_000_000
    return ShellLifecycleSample(construct_ms, first_paint_ms, shutdown_ms)


def run_benchmark(
    *,
    label: str = "pre-implementation",
    warmups: int = 2,
    samples: int = 10,
    dashboard_rows: int = 1_000,
    table_rows: int = 10_000,
    chart_points: int = 1_000,
    resource_cycles: int = 25,
) -> dict[str, object]:
    if label not in {"pre-implementation", "post-implementation"}:
        raise ValueError("label must be pre-implementation or post-implementation")
    if warmups < 0 or samples < 1:
        raise ValueError("warmups must be >= 0 and samples must be >= 1")
    if resource_cycles < 0:
        raise ValueError("resource_cycles must be >= 0")
    app = QApplication.instance() or QApplication([])
    measurements: list[Measurement] = []

    with TemporaryDirectory(prefix="rm153-benchmark-", dir=ROOT) as directory:
        root = Path(directory)
        for _ in range(warmups):
            _sample_shell_lifecycle(root, app)
        lifecycle = [_sample_shell_lifecycle(root, app) for _ in range(samples)]
        measurements.extend(
            (
                _summarize("shell_construct", [item.construct_ms for item in lifecycle]),
                _summarize("first_paint", [item.first_paint_ms for item in lifecycle]),
                _summarize("shell_shutdown", [item.shutdown_ms for item in lifecycle]),
            )
        )

        window = _window(root)
        window.show()
        app.processEvents()

        routes = iter(
            (RouteId.TENDERS, RouteId.WORKFLOW, RouteId.DASHBOARD) * (warmups + samples + 1)
        )

        def switch_page() -> None:
            result = window.workspace.navigate(
                RouteRequest(next(routes), cause=NavigationCause.PROGRAMMATIC)
            )
            if not result.succeeded:
                raise RuntimeError("synthetic route switch failed")
            app.processEvents()

        measurements.append(_measure("page_switch", switch_page, warmups=warmups, samples=samples))

        tenders = _recent_tenders(dashboard_rows)
        measurements.append(
            _measure(
                "dashboard_snapshot_update",
                lambda: (window.dashboard_page.set_recent_tenders(tenders), app.processEvents()),
                warmups=warmups,
                samples=samples,
            )
        )
        measurements.append(
            _measure(
                "theme_switch",
                lambda: (window.toggle_theme(), app.processEvents()),
                warmups=warmups,
                samples=samples,
            )
        )

        workflow_model = WorkflowTableModel()
        workflow_proxy = WorkflowFilterProxyModel()
        workflow_proxy.setSourceModel(workflow_model)
        workflow_proxy.set_archive_mode(WorkflowArchiveMode.ALL)
        workflow_model.set_records(list(_workflow_records(table_rows)))
        tokens = iter(f"missing-rm153-{index}" for index in range(warmups + samples + 1))

        def filter_table() -> None:
            workflow_proxy.set_search(next(tokens))
            workflow_proxy.rowCount()

        measurements.append(
            _measure("table_filter", filter_table, warmups=warmups, samples=samples)
        )

        canvas = ChartCanvas(_chart_spec(chart_points), DARK_PALETTE, window)
        chart_specs = iter(
            _chart_spec(chart_points - index % 2) for index in range(warmups + samples + 1)
        )
        measurements.append(
            _measure(
                "chart_update",
                lambda: (canvas.set_chart(next(chart_specs)), app.processEvents()),
                warmups=warmups,
                samples=samples,
            )
        )

        before = _resource_counts(window)
        current_bytes = 0
        peak_bytes = 0
        if resource_cycles:
            tracemalloc.start()
            for _ in range(resource_cycles):
                window.apply_theme(ThemeName.LIGHT)
                window.apply_theme(ThemeName.DARK)
                window.workspace.navigate(
                    RouteRequest(RouteId.TENDERS, cause=NavigationCause.PROGRAMMATIC)
                )
                window.workspace.navigate(
                    RouteRequest(RouteId.DASHBOARD, cause=NavigationCause.PROGRAMMATIC)
                )
                app.processEvents()
            current_bytes, peak_bytes = tracemalloc.get_traced_memory()
            tracemalloc.stop()
        after = _resource_counts(window)

        shutdown_started = perf_counter_ns()
        _dispose(window, app)
        shutdown_ms = (perf_counter_ns() - shutdown_started) / 1_000_000

    return {
        "baseline": label,
        "contract": "rm153-ui-performance-baseline-v1",
        "measurement_head": _git_head(),
        "production_baseline_commit": "1c227c323c0e9912f9a8f44dc859703e2d3fcd36",
        "environment": {
            "platform": platform(),
            "python": python_version(),
            "pyside": pyside_version,
            "qt_qpa_platform": os.environ["QT_QPA_PLATFORM"],
        },
        "method": {
            "clock": "perf_counter_ns",
            "warmups": warmups,
            "samples": samples,
            "offline_synthetic": True,
            "pass_thresholds": None,
            "dashboard_rows": dashboard_rows,
            "table_rows": table_rows,
            "chart_points": chart_points,
        },
        "measurements": [asdict(item) for item in measurements],
        "resource_cycles": {
            "cycles": resource_cycles,
            "before": before,
            "after": after,
            "growth": {name: after[name] - before[name] for name in before},
            "tracemalloc_current_bytes": current_bytes,
            "tracemalloc_peak_bytes": peak_bytes,
        },
        "shutdown_ms": round(shutdown_ms, 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--label",
        choices=("pre-implementation", "post-implementation"),
        default="pre-implementation",
    )
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--dashboard-rows", type=int, default=1_000)
    parser.add_argument("--table-rows", type=int, default=10_000)
    parser.add_argument("--chart-points", type=int, default=1_000)
    parser.add_argument("--resource-cycles", type=int, default=25)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    payload = run_benchmark(
        label=arguments.label,
        warmups=arguments.warmups,
        samples=arguments.samples,
        dashboard_rows=arguments.dashboard_rows,
        table_rows=arguments.table_rows,
        chart_points=arguments.chart_points,
        resource_cycles=arguments.resource_cycles,
    )
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if arguments.output is not None:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
