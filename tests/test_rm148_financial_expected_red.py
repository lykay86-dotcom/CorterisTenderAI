"""Expected-red RM-148 contract for the single financial numeric owner."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import json
import random
from zoneinfo import ZoneInfo

import pytest

from app.financial import (
    CurrencyCode,
    FinancialAnalyticsService,
    FinancialCurrencyError,
    FinancialMetricId,
    FinancialPrecisionError,
    FinancialUnit,
    FinancialValueState,
    MoneyAmount,
    WorkflowFinancialFact,
    canonical_money,
    derive_margin,
    format_money,
    parse_money,
    quantize_money,
    snapshot_to_csv_bytes,
    snapshot_to_json_bytes,
)


MOSCOW = ZoneInfo("Europe/Moscow")
NOW = datetime(2026, 7, 19, 12, 0, tzinfo=MOSCOW)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("0.01", Decimal("0.01")),
        ("0,10 ₽", Decimal("0.10")),
        ("1 000 000.00 RUB", Decimal("1000000.00")),
        ("0", Decimal("0.00")),
    ],
)
def test_money_parser_is_exact_and_locale_bounded(source: str, expected: Decimal) -> None:
    value = parse_money(source)

    assert value.amount == expected
    assert value.currency is CurrencyCode.RUB
    assert value.unit is FinancialUnit.MONEY
    assert value.state is FinancialValueState.AVAILABLE


@pytest.mark.parametrize("source", ["", "abc", "NaN", "Infinity", "1e3", "1,2.3"])
def test_money_parser_does_not_invent_zero(source: str) -> None:
    value = parse_money(source)

    assert value.amount is None
    assert value.state in {FinancialValueState.MISSING, FinancialValueState.INVALID}


def test_domain_rejects_float_and_overprecision() -> None:
    with pytest.raises(TypeError):
        MoneyAmount(0.1, CurrencyCode.RUB, FinancialValueState.AVAILABLE)  # type: ignore[arg-type]
    with pytest.raises(FinancialPrecisionError):
        parse_money("1.005", strict_scale=True)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("1.005", "1.01"),
        ("2.675", "2.68"),
        ("10.115", "10.12"),
        ("999999999.995", "1000000000.00"),
    ],
)
def test_named_money_rounding_uses_half_up(source: str, expected: str) -> None:
    assert canonical_money(quantize_money(Decimal(source))) == expected


def test_margin_is_derived_once_and_zero_total_is_missing() -> None:
    margin = derive_margin(parse_money("100.00"), parse_money("12.50"))
    undefined = derive_margin(parse_money("0.00"), parse_money("0.00"))

    assert margin.value == Decimal("12.5")
    assert margin.display_value == "12.50"
    assert margin.state is FinancialValueState.AVAILABLE
    assert undefined.value is None
    assert undefined.state is FinancialValueState.MISSING


def test_currency_mismatch_fails_closed() -> None:
    rub = parse_money("10.00")
    unknown = MoneyAmount(Decimal("5.00"), CurrencyCode.UNKNOWN)

    with pytest.raises(FinancialCurrencyError):
        FinancialAnalyticsService().sum_money((rub, unknown))


def _fact(
    record_id: str,
    tender_id: str,
    kind: str,
    total: str,
    profit: str,
    *,
    status: str = "active",
) -> WorkflowFinancialFact:
    return WorkflowFinancialFact(
        record_id=record_id,
        tender_id=tender_id,
        kind=kind,
        status=status,
        total=parse_money(total),
        profit=parse_money(profit),
        created_at=NOW,
    )


def test_snapshot_preserves_potential_profit_selection_and_weighted_margin() -> None:
    facts = (
        _fact("proposal-a", "T-1", "proposal", "100.00", "10.10", status="ready"),
        _fact("project-a", "T-1", "project", "200.00", "20.20"),
        _fact("proposal-b", "T-2", "proposal", "50.00", "15.05", status="blocked"),
        _fact("cancelled", "T-3", "proposal", "100.00", "99.00", status="cancelled"),
    )

    snapshot = FinancialAnalyticsService().build(facts, generated_at=NOW)
    total = snapshot.metric(FinancialMetricId.CURRENT_TOTAL)
    profit = snapshot.metric(FinancialMetricId.POTENTIAL_PROFIT)
    margin = snapshot.metric(FinancialMetricId.WEIGHTED_MARGIN)

    assert total.exact_value == Decimal("350.00")
    assert total.contributor_ids == ("project-a", "proposal-a", "proposal-b")
    assert profit.exact_value == Decimal("35.25")
    assert profit.contributor_ids == ("project-a", "proposal-b")
    assert margin.exact_value == Decimal("14.10")
    assert margin.unit is FinancialUnit.PERCENTAGE_POINT
    assert format_money(profit.as_money(), accessible=True) == "35.25 RUB"


def test_snapshot_and_exports_are_deterministic_under_shuffle() -> None:
    facts = [
        _fact("a", "T-1", "proposal", "0.10", "0.01", status="ready"),
        _fact("b", "T-2", "project", "0.20", "0.02"),
        _fact("c", "T-3", "estimate", "0.30", "0.03", status="review"),
    ]
    baseline = FinancialAnalyticsService().build(tuple(facts), generated_at=NOW)
    expected_json = snapshot_to_json_bytes(baseline)
    expected_csv = snapshot_to_csv_bytes(baseline)

    for seed in range(10):
        shuffled = facts.copy()
        random.Random(seed).shuffle(shuffled)
        candidate = FinancialAnalyticsService().build(tuple(shuffled), generated_at=NOW)
        assert candidate.fingerprint == baseline.fingerprint, f"seed={seed}"
        assert snapshot_to_json_bytes(candidate) == expected_json, f"seed={seed}"
        assert snapshot_to_csv_bytes(candidate) == expected_csv, f"seed={seed}"

    payload = json.loads(expected_json)
    metric = next(item for item in payload["metrics"] if item["metric_id"] == "fa-02")
    assert metric["value"] == "0.06"
    assert metric["currency"] == "RUB"
    assert metric["unit"] == "money"
