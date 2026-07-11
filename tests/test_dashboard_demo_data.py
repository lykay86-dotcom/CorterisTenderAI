"""Tests for Dashboard demonstration data."""

from __future__ import annotations

from datetime import datetime

from app.ui.dashboard.demo_data import (
    DEMO_ENVIRONMENT_VARIABLE,
    build_demo_snapshot,
    build_empty_dashboard_kpis,
    demo_mode_from_environment,
)


ANCHOR = datetime(2026, 7, 11, 10, 30)


def test_demo_snapshot_has_complete_dashboard_content() -> None:
    snapshot = build_demo_snapshot(ANCHOR)

    assert len(snapshot.kpis) == 6
    assert len(snapshot.tenders) == 5
    assert len(snapshot.recommendations) >= 4
    assert len(snapshot.activities) >= 4


def test_demo_tenders_are_clearly_synthetic() -> None:
    snapshot = build_demo_snapshot(ANCHOR)

    numbers = [tender.number for tender in snapshot.tenders]
    assert len(numbers) == len(set(numbers))
    assert all(number.startswith("DEMO-") for number in numbers)


def test_demo_priority_tender_is_deterministic() -> None:
    snapshot = build_demo_snapshot(ANCHOR)

    assert snapshot.priority_tender is not None
    assert snapshot.priority_tender.number == "DEMO-44-FZ-001"
    assert snapshot.priority_tender.score == 94


def test_demo_deadlines_are_relative_to_anchor() -> None:
    snapshot = build_demo_snapshot(ANCHOR)

    assert snapshot.tenders[0].deadline == "18.07.2026"
    assert snapshot.tenders[-1].deadline == "13.07.2026"


def test_demo_environment_flag() -> None:
    assert demo_mode_from_environment(
        {DEMO_ENVIRONMENT_VARIABLE: "1"}
    )
    assert demo_mode_from_environment(
        {DEMO_ENVIRONMENT_VARIABLE: "TRUE"}
    )
    assert not demo_mode_from_environment(
        {DEMO_ENVIRONMENT_VARIABLE: "0"}
    )


def test_empty_kpis_have_stable_order_and_zero_values() -> None:
    kpis = build_empty_dashboard_kpis()

    assert [item.key for item in kpis] == [
        "potential_profit",
        "new_tenders",
        "recommended",
        "proposals_in_work",
        "active_projects",
        "attention",
    ]
    assert kpis[1].value == "0"
    assert kpis[0].value == "0 ₽"
