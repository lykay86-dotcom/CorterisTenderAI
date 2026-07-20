from __future__ import annotations

import json
from pathlib import Path

from scripts.benchmark_rm153_ui import _MemorySettings, _percentile_95


ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / "docs" / "RM-153_PERFORMANCE_BASELINE.json"
BASELINE_SHA = "1c227c323c0e9912f9a8f44dc859703e2d3fcd36"

EXPECTED_SCENARIOS = {
    "shell_construct",
    "first_paint",
    "shell_shutdown",
    "page_switch",
    "dashboard_snapshot_update",
    "theme_switch",
    "table_filter",
    "chart_update",
}


def test_rm153_baseline_is_reproducible_and_preimplementation() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))

    assert payload["baseline"] == "pre-implementation"
    assert payload["contract"] == "rm153-ui-performance-baseline-v1"
    assert payload["measurement_head"] == BASELINE_SHA
    assert payload["production_baseline_commit"] == BASELINE_SHA
    assert payload["method"] == {
        "chart_points": 1_000,
        "clock": "perf_counter_ns",
        "dashboard_rows": 1_000,
        "offline_synthetic": True,
        "pass_thresholds": None,
        "samples": 10,
        "table_rows": 10_000,
        "warmups": 2,
    }
    assert {item["scenario"] for item in payload["measurements"]} == EXPECTED_SCENARIOS
    assert all(item["samples"] == 10 for item in payload["measurements"])


def test_rm153_baseline_resource_cycle_has_no_owner_growth() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    resources = payload["resource_cycles"]

    assert resources["cycles"] == 25
    assert resources["growth"] == {
        "active_qtimer": 0,
        "python_threads": 0,
        "qobject": 0,
        "qthread": 0,
        "qtimer": 0,
    }
    assert resources["tracemalloc_current_bytes"] <= 64 * 1024
    assert resources["tracemalloc_peak_bytes"] <= 128 * 1024


def test_rm153_benchmark_settings_are_memory_only() -> None:
    first = _MemorySettings("Corteris", "CorterisTenderAI")
    second = _MemorySettings("Corteris", "CorterisTenderAI")

    first.setValue("ui/theme", "light")

    assert first.value("ui/theme", "dark") == "light"
    assert second.value("ui/theme", "dark") == "dark"


def test_rm153_p95_uses_nearest_rank_without_interpolation() -> None:
    assert _percentile_95(tuple(float(index) for index in range(1, 11))) == 10.0
    assert _percentile_95(tuple(float(index) for index in range(1, 21))) == 19.0
