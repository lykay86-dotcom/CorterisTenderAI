"""Reproducible pre/post RM-150 table-model measurements without pass thresholds."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from decimal import Decimal
import json
import os
from pathlib import Path
from platform import platform, python_version
import statistics
import subprocess
from time import perf_counter_ns
import tracemalloc
from typing import Final

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import __version__ as pyside_version  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.repositories.business_metrics import (  # noqa: E402
    BusinessRecordKind,
    BusinessStatus,
    BusinessWorkflowRecord,
)
from app.ui.business_workflow.model import (  # noqa: E402
    WorkflowArchiveMode,
    WorkflowFilterProxyModel,
    WorkflowTableModel,
)
from app.ui.dashboard.tender_feed import TenderFeedModel  # noqa: E402
from app.ui.viewmodels.dashboard_viewmodel import RecentTender  # noqa: E402


DEFAULT_SIZES: Final[tuple[int, ...]] = (0, 100, 1_000, 10_000)


def _git_head() -> str:
    completed = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


@dataclass(frozen=True, slots=True)
class Measurement:
    scenario: str
    rows: int
    repeats: int
    p50_ms: float
    p95_ms: float
    minimum_ms: float
    maximum_ms: float
    peak_bytes: int


def _workflow_records(size: int) -> tuple[BusinessWorkflowRecord, ...]:
    return tuple(
        BusinessWorkflowRecord(
            id=f"record-{index:05d}",
            kind=BusinessRecordKind.PROPOSAL.value,
            tender_id=f"tender-{index:05d}",
            title=f"Tender workflow {index % 100:03d} unicode Тендер {index:05d}",
            status=BusinessStatus.REVIEW.value,
            total=Decimal(index) * Decimal("1000.25"),
            profit=Decimal(index) * Decimal("83.50"),
            margin_percent=Decimal("8.35"),
            updated_at=f"2026-07-{(index % 28) + 1:02d}T12:00:00",
        )
        for index in range(size)
    )


def _recent_tenders(size: int) -> tuple[RecentTender, ...]:
    return tuple(
        RecentTender(
            number=f"T-{index:05d}",
            title=f"Tender {index % 100:03d} unicode Тендер {index:05d}",
            customer=f"Customer {index % 100}",
            deadline="31.12.2026",
            score=index % 101,
            recommendation="owner-supplied",
            nmck=str(Decimal(index) * Decimal("10000.25")),
            status="ready",
        )
        for index in range(size)
    )


def _percentile_95(values: Sequence[float]) -> float:
    ordered = sorted(values)
    rank = max(0, int((len(ordered) * 0.95) + 0.999999) - 1)
    return ordered[rank]


def _measure(
    scenario: str,
    rows: int,
    operation: Callable[[], None],
    *,
    warmups: int,
    repeats: int,
) -> Measurement:
    for _ in range(warmups):
        operation()

    durations: list[float] = []
    for _ in range(repeats):
        started = perf_counter_ns()
        operation()
        durations.append((perf_counter_ns() - started) / 1_000_000)

    tracemalloc.start()
    operation()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return Measurement(
        scenario=scenario,
        rows=rows,
        repeats=repeats,
        p50_ms=round(statistics.median(durations), 3),
        p95_ms=round(_percentile_95(durations), 3),
        minimum_ms=round(min(durations), 3),
        maximum_ms=round(max(durations), 3),
        peak_bytes=peak,
    )


def benchmark_size(size: int, *, warmups: int, repeats: int) -> list[Measurement]:
    records = _workflow_records(size)
    tenders = _recent_tenders(size)
    workflow_model = WorkflowTableModel()
    workflow_proxy = WorkflowFilterProxyModel()
    workflow_proxy.setSourceModel(workflow_model)
    workflow_proxy.set_archive_mode(WorkflowArchiveMode.ALL)
    workflow_model.set_records(list(records))
    tender_model = TenderFeedModel()

    reset = _measure(
        "workflow_model_reset",
        size,
        lambda: workflow_model.set_records(list(records)),
        warmups=warmups,
        repeats=repeats,
    )
    search_tokens = iter(f"missing-{index}" for index in range(warmups + repeats + 1))

    def filter_missing() -> None:
        workflow_proxy.set_search(next(search_tokens))
        workflow_proxy.rowCount()

    filtered = _measure(
        "workflow_filter_missing_text",
        size,
        filter_missing,
        warmups=warmups,
        repeats=repeats,
    )

    workflow_proxy.set_search("")

    sort_direction = iter(
        (Qt.SortOrder.AscendingOrder, Qt.SortOrder.DescendingOrder) * ((warmups + repeats + 2) // 2)
    )

    def sort_and_materialize() -> None:
        workflow_proxy.sort(4, next(sort_direction))
        if workflow_proxy.rowCount():
            workflow_proxy.index(workflow_proxy.rowCount() - 1, 4).data()

    sorted_rows = _measure(
        "workflow_sort_decimal",
        size,
        sort_and_materialize,
        warmups=warmups,
        repeats=repeats,
    )
    dashboard = _measure(
        "dashboard_model_reset",
        size,
        lambda: tender_model.set_tenders(tenders),
        warmups=warmups,
        repeats=repeats,
    )
    return [reset, filtered, sorted_rows, dashboard]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", nargs="+", type=int, default=DEFAULT_SIZES)
    parser.add_argument("--warmups", type=int, default=5)
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--production-baseline", default=_git_head())
    arguments = parser.parse_args()
    if arguments.warmups < 0 or arguments.repeats < 1:
        parser.error("warmups must be >= 0 and repeats must be >= 1")
    if any(size < 0 for size in arguments.sizes):
        parser.error("sizes must be >= 0")

    QApplication.instance() or QApplication([])
    measurements = [
        measurement
        for size in arguments.sizes
        for measurement in benchmark_size(
            size,
            warmups=arguments.warmups,
            repeats=arguments.repeats,
        )
    ]
    payload = {
        "baseline": "pre-implementation",
        "measurement_head": _git_head(),
        "production_baseline_commit": arguments.production_baseline,
        "environment": {
            "platform": platform(),
            "python": python_version(),
            "pyside": pyside_version,
            "qt_qpa_platform": os.environ["QT_QPA_PLATFORM"],
        },
        "method": {
            "clock": "perf_counter_ns",
            "warmups": arguments.warmups,
            "repeats": arguments.repeats,
            "sizes": arguments.sizes,
            "data_generation_included": False,
            "pass_thresholds": None,
            "peak_allocation": "separate tracemalloc sample after timed samples",
        },
        "measurements": [asdict(item) for item in measurements],
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if arguments.output is not None:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
