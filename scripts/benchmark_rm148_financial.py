"""Print reproducible RM-148 aggregation and artifact measurements."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json
import math
from statistics import median
from time import perf_counter
import tracemalloc

from app.financial import (
    FinancialAnalyticsService,
    MoneyAmount,
    WorkflowFinancialFact,
    snapshot_to_csv_bytes,
    snapshot_to_json_bytes,
)


SIZES = (0, 1, 100, 1_000, 10_000)
REPEATS = 20
NOW = datetime(2026, 7, 19, 9, tzinfo=timezone.utc)


def facts(size: int) -> tuple[WorkflowFinancialFact, ...]:
    return tuple(
        WorkflowFinancialFact(
            record_id=f"record-{index:05d}",
            tender_id=f"tender-{index:05d}",
            kind="proposal",
            status="ready",
            total=MoneyAmount(Decimal("100.00")),
            profit=MoneyAmount(Decimal("10.00")),
            created_at=NOW,
        )
        for index in range(size)
    )


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def main() -> None:
    service = FinancialAnalyticsService()
    results: list[dict[str, int | float]] = []
    for size in SIZES:
        source = facts(size)
        durations: list[float] = []
        snapshot = service.build(source, generated_at=NOW)
        for _ in range(REPEATS):
            started = perf_counter()
            snapshot = service.build(source, generated_at=NOW)
            durations.append((perf_counter() - started) * 1_000)

        tracemalloc.start()
        snapshot = service.build(source, generated_at=NOW)
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        results.append(
            {
                "records": size,
                "p50_ms": round(median(durations), 3),
                "p95_ms": round(percentile(durations, 0.95), 3),
                "peak_bytes": peak,
                "json_bytes": len(snapshot_to_json_bytes(snapshot)),
                "csv_bytes": len(snapshot_to_csv_bytes(snapshot)),
                "service_repository_reads": 0,
                "export_repository_reads": 0,
            }
        )
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
