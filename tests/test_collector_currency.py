"""Tests for auditable offline currency conversion."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.tenders.collector.currency import (
    CurrencyRateUnavailableError,
    ExchangeRateBook,
    ExchangeRateQuote,
)
from app.tenders.models import TenderMoney


def _quote(
    *,
    base: str = "USD",
    quote: str = "RUB",
    rate: str = "90.125",
    effective_date: date = date(2026, 7, 10),
) -> ExchangeRateQuote:
    return ExchangeRateQuote(
        base_currency=base,
        quote_currency=quote,
        rate=rate,
        effective_date=effective_date,
        source="Банк России",
        retrieved_at="2026-07-10T08:30:00+03:00",
        source_url="https://www.cbr.ru/currency_base/daily/",
    )


def test_direct_conversion_preserves_audit_values() -> None:
    quote = _quote()
    book = ExchangeRateBook((quote,))

    result = book.convert(
        TenderMoney.from_value("100.01", currency="USD"),
        "RUB",
        as_of=date(2026, 7, 12),
    )

    assert result.original.amount == Decimal("100.01")
    assert result.original.currency == "USD"
    assert result.unrounded_amount == Decimal("9013.40125")
    assert result.converted.amount == Decimal("9013.40")
    assert result.converted.currency == "RUB"
    assert result.applied_rate == Decimal("90.125")
    assert result.quote is quote
    assert not result.inverted
    assert "Банк России" in result.audit_text()


def test_inverse_conversion_is_explicit_and_reproducible() -> None:
    result = ExchangeRateBook((_quote(),)).convert(
        TenderMoney.from_value("9012.50", currency="RUB"),
        "USD",
        as_of=date(2026, 7, 10),
    )

    assert result.converted.amount == Decimal("100.00")
    assert result.inverted
    assert result.applied_rate == Decimal("1") / Decimal("90.125")
    assert "обратный курс" in result.audit_text()


def test_future_and_stale_quotes_are_not_used() -> None:
    book = ExchangeRateBook((_quote(),), max_age_days=2)
    money = TenderMoney.from_value("100", currency="USD")

    with pytest.raises(CurrencyRateUnavailableError):
        book.convert(money, "RUB", as_of=date(2026, 7, 9))

    with pytest.raises(CurrencyRateUnavailableError):
        book.convert(money, "RUB", as_of=date(2026, 7, 13))


def test_quote_json_round_trip_and_fingerprint_are_stable() -> None:
    quote = _quote(base="eur", rate="100.50")
    restored = ExchangeRateQuote.from_dict(quote.to_dict())

    assert restored == quote
    assert ExchangeRateBook((quote,)).fingerprint == ExchangeRateBook((restored,)).fingerprint


def test_quote_requires_positive_rate_source_and_timezone() -> None:
    with pytest.raises(ValueError):
        _quote(rate="0")

    with pytest.raises(ValueError):
        ExchangeRateQuote(
            base_currency="USD",
            quote_currency="RUB",
            rate="90",
            effective_date=date(2026, 7, 10),
            source="",
            retrieved_at="2026-07-10T08:30:00+03:00",
        )

    with pytest.raises(ValueError):
        ExchangeRateQuote(
            base_currency="USD",
            quote_currency="RUB",
            rate="90",
            effective_date=date(2026, 7, 10),
            source="Банк России",
            retrieved_at="2026-07-10T08:30:00",
        )
