"""Static cross-stage, frozen and migration boundaries of RM-155."""

from __future__ import annotations

from pathlib import Path

from app.core.frozen_self_test import DEFAULT_REQUIRED_MODULES


ROOT = Path(__file__).parents[1]


def test_frozen_self_test_keeps_current_analytics_and_chart_owners_only() -> None:
    assert "app.tenders.analytics" in DEFAULT_REQUIRED_MODULES
    assert "app.ui.charts" in DEFAULT_REQUIRED_MODULES
    assert "app.ui.main_window" not in DEFAULT_REQUIRED_MODULES


def test_cleanup_changes_no_schema_setting_route_or_dependency_contract() -> None:
    audit = (ROOT / "docs" / "RM-155_FINAL_CLEANUP_AUDIT.md").read_text(encoding="utf-8")
    matrix = (ROOT / "docs" / "RM-155_SETTINGS_ACTION_ROUTE_MATRIX.md").read_text(encoding="utf-8")
    rollback = (ROOT / "docs" / "RM-155_ROLLBACK_PLAN.md").read_text(encoding="utf-8")
    assert "A database migration is neither required nor authorized" in audit
    assert "No UI/settings migration is required" in matrix
    assert "no data\nconversion" in rollback


def test_decision_integrity_is_an_explicit_publication_stop_condition() -> None:
    gate = (ROOT / "docs" / "RM-155_CROSS_STAGE_GATE.md").read_text(encoding="utf-8")
    assert "RM-107 score/recommendation/critical stop-factor priority" in gate
    assert "Any changed\ndecision payload" in gate
