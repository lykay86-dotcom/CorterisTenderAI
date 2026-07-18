"""Measure RM-141 table-model refresh and filtering costs without pass thresholds."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
import json
import os
from platform import platform, python_version
import statistics
from time import perf_counter_ns
from typing import Final

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import __version__ as pyside_version  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.repositories.business_metrics import (  # noqa: E402
    BusinessRecordKind,
    BusinessStatus,
    BusinessWorkflowRecord,
)
from app.ui.business_workflow.model import (  # noqa: E402
    WorkflowFilterProxyModel,
    WorkflowTableModel,
)
from app.ui.dashboard.tender_feed import TenderFeedModel  # noqa: E402
from app.ui.viewmodels.dashboard_viewmodel import RecentTender  # noqa: E402


DEFAULT_SIZES: Final[tuple[int, ...]] = (0, 100, 1_000, 10_000)


@dataclass(frozen=True, slots=True)
class Measurement:
    scenario: str
    rows: int
    repeats: int
    median_ms: float
    p95_ms: float
    minimum_ms: float
    maximum_ms: float


def _workflow_records(size: int) -> list[BusinessWorkflowRecord]:
    return [
        BusinessWorkflowRecord(
            id=f"record-{index:05d}",
            kind=BusinessRecordKind.PROPOSAL.value,
            tender_id=str(index),
            title=f"Tender workflow {index:05d}",
            status=BusinessStatus.REVIEW.value,
            total=float(index) * 1_000.25,
            profit=float(index) * 83.5,
            margin_percent=8.35,
            updated_at=f"2026-07-{(index % 28) + 1:02d}T12:00:00",
        )
        for index in range(size)
    ]


def _recent_tenders(size: int) -> list[RecentTender]:
    return [
        RecentTender(
            number=f"T-{index:05d}",
            title=f"Tender {index:05d}",
            customer=f"Customer {index % 100}",
            deadline="31.12.2026",
            score=index % 101,
            recommendation="participate",
            nmck=str(index * 10_000),
            status="new",
        )
        for index in range(size)
    ]


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

    return Measurement(
        scenario=scenario,
        rows=rows,
        repeats=repeats,
        median_ms=round(statistics.median(durations), 3),
        p95_ms=round(_percentile_95(durations), 3),
        minimum_ms=round(min(durations), 3),
        maximum_ms=round(max(durations), 3),
    )


def benchmark_size(size: int, *, warmups: int, repeats: int) -> list[Measurement]:
    records = _workflow_records(size)
    tenders = _recent_tenders(size)

    workflow_model = WorkflowTableModel()
    workflow_proxy = WorkflowFilterProxyModel()
    workflow_proxy.setSourceModel(workflow_model)
    tender_model = TenderFeedModel()

    workflow_measurement = _measure(
        "workflow_model_reset_and_sort",
        size,
        lambda: workflow_model.set_records(records),
        warmups=warmups,
        repeats=repeats,
    )

    search_tokens = iter(f"missing-{index}" for index in range(warmups + repeats))

    def filter_and_materialize() -> None:
        workflow_proxy.set_search(next(search_tokens))
        workflow_proxy.rowCount()

    filter_measurement = _measure(
        "workflow_proxy_filter_missing_text",
        size,
        filter_and_materialize,
        warmups=warmups,
        repeats=repeats,
    )
    tender_measurement = _measure(
        "dashboard_tender_model_reset",
        size,
        lambda: tender_model.set_tenders(tenders),
        warmups=warmups,
        repeats=repeats,
    )
    return [workflow_measurement, filter_measurement, tender_measurement]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", nargs="+", type=int, default=DEFAULT_SIZES)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--repeats", type=int, default=9)
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
            "data_generation_included": False,
            "pass_thresholds": None,
        },
        "measurements": [asdict(item) for item in measurements],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
