"""Measure the audited PRE-RM-156 P3 performance and lifecycle budgets."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import gc
import json
from pathlib import Path
import platform
from statistics import median
import sys
from tempfile import TemporaryDirectory
from threading import Event, Thread, active_count
from time import perf_counter

import psutil

from app.tenders.collector.async_engine import AsyncProviderSearchEngine
from app.tenders.collector.async_provider import AsyncTenderProvider
from app.tenders.collector.cancellation import CollectorCancellationToken
from app.tenders.collector.deduplicator import TenderDeduplicator
from app.tenders.collector.models import CollectionRunStatus
from app.tenders.collector.normalizer import TenderNormalizer
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.models import TenderSource
from app.tenders.provider_base import (
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderHealth,
    ProviderHealthStatus,
    TenderSearchQuery,
    TenderSearchResult,
)
from tests.collector_c3_helpers import make_tender


P1_P95_MS = 8_096.375
MAX_P95_MS = 10_000.0
MAX_REGRESSION = 0.20
MAX_RSS_DELTA = 64 * 1024 * 1024


def _raw_items():
    for index in range(10_000):
        identity = index // 2
        yield make_tender(
            source=TenderSource.EIS if index % 2 == 0 else TenderSource.CUSTOM,
            external_id=f"rm140-{index:05d}",
            procurement_number=f"RM140-{identity:05d}",
            title=f"RM-140 deterministic fixture {identity:05d}",
            customer_inn=f"77{identity:08d}",
            raw_metadata={"fixture": "rm140-baseline-v1"},
        )


def _pipeline(raw_items):
    normalizer = TenderNormalizer()
    return TenderDeduplicator(normalizer).normalize_and_deduplicate(raw_items)


@dataclass(slots=True)
class _RssSampler:
    baseline: int
    peak: int
    stop: Event
    thread: Thread

    @classmethod
    def start(cls) -> _RssSampler:
        process = psutil.Process()
        stop = Event()
        baseline = process.memory_info().rss
        sampler = cls(baseline, baseline, stop, Thread())

        def sample() -> None:
            while not stop.wait(0.01):
                sampler.peak = max(sampler.peak, process.memory_info().rss)

        sampler.thread = Thread(target=sample, name="pre-rm156-p3-rss", daemon=True)
        sampler.thread.start()
        return sampler

    def close(self) -> int:
        self.stop.set()
        self.thread.join(timeout=1.0)
        self.peak = max(self.peak, psutil.Process().memory_info().rss)
        return max(0, self.peak - self.baseline)


def _performance() -> dict[str, object]:
    raw_items = tuple(_raw_items())
    warmup = _pipeline(raw_items)
    assert warmup.raw_count == 10_000 and warmup.merged_count == 5_000
    del warmup
    gc.collect()
    sampler = _RssSampler.start()
    timings: list[float] = []
    for _ in range(5):
        started = perf_counter()
        result = _pipeline(raw_items)
        timings.append((perf_counter() - started) * 1000)
        assert result.raw_count == 10_000 and result.merged_count == 5_000
        del result
        gc.collect()
    rss_delta = sampler.close()
    ordered = sorted(timings)
    p95 = ordered[-1]  # P1 used nearest-rank p95 for n=5.
    regression = (p95 / P1_P95_MS) - 1.0
    return {
        "raw_count": 10_000,
        "merged_count": 5_000,
        "samples": 5,
        "p50_ms": round(median(timings), 3),
        "p95_nearest_rank_ms": round(p95, 3),
        "min_ms": round(min(timings), 3),
        "max_ms": round(max(timings), 3),
        "regression_ratio": round(regression, 6),
        "rss_delta_bytes": rss_delta,
        "passed": (
            p95 <= MAX_P95_MS and regression <= MAX_REGRESSION and rss_delta <= MAX_RSS_DELTA
        ),
    }


class _OnePageProvider(AsyncTenderProvider):
    contract_version = "contract-v1"
    parser_version = "parser-v1"
    connection_mode = "fixture"

    def __init__(self, *, slow: bool = False) -> None:
        self.slow = slow
        self.descriptor = ProviderDescriptor(
            id="fixture",
            display_name="Fixture",
            source=TenderSource.CUSTOM,
            homepage_url="https://example.test/",
            capabilities=ProviderCapabilities(search=True),
            implementation_status="fixture",
        )

    async def search(self, query, *, cancellation_token=None):
        if self.slow:
            while True:
                if cancellation_token is not None:
                    cancellation_token.throw_if_cancelled()
                await asyncio.sleep(0.01)
        return TenderSearchResult(
            provider_id="fixture",
            items=(
                make_tender(
                    source=TenderSource.CUSTOM,
                    external_id=str(query.extra.get("cycle", "one")),
                ),
            ),
        )

    async def get_tender(self, external_id, *, cancellation_token=None):
        del external_id, cancellation_token
        raise NotImplementedError

    async def list_documents(self, external_id, *, cancellation_token=None):
        del external_id, cancellation_token
        return ()

    async def check_health(self, *, cancellation_token=None):
        del cancellation_token
        return ProviderHealth(
            provider_id="fixture",
            status=ProviderHealthStatus.AVAILABLE,
            checked_at="2026-07-22T00:00:00+00:00",
        )


async def _resources() -> dict[str, object]:
    process = psutil.Process()
    baseline_tasks = len(asyncio.all_tasks())
    baseline_threads = active_count()
    cancellation_ms = 0.0
    with TemporaryDirectory(prefix="pre-rm156-p3-") as directory:
        root = Path(directory)
        repository = CollectorStateRepository(root / "registry.sqlite3")
        repository.initialize()
        baseline_handles = {
            item.path for item in process.open_files() if Path(item.path).is_relative_to(root)
        }
        for cycle in range(25):
            query = TenderSearchQuery(extra={"cycle": cycle})
            run_id = repository.start_run(query, provider_ids=("fixture",))
            result = await AsyncProviderSearchEngine(
                (_OnePageProvider(),), accepted_page_repository=repository
            ).search(query, run_id=run_id)
            repository.complete_run(
                run_id,
                status=CollectionRunStatus.COMPLETED,
                provider_outcomes=result.outcomes,
            )

        token = CollectorCancellationToken()
        cancellation = asyncio.create_task(
            AsyncProviderSearchEngine((_OnePageProvider(slow=True),)).search(
                TenderSearchQuery(), cancellation_token=token
            )
        )
        await asyncio.sleep(0.04)
        started = perf_counter()
        token.cancel("P3 offline cancellation measurement")
        cancelled = await asyncio.wait_for(cancellation, timeout=1.0)
        cancellation_ms = (perf_counter() - started) * 1000
        await asyncio.sleep(0)
        gc.collect()
        final_handles = {
            item.path for item in process.open_files() if Path(item.path).is_relative_to(root)
        }
        temporary_files = tuple(
            sorted(
                path.name
                for path in root.rglob("*")
                if path.is_file() and path.suffix in {".tmp", ".restore"}
            )
        )
    final_tasks = len(asyncio.all_tasks())
    final_threads = active_count()
    passed = (
        cancelled.cancelled
        and cancellation_ms <= 1_000
        and final_tasks == baseline_tasks
        and final_threads == baseline_threads
        and final_handles == baseline_handles
        and not temporary_files
    )
    return {
        "cycles": 25,
        "cancellation_ms": round(cancellation_ms, 3),
        "baseline_tasks": baseline_tasks,
        "final_tasks": final_tasks,
        "baseline_threads": baseline_threads,
        "final_threads": final_threads,
        "open_handle_growth": len(final_handles - baseline_handles),
        "temporary_files": temporary_files,
        "passed": passed,
    }


def main() -> int:
    payload = {
        "environment": {
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "machine": platform.machine(),
        },
        "performance": _performance(),
        "resources": asyncio.run(_resources()),
    }
    payload["passed"] = bool(payload["performance"]["passed"] and payload["resources"]["passed"])
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
