"""Reproducible pre/post RM-151 operation measurements without time gates."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
import gc
import json
from pathlib import Path
from platform import platform, python_version
import statistics
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter_ns
import tracemalloc
from typing import Final


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.tenders.collector.notifications import (  # noqa: E402
    CollectorNotification,
    CollectorNotificationKind,
    CollectorNotificationRepository,
)
from app.tenders.collector.search_errors import safe_search_error_fields  # noqa: E402


DEFAULT_SIZES: Final[tuple[int, ...]] = (0, 1, 100, 1_000, 10_000)
MALICIOUS_UNIT: Final[str] = (
    "RM151_BENCH_SECRET C:\\Users\\private\\report.txt "
    "https://example.invalid/?token=secret <b>unsafe</b>\u202e"
)


@dataclass(frozen=True, slots=True)
class Measurement:
    scenario: str
    events: int
    repeats: int
    p50_ms: float
    p95_ms: float
    minimum_ms: float
    maximum_ms: float
    peak_bytes: int
    output_count: int
    output_characters: int


def _git_head() -> str:
    completed = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _percentile_95(values: Sequence[float]) -> float:
    ordered = sorted(values)
    rank = max(0, int((len(ordered) * 0.95) + 0.999999) - 1)
    return ordered[rank]


def _measure(
    scenario: str,
    events: int,
    operation: Callable[[], tuple[int, int]],
    *,
    warmups: int,
    repeats: int,
) -> Measurement:
    for _ in range(warmups):
        operation()

    durations: list[float] = []
    output_count = 0
    output_characters = 0
    for _ in range(repeats):
        started = perf_counter_ns()
        output_count, output_characters = operation()
        durations.append((perf_counter_ns() - started) / 1_000_000)

    gc.collect()
    tracemalloc.start()
    operation()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return Measurement(
        scenario=scenario,
        events=events,
        repeats=repeats,
        p50_ms=round(statistics.median(durations), 3),
        p95_ms=round(_percentile_95(durations), 3),
        minimum_ms=round(min(durations), 3),
        maximum_ms=round(max(durations), 3),
        peak_bytes=peak,
        output_count=output_count,
        output_characters=output_characters,
    )


def _notification(index: int) -> CollectorNotification:
    return CollectorNotification(
        id=f"run-151:event-{index}",
        created_at=f"2026-07-20T12:{index % 60:02d}:{index % 60:02d}+03:00",
        title="Benchmark",
        message=f"Collector event {index}",
        kind=CollectorNotificationKind.INFO,
        run_id="run-151",
    )


def benchmark_size(size: int, *, warmups: int, repeats: int) -> list[Measurement]:
    payload = MALICIOUS_UNIT * size

    def safe_projection() -> tuple[int, int]:
        code, message = safe_search_error_fields(payload)
        return 1, len(code) + len(message)

    projection = _measure(
        "legacy_safe_search_error_projection",
        size,
        safe_projection,
        warmups=warmups,
        repeats=repeats,
    )

    events = tuple(_notification(index) for index in range(size))
    with TemporaryDirectory(prefix="rm151-benchmark-", dir=ROOT) as directory:
        repository = CollectorNotificationRepository(
            Path(directory) / "collector_notifications.json"
        )

        def insert_dedupe_read() -> tuple[int, int]:
            repository.clear()
            repository.add_many(events)
            stored = repository.list_notifications()
            return len(stored), sum(len(item.message) for item in stored)

        notification = _measure(
            "legacy_notification_insert_dedupe_read",
            size,
            insert_dedupe_read,
            warmups=warmups,
            repeats=repeats,
        )

    return [projection, notification]


def _duplicate_measurement(*, warmups: int, repeats: int) -> Measurement:
    duplicate = _notification(0)
    duplicates = (duplicate,) * 1_000
    with TemporaryDirectory(prefix="rm151-duplicates-", dir=ROOT) as directory:
        repository = CollectorNotificationRepository(Path(directory) / "notifications.json")

        def operation() -> tuple[int, int]:
            repository.clear()
            repository.add_many(duplicates)
            stored = repository.list_notifications()
            return len(stored), sum(len(item.message) for item in stored)

        return _measure(
            "legacy_notification_1000_duplicates",
            1_000,
            operation,
            warmups=warmups,
            repeats=repeats,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", nargs="+", type=int, default=DEFAULT_SIZES)
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--production-baseline", default=_git_head())
    parser.add_argument("--label", default="pre-implementation")
    arguments = parser.parse_args()
    if arguments.warmups < 0 or arguments.repeats < 1:
        parser.error("warmups must be >= 0 and repeats must be >= 1")
    if any(size < 0 for size in arguments.sizes):
        parser.error("sizes must be >= 0")

    measurements = [
        measurement
        for size in arguments.sizes
        for measurement in benchmark_size(
            size,
            warmups=arguments.warmups,
            repeats=arguments.repeats,
        )
    ]
    measurements.append(
        _duplicate_measurement(warmups=arguments.warmups, repeats=arguments.repeats)
    )
    payload = {
        "baseline": arguments.label,
        "measurement_head": _git_head(),
        "production_baseline_commit": arguments.production_baseline,
        "environment": {
            "platform": platform(),
            "python": python_version(),
        },
        "method": {
            "clock": "perf_counter_ns",
            "warmups": arguments.warmups,
            "repeats": arguments.repeats,
            "sizes": arguments.sizes,
            "pass_thresholds": None,
            "peak_allocation": "separate tracemalloc sample after timed samples",
            "notification_repository_cap": 200,
            "announcement_owner_available": False,
            "qt_object_delta_measured_by_characterization": True,
            "known_gap": (
                "The pre-change repository has no canonical operation episode or "
                "announcement coalescer; those counts are therefore unavailable."
            ),
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
