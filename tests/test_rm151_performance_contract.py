"""Correctness bounds for the RM-151 deterministic benchmark artifact."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_post_implementation_artifact_covers_required_sizes_and_scenarios() -> None:
    payload = json.loads(
        (ROOT / "docs" / "RM-151_PERFORMANCE_POST.json").read_text(encoding="utf-8")
    )
    measurements = payload["measurements"]

    assert payload["baseline"] == "post-implementation"
    assert payload["method"]["sizes"] == [0, 1, 100, 1000, 10000]
    assert payload["method"]["pass_thresholds"] is None
    assert payload["method"]["announcement_owner_available"] is True
    assert payload["method"]["known_gap"] is None
    assert {item["scenario"] for item in measurements} >= {
        "canonical_safe_feedback_projection",
        "canonical_legacy_notification_adapter",
        "canonical_announcement_coalescing",
        "legacy_notification_insert_dedupe_read",
        "legacy_notification_1000_duplicates",
    }


def test_post_implementation_correctness_counts_are_bounded() -> None:
    payload = json.loads(
        (ROOT / "docs" / "RM-151_PERFORMANCE_POST.json").read_text(encoding="utf-8")
    )
    measurements = payload["measurements"]
    canonical_projection = [
        item for item in measurements if item["scenario"] == "canonical_safe_feedback_projection"
    ]
    announcements = [
        item for item in measurements if item["scenario"] == "canonical_announcement_coalescing"
    ]
    duplicate = next(
        item for item in measurements if item["scenario"] == "legacy_notification_1000_duplicates"
    )

    assert all(item["output_count"] == 1 for item in canonical_projection)
    assert len({item["output_characters"] for item in canonical_projection}) == 1
    assert all(item["output_characters"] <= 512 for item in canonical_projection)
    assert all(item["output_count"] <= 12 for item in announcements)
    assert duplicate["events"] == 1000
    assert duplicate["output_count"] == 1
