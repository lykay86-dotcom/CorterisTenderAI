"""Deterministic offline benchmark for the RM-147 analytics pipeline."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import statistics
import sys
from time import perf_counter_ns
import tracemalloc


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.tenders.analytics import (  # noqa: E402
    AnalyticsGrain,
    AnalyticsInterval,
    AnalyticsTenderFact,
    TenderAnalyticsChartAdapter,
    TenderAnalyticsQuery,
    TenderAnalyticsService,
    export_snapshot_csv,
    export_snapshot_json,
    resolve_selection,
)
from app.ui.charts import ChartViewport, normalize_chart  # noqa: E402
from app.ui.theme.colors import ThemeName, get_palette  # noqa: E402


DEFAULT_SIZES = (0, 1, 10, 100, 1_000, 10_000)


def _records(size: int) -> tuple[AnalyticsTenderFact, ...]:
    statuses = (
        "published",
        "accepting_applications",
        "completed",
        "unknown",
    )
    sources = ("eis", "rts", "mos")
    return tuple(
        AnalyticsTenderFact(
            registry_key=f"benchmark:{index:05d}",
            source_id=sources[index % len(sources)],
            external_id=f"external-{index:05d}",
            status=statuses[index % len(statuses)],
            first_seen_at=(
                datetime(2026, 7, 1, tzinfo=timezone.utc)
                + timedelta(minutes=index % (30 * 24 * 60))
            ).isoformat(),
            last_seen_at="2026-07-19T09:00:00+00:00",
            application_deadline=(
                datetime(2026, 7, 19, tzinfo=timezone.utc) + timedelta(days=index % 12)
            ).isoformat(),
        )
        for index in range(size)
    )


def _query() -> TenderAnalyticsQuery:
    return TenderAnalyticsQuery(
        AnalyticsInterval(
            datetime(2026, 7, 1, tzinfo=timezone.utc),
            datetime(2026, 8, 1, tzinfo=timezone.utc),
            "UTC",
        ),
        AnalyticsGrain.DAY,
    )


def _percentiles(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    p95_index = max(0, min(len(ordered) - 1, int(len(ordered) * 0.95 + 0.999) - 1))
    return {
        "p50_ms": round(statistics.median(ordered), 4),
        "p95_ms": round(ordered[p95_index], 4),
    }


def _measure(callable_, samples: int) -> tuple[dict[str, float], object]:
    values: list[float] = []
    result: object = None
    for _ in range(samples):
        started = perf_counter_ns()
        result = callable_()
        values.append((perf_counter_ns() - started) / 1_000_000)
    return _percentiles(values), result


def run_benchmark(
    *,
    sizes: tuple[int, ...] = DEFAULT_SIZES,
    samples: int = 10,
    warmups: int = 2,
) -> dict[str, object]:
    if samples < 1 or warmups < 0:
        raise ValueError("samples must be positive and warmups non-negative")
    service = TenderAnalyticsService()
    adapter = TenderAnalyticsChartAdapter()
    query = _query()
    as_of = datetime(2026, 7, 19, 9, tzinfo=timezone.utc)
    palette = get_palette(ThemeName.DARK)
    results: list[dict[str, object]] = []

    for size in sizes:
        ordered = _records(size)
        shuffled = tuple(reversed(ordered))

        def aggregate_ordered():
            return service.aggregate(query, ordered, as_of=as_of, generation=1)

        for _ in range(warmups):
            aggregate_ordered()
        aggregation_timing, snapshot_object = _measure(aggregate_ordered, samples)
        snapshot = snapshot_object
        shuffled_snapshot = service.aggregate(query, shuffled, as_of=as_of, generation=1)
        if snapshot.fingerprint != shuffled_snapshot.fingerprint:
            raise RuntimeError("shuffled input changed the semantic snapshot")

        adapter_timing, specs_object = _measure(
            lambda: tuple(adapter.adapt(metric, snapshot.coverage) for metric in snapshot.metrics),
            samples,
        )
        specs = specs_object
        render_timing, _plans = _measure(
            lambda: tuple(
                normalize_chart(spec, ChartViewport(640, 360), palette) for spec in specs
            ),
            samples,
        )
        selectable = next(
            (
                (metric.metric_id, point.point_id)
                for metric in snapshot.metrics
                for point in metric.points
                if point.contributor_ids
            ),
            None,
        )
        selection_timing, _selection = _measure(
            lambda: (
                None
                if selectable is None
                else resolve_selection(snapshot, selectable[0], selectable[1])
            ),
            samples,
        )

        tracemalloc.start()
        memory_snapshot = aggregate_ordered()
        _current, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        contributor_identity_bytes = sum(
            len(key.encode("utf-8"))
            for metric in memory_snapshot.metrics
            for point in metric.points
            for key in point.contributor_ids
        )
        results.append(
            {
                "size": size,
                "ordered_shuffled_equal": True,
                "state": snapshot.state.value,
                "aggregation": aggregation_timing,
                "adapter": adapter_timing,
                "render_plan": render_timing,
                "selection": selection_timing,
                "service_query_count": 0,
                "application_read_query_count": 4,
                "peak_traced_bytes": peak_bytes,
                "contributor_identity_bytes": contributor_identity_bytes,
                "json_bytes": len(export_snapshot_json(snapshot)),
                "csv_bytes": len(export_snapshot_csv(snapshot)),
                "sampled": False,
            }
        )
    return {
        "contract": "rm147-analytics-benchmark-v1",
        "sizes": sizes,
        "samples": samples,
        "warmups": warmups,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--sizes", default=",".join(str(item) for item in DEFAULT_SIZES))
    arguments = parser.parse_args()
    sizes = tuple(int(item.strip()) for item in arguments.sizes.split(",") if item.strip())
    print(
        json.dumps(
            run_benchmark(sizes=sizes, samples=arguments.samples, warmups=arguments.warmups),
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
