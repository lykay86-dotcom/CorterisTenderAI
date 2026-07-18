"""Reproduce the same-machine RM-140 search stabilization measurements."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import replace
import gc
import json
import os
from pathlib import Path
import platform
from statistics import median
import sys
from tempfile import TemporaryDirectory
from threading import active_count
from time import perf_counter
import tracemalloc

from app.tenders.collector.async_engine import AsyncProviderSearchEngine
from app.tenders.collector.cancellation import CollectorCancellationToken
from app.tenders.collector.deduplicator import TenderDeduplicator
from app.tenders.collector.models import CollectionRunStatus
from app.tenders.collector.normalizer import TenderNormalizer
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.models import TenderSource
from app.tenders.provider_base import TenderSearchQuery
from tests.collector_c3_helpers import make_tender
from tests.test_collector_async_engine import FakeProvider


FIXTURE_ID = "rm140-baseline-v1"
SIZES_AND_REPEATS = ((0, 12), (100, 12), (1_000, 8), (10_000, 5))


def _raw_items(raw_count: int):
    for index in range(raw_count):
        identity = index // 2
        source = TenderSource.EIS if index % 2 == 0 else TenderSource.CUSTOM
        yield make_tender(
            source=source,
            external_id=f"rm140-{index:05d}",
            procurement_number=f"RM140-{identity:05d}",
            title=f"RM-140 deterministic fixture {identity:05d}",
            customer_inn=f"77{identity:08d}",
            raw_metadata={"fixture": FIXTURE_ID},
        )


def _pipeline(raw_items):
    normalizer = TenderNormalizer()
    normalized = normalizer.normalize_many(raw_items)
    return TenderDeduplicator(normalizer).deduplicate(normalized)


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    rank = (len(ordered) - 1) * percentile
    lower = int(rank)
    upper = min(len(ordered) - 1, lower + 1)
    fraction = rank - lower
    return ordered[lower] + ((ordered[upper] - ordered[lower]) * fraction)


def _pipeline_measurements(*, quick: bool) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for raw_count, configured_repeats in SIZES_AND_REPEATS:
        repeats = 1 if quick else configured_repeats
        raw_items = tuple(_raw_items(raw_count))
        for _ in range(0 if quick else 2):
            _pipeline(raw_items)

        thread_baseline = active_count()
        timings: list[float] = []
        merged_count = 0
        for _ in range(repeats):
            started = perf_counter()
            result = _pipeline(raw_items)
            timings.append((perf_counter() - started) * 1000)
            merged_count = result.merged_count

        gc.collect()
        tracemalloc.start()
        traced = _pipeline(raw_items)
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        del traced
        rows.append(
            {
                "raw_count": raw_count,
                "merged_count": merged_count,
                "repeats": repeats,
                "p50_ms": round(median(timings), 3),
                "p95_ms": round(_percentile(timings, 0.95), 3),
                "peak_mib": round(peak_bytes / (1024 * 1024), 3),
                "thread_delta": active_count() - thread_baseline,
            }
        )
    return rows


def _history_measurements() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for raw_count in (0, 100, 1_000):
        result = _pipeline(tuple(_raw_items(raw_count)))
        with TemporaryDirectory(prefix="rm140-history-") as directory:
            repository = CollectorStateRepository(Path(directory) / "registry.sqlite3")
            repository.initialize()
            started = perf_counter()
            run_id = repository.start_run(
                TenderSearchQuery(extra={"fixture": FIXTURE_ID}),
                provider_ids=("fixture",),
            )
            repository.save_batch(run_id, result)
            repository.complete_run(run_id, status=CollectionRunStatus.COMPLETED)
            write_ms = (perf_counter() - started) * 1000

            started = perf_counter()
            stored = repository.get_run(run_id)
            outcomes = repository.list_provider_outcomes(limit=200)
            read_ms = (perf_counter() - started) * 1000
            if stored is None or outcomes:
                raise RuntimeError("history benchmark invariant failed")
        rows.append(
            {
                "raw_count": raw_count,
                "merged_count": result.merged_count,
                "write_ms": round(write_ms, 3),
                "read_ms": round(read_ms, 3),
            }
        )
    return rows


async def _cancel_measurements(*, quick: bool) -> dict[str, object]:
    timings: list[float] = []
    baseline_tasks = len(asyncio.all_tasks())
    peak_tasks = baseline_tasks
    runs = 1 if quick else 10

    class SlowProvider(FakeProvider):
        async def search(self, query, *, cancellation_token=None):
            del query
            while True:
                if cancellation_token is not None:
                    cancellation_token.throw_if_cancelled()
                await asyncio.sleep(0.01)

    for run_index in range(runs):
        providers = tuple(SlowProvider(f"slow-{index}", "slow") for index in range(10))
        providers = tuple(
            replace_provider_priority(provider, index) for index, provider in enumerate(providers)
        )
        token = CollectorCancellationToken()
        engine = AsyncProviderSearchEngine(
            providers,
            max_concurrent_providers=4,
            provider_timeout_seconds=5,
            overall_timeout_seconds=5,
        )
        task = asyncio.create_task(
            engine.search(
                TenderSearchQuery(extra={"fixture": FIXTURE_ID, "run": run_index}),
                cancellation_token=token,
            )
        )
        await asyncio.sleep(0.02)
        peak_tasks = max(peak_tasks, len(asyncio.all_tasks()))
        started = perf_counter()
        token.cancel("rm140 benchmark cancellation")
        result = await asyncio.wait_for(task, timeout=1.0)
        timings.append((perf_counter() - started) * 1000)
        if not result.cancelled:
            raise RuntimeError("cancel benchmark invariant failed")
    await asyncio.sleep(0)
    final_tasks = len(asyncio.all_tasks())
    return {
        "runs": runs,
        "baseline_tasks": baseline_tasks,
        "peak_tasks": peak_tasks,
        "final_tasks": final_tasks,
        "p50_ms": round(median(timings), 3),
        "p95_ms": round(_percentile(timings, 0.95), 3),
        "max_ms": round(max(timings), 3),
    }


def replace_provider_priority(provider: FakeProvider, priority: int) -> FakeProvider:
    provider.descriptor = replace(provider.descriptor, priority=priority)
    return provider


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    arguments = parser.parse_args()
    payload = {
        "fixture": FIXTURE_ID,
        "environment": {
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "machine": platform.machine(),
            "processor": platform.processor(),
            "logical_cpus": os.cpu_count(),
        },
        "pipeline": _pipeline_measurements(quick=arguments.quick),
        "history": _history_measurements(),
        "cancellation": asyncio.run(_cancel_measurements(quick=arguments.quick)),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
