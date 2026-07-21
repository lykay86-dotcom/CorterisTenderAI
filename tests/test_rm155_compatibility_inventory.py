"""RM-155 machine-checkable inventory and consumer-map acceptance."""

from __future__ import annotations

from pathlib import Path

from scripts.check_rm155_compatibility import REQUIRED_CANDIDATES, violations


ROOT = Path(__file__).parents[1]


def test_retirement_inventory_is_complete_and_guard_is_green() -> None:
    assert len(REQUIRED_CANDIDATES) == 32
    assert violations(ROOT) == ()


def test_every_candidate_has_a_decision_and_rollback_owner() -> None:
    inventory = (ROOT / "docs" / "RM-155_COMPATIBILITY_INVENTORY.md").read_text(encoding="utf-8")
    for candidate in REQUIRED_CANDIDATES:
        row = next(line for line in inventory.splitlines() if candidate in line)
        assert any(decision in row for decision in ("REMOVE", "MIGRATE", "KEEP", "DEPRECATE"))
        assert row.count("|") >= 7


def test_consumer_map_names_each_audited_consumer_class() -> None:
    consumer_map = (ROOT / "docs" / "RM-155_CONSUMER_MAP.md").read_text(encoding="utf-8")
    for evidence_class in (
        "Production",
        "Tests",
        "History/public",
        "Frozen/settings/data",
        "Migration",
    ):
        assert evidence_class in consumer_map
