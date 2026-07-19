"""Reproducible RM-149 detail/card performance and lifecycle measurements."""

# ruff: noqa: E402

from __future__ import annotations

from collections.abc import Mapping
import json
import os
from pathlib import Path
from statistics import median
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
import tracemalloc

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QObject, QThread, QTimer
from PySide6.QtWidgets import QApplication

from app.tenders.collector.freshness import TenderFreshnessState
from app.tenders.collector.participation_score import CorterisParticipationScore
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.collector.verification import TenderVerificationState
from app.tenders.detail import (
    TenderDetailAssembler,
    TenderIdentity,
    TenderIdentityKind,
    project_tender_card,
)
from app.tenders.tender_registry import (
    TenderRegistryOccurrence,
    TenderRegistryRecord,
    TenderRegistryRepository,
    tender_registry_key,
)
from app.ui.widgets.tender_detail import TenderDetailPanel
from tests.tender_search_ui_helpers import make_profile_run


class CountingRegistry:
    def __init__(self, owner: TenderRegistryRepository) -> None:
        self.owner = owner
        self.reads = 0

    def get_record(self, registry_key: str) -> TenderRegistryRecord | None:
        self.reads += 1
        return self.owner.get_record(registry_key)

    def list_tender_occurrences(
        self, registry_key: str, *, limit: int = 100
    ) -> tuple[TenderRegistryOccurrence, ...]:
        self.reads += 1
        return self.owner.list_tender_occurrences(registry_key, limit=limit)


class CountingState:
    def __init__(self, owner: CollectorStateRepository) -> None:
        self.owner = owner
        self.reads = 0

    def get_verification_state(self, key: str) -> TenderVerificationState | None:
        self.reads += 1
        return self.owner.get_verification_state(key)

    def get_freshness_state(
        self, key: str, *, now: str | None = None
    ) -> TenderFreshnessState | None:
        self.reads += 1
        return self.owner.get_freshness_state(key, now=now)

    def get_latest_score(self, key: str) -> CorterisParticipationScore | None:
        self.reads += 1
        return self.owner.get_latest_score(key)

    def get_latest_participation_decision_payload(self, key: str) -> Mapping[str, object] | None:
        self.reads += 1
        return self.owner.get_latest_participation_decision_payload(key)


def _percentile_95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, round(0.95 * (len(ordered) - 1)))]


def _timed(callback, *, repetitions: int) -> tuple[float, float]:
    samples = []
    for _ in range(repetitions):
        started = perf_counter()
        callback()
        samples.append((perf_counter() - started) * 1000)
    return median(samples), _percentile_95(samples)


def _object_counts(root: QObject) -> dict[str, int]:
    return {
        "qobject": len(root.findChildren(QObject)),
        "qthread": len(root.findChildren(QThread)),
        "qtimer": len(root.findChildren(QTimer)),
    }


def main() -> None:
    with TemporaryDirectory(prefix="rm149-benchmark-") as directory:
        path = Path(directory) / "registry.sqlite3"
        run = make_profile_run()
        repository = TenderRegistryRepository(path)
        repository.record_profile_run(run, run_id="benchmark-run")
        state = CollectorStateRepository(path)
        key = tender_registry_key(run.result.filter_result.accepted[0].tender)
        identity = TenderIdentity(TenderIdentityKind.REGISTRY, key)
        counting_registry = CountingRegistry(repository)
        counting_state = CountingState(state)
        assembler = TenderDetailAssembler(counting_registry, counting_state)

        cold_started = perf_counter()
        snapshot = assembler.assemble(identity)
        cold_ms = (perf_counter() - cold_started) * 1000
        cold_reads = counting_registry.reads + counting_state.reads

        reads_before = counting_registry.reads + counting_state.reads
        warm_p50, warm_p95 = _timed(lambda: assembler.assemble(identity), repetitions=20)
        warm_reads = counting_registry.reads + counting_state.reads - reads_before

        projection_results: dict[str, dict[str, float | int]] = {}
        for size in (0, 1, 100, 1_000, 10_000):
            tracemalloc.start()

            def project_batch() -> None:
                for _ in range(size):
                    project_tender_card(snapshot)

            p50, p95 = _timed(project_batch, repetitions=5)
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            projection_results[str(size)] = {
                "p50_ms": round(p50, 3),
                "p95_ms": round(p95, 3),
                "peak_bytes": peak,
                "repository_reads": 0,
            }

        app = QApplication.instance() or QApplication([])
        panel = TenderDetailPanel()
        panel.set_snapshot(snapshot)
        app.processEvents()
        before = _object_counts(panel)
        publish_p50, publish_p95 = _timed(
            lambda: (panel.set_snapshot(snapshot), app.processEvents()),
            repetitions=25,
        )
        after = _object_counts(panel)

        result = {
            "contract": snapshot.contract_version,
            "first_detail_assembly": {
                "elapsed_ms": round(cold_ms, 3),
                "logical_repository_reads": cold_reads,
                "history_items": len(snapshot.history),
            },
            "warm_detail_assembly_20": {
                "p50_ms": round(warm_p50, 3),
                "p95_ms": round(warm_p95, 3),
                "logical_repository_reads": warm_reads,
                "reads_per_assembly": warm_reads / 20,
            },
            "card_projection_batches": projection_results,
            "snapshot_republication_25": {
                "p50_ms": round(publish_p50, 3),
                "p95_ms": round(publish_p95, 3),
                "before": before,
                "after": after,
                "growth": {name: after[name] - before[name] for name in before},
                "repository_reads": 0,
            },
        }
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
