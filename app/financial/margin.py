"""The single revenue-margin formula owner."""

from __future__ import annotations

from decimal import Decimal

from app.financial.contracts import (
    FinancialValueState,
    MoneyAmount,
    PercentageValue,
)
from app.financial.decimal_codec import MAX_MARGIN


def derive_margin(total: MoneyAmount, profit: MoneyAmount) -> PercentageValue:
    if not isinstance(total, MoneyAmount) or not isinstance(profit, MoneyAmount):
        raise TypeError("margin operands must be MoneyAmount")
    if total.currency is not profit.currency:
        return PercentageValue(
            None,
            FinancialValueState.UNSUPPORTED_CURRENCY,
            "currency_mismatch",
        )
    if not total.is_available or not profit.is_available:
        state = (
            FinancialValueState.INVALID
            if FinancialValueState.INVALID in {total.state, profit.state}
            else FinancialValueState.MISSING
        )
        return PercentageValue(None, state, "operand_unavailable")
    assert total.amount is not None and profit.amount is not None
    if total.amount == 0:
        return PercentageValue(None, FinancialValueState.MISSING, "zero_total")
    value = profit.amount / total.amount * Decimal("100")
    if value < 0 or value > MAX_MARGIN:
        return PercentageValue(None, FinancialValueState.OUT_OF_RANGE, "margin_out_of_range")
    return PercentageValue(value)


__all__ = ["derive_margin"]
