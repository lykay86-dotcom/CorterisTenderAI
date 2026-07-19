"""One parsing, validation, rounding and formatting owner for RM-148."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from typing import Final

from app.financial.contracts import CurrencyCode, FinancialValueState, MoneyAmount
from app.financial.errors import FinancialPrecisionError, FinancialRangeError


MONEY_QUANTUM: Final = Decimal("0.01")
PERCENTAGE_QUANTUM: Final = Decimal("0.01")
MAX_MONEY: Final = Decimal("999999999999.99")
MAX_MARGIN: Final = Decimal("1000.00")

_PLAIN_DECIMAL = re.compile(r"^[+-]?\d+(?:[.,]\d+)?$")
_GROUPED_DECIMAL = re.compile(r"^[+-]?\d{1,3}(?:[ \u00a0]\d{3})+(?:[.,]\d+)?$")


def _fraction_digits(value: Decimal) -> int:
    return max(0, -value.as_tuple().exponent)


def quantize_money(value: Decimal) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise TypeError("money rounding requires a finite Decimal")
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def quantize_percentage(value: Decimal) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise TypeError("percentage rounding requires a finite Decimal")
    return value.quantize(PERCENTAGE_QUANTUM, rounding=ROUND_HALF_UP)


def canonical_money(value: Decimal) -> str:
    rounded = quantize_money(value)
    if rounded == 0:
        rounded = Decimal("0.00")
    return format(rounded, ".2f")


def canonical_percentage(value: Decimal) -> str:
    rounded = quantize_percentage(value)
    if rounded == 0:
        rounded = Decimal("0.00")
    return format(rounded, ".2f")


def _invalid(issue: str, currency: CurrencyCode) -> MoneyAmount:
    return MoneyAmount(None, currency, FinancialValueState.INVALID, issue)


def parse_money(
    value: object,
    *,
    currency: CurrencyCode = CurrencyCode.RUB,
    strict_scale: bool = True,
) -> MoneyAmount:
    if not isinstance(currency, CurrencyCode):
        raise TypeError("currency must be CurrencyCode")
    if isinstance(value, MoneyAmount):
        return value
    if value is None:
        return MoneyAmount(None, currency, FinancialValueState.MISSING)
    if isinstance(value, bool) or isinstance(value, float):
        return _invalid("binary_float_not_allowed", currency)

    if isinstance(value, Decimal):
        amount = value
    elif isinstance(value, int):
        amount = Decimal(value)
    elif isinstance(value, str):
        source = value.strip()
        if not source:
            return MoneyAmount(None, currency, FinancialValueState.MISSING)
        upper = source.upper()
        detected = currency
        if upper.endswith("RUB"):
            source = source[:-3].rstrip()
            detected = CurrencyCode.RUB
        if source.endswith("₽"):
            source = source[:-1].rstrip()
            detected = CurrencyCode.RUB
        if "." in source and "," in source:
            return _invalid("ambiguous_decimal_separator", detected)
        if "e" in source.casefold():
            return _invalid("exponent_not_allowed", detected)
        if not (_PLAIN_DECIMAL.fullmatch(source) or _GROUPED_DECIMAL.fullmatch(source)):
            return _invalid("invalid_decimal_syntax", detected)
        normalized = source.replace(" ", "").replace("\u00a0", "").replace(",", ".")
        try:
            amount = Decimal(normalized)
        except InvalidOperation:
            return _invalid("invalid_decimal", detected)
        currency = detected
    else:
        return _invalid("unsupported_input_type", currency)

    if not amount.is_finite():
        return _invalid("non_finite", currency)
    if amount < 0 or amount > MAX_MONEY:
        return MoneyAmount(None, currency, FinancialValueState.OUT_OF_RANGE, "money_out_of_range")
    if _fraction_digits(amount) > 2:
        if strict_scale:
            raise FinancialPrecisionError("money has more than two fractional digits")
        return _invalid("money_overprecision", currency)
    return MoneyAmount(amount, currency)


def require_money(value: object, *, field_name: str = "money") -> Decimal:
    parsed = parse_money(value)
    if parsed.state is FinancialValueState.OUT_OF_RANGE:
        raise FinancialRangeError(f"{field_name} is out of range")
    if not parsed.is_available or parsed.amount is None:
        raise ValueError(f"{field_name} is invalid: {parsed.issue or parsed.state.value}")
    return parsed.amount


def format_money(value: MoneyAmount, *, accessible: bool = False) -> str:
    if not isinstance(value, MoneyAmount):
        raise TypeError("value must be MoneyAmount")
    if value.amount is None:
        return "—"
    exact = canonical_money(value.amount)
    if accessible:
        return f"{exact} {value.currency.value}"
    grouped = f"{Decimal(exact):,.2f}".replace(",", " ")
    suffix = "₽" if value.currency is CurrencyCode.RUB else value.currency.value
    return f"{grouped} {suffix}"


__all__ = [
    "MAX_MARGIN",
    "MAX_MONEY",
    "MONEY_QUANTUM",
    "PERCENTAGE_QUANTUM",
    "canonical_money",
    "canonical_percentage",
    "format_money",
    "parse_money",
    "quantize_money",
    "quantize_percentage",
    "require_money",
]
