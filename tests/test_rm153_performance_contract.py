from __future__ import annotations

import json
from pathlib import Path

from scripts.benchmark_rm153_ui import _MemorySettings, _percentile_95


ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / "docs" / "RM-153_PERFORMANCE_BASELINE.json"
POST_PATH = ROOT / "docs" / "RM-153_PERFORMANCE_POST.json"
RESOURCE_POST_PATH = ROOT / "docs" / "RM-153_RESOURCE_POST.json"
BASELINE_SHA = "1c227c323c0e9912f9a8f44dc859703e2d3fcd36"
POST_SHA = "2c6c7cefbc853bc3a20d1020cbe56b6feda60e5d"

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


def test_rm153_post_p95_passes_guards_and_profiled_targets() -> None:
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    post = json.loads(POST_PATH.read_text(encoding="utf-8"))
    baseline_p95 = {item["scenario"]: item["p95_ms"] for item in baseline["measurements"]}
    post_p95 = {item["scenario"]: item["p95_ms"] for item in post["measurements"]}
    ceilings = {
        "shell_construct": 1_230.0,
        "first_paint": 260.0,
        "shell_shutdown": 12.0,
        "page_switch": 55.0,
        "dashboard_snapshot_update": 66.0,
        "theme_switch": 820.0,
        "table_filter": 155.0,
        "chart_update": 50.0,
    }

    assert post["baseline"] == "post-implementation"
    assert post["measurement_head"] == POST_SHA
    assert post["method"]["samples"] == 20
    assert post["resource_cycles"]["cycles"] == 0
    assert post_p95.keys() == ceilings.keys()
    assert all(post_p95[scenario] <= ceiling for scenario, ceiling in ceilings.items())
    assert post_p95["shell_construct"] <= baseline_p95["shell_construct"] * 0.8
    assert post_p95["theme_switch"] <= baseline_p95["theme_switch"] * 0.8


def test_rm153_fresh_resource_post_has_no_positive_owner_growth() -> None:
    post = json.loads(RESOURCE_POST_PATH.read_text(encoding="utf-8"))
    resources = post["resource_cycles"]

    assert post["baseline"] == "post-implementation"
    assert post["measurement_head"] == POST_SHA
    assert post["method"]["samples"] == 1
    assert post["method"]["warmups"] == 0
    assert resources["cycles"] == 25
    assert all(growth <= 0 for growth in resources["growth"].values())
    assert resources["tracemalloc_current_bytes"] <= 64 * 1024
    assert resources["tracemalloc_peak_bytes"] <= 128 * 1024
