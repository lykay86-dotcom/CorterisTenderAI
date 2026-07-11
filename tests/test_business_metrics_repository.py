"""Tests for persistent business workflow metrics."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.repositories.business_metrics import (
    BusinessMetricsRepository,
    BusinessStatus,
)


def test_records_are_persisted_and_upserted(tmp_path) -> None:
    path = tmp_path / "business.json"
    repository = BusinessMetricsRepository(path)

    first = repository.record_estimate(
        10,
        {
            "total": 1_220_000,
            "profit": 220_000,
            "margin_percent": 18,
        },
    )
    second = repository.record_estimate(
        10,
        {
            "total": 1_400_000,
            "profit": 280_000,
            "margin_percent": 20,
        },
        status=BusinessStatus.REVIEW,
    )

    assert first.id == second.id
    loaded = BusinessMetricsRepository(path).list_records()
    assert len(loaded) == 1
    assert loaded[0].profit == 280_000


def test_summary_counts_real_workflow_records(tmp_path) -> None:
    repository = BusinessMetricsRepository(
        tmp_path / "business.json"
    )
    repository.record_estimate(
        1,
        {"total": 500_000, "profit": 100_000},
        status=BusinessStatus.DRAFT,
    )
    repository.record_proposal(
        1,
        total=500_000,
        profit=100_000,
        status=BusinessStatus.READY,
    )
    repository.record_project(
        2,
        title="Монтаж видеонаблюдения",
        status=BusinessStatus.ACTIVE,
        total=2_000_000,
        expected_profit=400_000,
    )

    summary = repository.summary(
        today=date(2026, 7, 11)
    )

    assert summary.estimates_in_work == 1
    assert summary.proposals_in_work == 1
    assert summary.active_projects == 1
    assert summary.potential_profit == Decimal("500000")
    assert summary.profit_sources == 2


def test_project_profit_replaces_estimate_for_same_tender(
    tmp_path,
) -> None:
    repository = BusinessMetricsRepository(
        tmp_path / "business.json"
    )
    repository.record_estimate(
        7,
        {"total": 1_000_000, "profit": 200_000},
    )
    repository.record_project(
        7,
        title="Проект",
        status=BusinessStatus.INSTALLATION,
        expected_profit=260_000,
    )

    summary = repository.summary()

    assert summary.potential_profit == Decimal("260000")
    assert summary.profit_sources == 1


def test_blocked_and_near_due_records_require_attention(
    tmp_path,
) -> None:
    repository = BusinessMetricsRepository(
        tmp_path / "business.json"
    )
    repository.record_proposal(
        1,
        status=BusinessStatus.BLOCKED,
    )
    repository.record_project(
        2,
        title="Проект",
        status=BusinessStatus.ACTIVE,
        due_date="13.07.2026",
    )

    summary = repository.summary(
        today=date(2026, 7, 11)
    )

    assert summary.attention == 2
