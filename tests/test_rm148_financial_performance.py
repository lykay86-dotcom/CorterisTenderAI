"""Bounded RM-148 financial aggregation performance contour."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from time import perf_counter

import pytest

from app.financial import (
    FinancialAnalyticsService,
    MoneyAmount,
    WorkflowFinancialFact,
)


@pytest.mark.parametrize("size", [0, 1, 100, 1_000, 10_000])
def test_financial_snapshot_scales_to_ten_thousand_records(size: int) -> None:
    now = datetime(2026, 7, 19, 9, tzinfo=timezone.utc)
    facts = tuple(
        WorkflowFinancialFact(
            record_id=f"record-{index:05d}",
            tender_id=f"tender-{index:05d}",
            kind="proposal",
            status="ready",
            total=MoneyAmount(Decimal("100.00")),
            profit=MoneyAmount(Decimal("10.00")),
            created_at=now,
        )
        for index in range(size)
    )

    started = perf_counter()
    snapshot = FinancialAnalyticsService().build(facts, generated_at=now)
    elapsed = perf_counter() - started

    assert snapshot.metrics[0].exact_value == Decimal(size * 100)
    assert len(snapshot.metrics[0].contributor_ids) == size
    assert elapsed < 5.0
