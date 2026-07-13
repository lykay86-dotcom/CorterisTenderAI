"""Auditable, offline currency conversion for tender evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from typing import Iterable

from app.tenders.models import (
    TenderMoney,
    normalize_currency_code,
    normalize_money_amount,
)


class CurrencyRateUnavailableError(LookupError):
    """Raised when no valid quote can support a conversion."""


@dataclass(frozen=True, slots=True)
class ExchangeRateQuote:
    """A source-backed quote expressed as quote units per base unit."""

    base_currency: str
    quote_currency: str
    rate: Decimal | int | float | str
    effective_date: date
    source: str
    retrieved_at: str
    source_url: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "base_currency",
            normalize_currency_code(self.base_currency),
        )
        object.__setattr__(
            self,
            "quote_currency",
            normalize_currency_code(self.quote_currency),
        )
        if self.base_currency == self.quote_currency:
            raise ValueError("exchange-rate currencies must differ")
        rate = normalize_money_amount(self.rate, field_name="rate")
        if rate == 0:
            raise ValueError("rate must be greater than zero")
        object.__setattr__(self, "rate", rate)
        if not self.source.strip():
            raise ValueError("exchange-rate source must not be empty")
        retrieved = _parse_timestamp(self.retrieved_at)
        object.__setattr__(
            self,
            "retrieved_at",
            retrieved.isoformat(timespec="seconds"),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "base_currency": self.base_currency,
            "quote_currency": self.quote_currency,
            "rate": str(self.rate),
            "effective_date": self.effective_date.isoformat(),
            "source": self.source,
            "retrieved_at": self.retrieved_at,
            "source_url": self.source_url,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "ExchangeRateQuote":
        return cls(
            base_currency=str(payload.get("base_currency", "")),
            quote_currency=str(payload.get("quote_currency", "")),
            rate=str(payload.get("rate", "")),
            effective_date=date.fromisoformat(str(payload.get("effective_date", ""))),
            source=str(payload.get("source", "")),
            retrieved_at=str(payload.get("retrieved_at", "")),
            source_url=str(payload.get("source_url", "")),
        )


@dataclass(frozen=True, slots=True)
class CurrencyConversion:
    """Reproducible conversion result retaining the original amount."""

    original: TenderMoney
    converted: TenderMoney
    unrounded_amount: Decimal
    applied_rate: Decimal
    quote: ExchangeRateQuote
    as_of: date
    inverted: bool = False

    def audit_text(self) -> str:
        direction = "обратный " if self.inverted else ""
        return (
            f"{self.original.amount} {self.original.currency} → "
            f"{self.converted.amount} {self.converted.currency}; "
            f"{direction}курс {self.applied_rate} на "
            f"{self.quote.effective_date.isoformat()}, "
            f"источник: {self.quote.source}"
        )


class ExchangeRateBook:
    """Immutable collection of verified quotes used without network I/O."""

    def __init__(
        self,
        quotes: Iterable[ExchangeRateQuote] = (),
        *,
        max_age_days: int = 7,
    ) -> None:
        if max_age_days < 0:
            raise ValueError("max_age_days must be non-negative")
        self.quotes = tuple(quotes)
        self.max_age_days = int(max_age_days)

    @property
    def fingerprint(self) -> str:
        payload = {
            "max_age_days": self.max_age_days,
            "quotes": [
                item.to_dict()
                for item in sorted(
                    self.quotes,
                    key=lambda quote: (
                        quote.base_currency,
                        quote.quote_currency,
                        quote.effective_date,
                        quote.retrieved_at,
                    ),
                )
            ],
        }
        rendered = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(rendered.encode("utf-8")).hexdigest()

    def convert(
        self,
        money: TenderMoney,
        target_currency: str,
        *,
        as_of: date,
    ) -> CurrencyConversion:
        target = normalize_currency_code(target_currency)
        if money.currency == target:
            raise ValueError("conversion currencies must differ")

        direct = self._latest_quote(
            money.currency,
            target,
            as_of=as_of,
        )
        inverted = False
        if direct is None:
            direct = self._latest_quote(
                target,
                money.currency,
                as_of=as_of,
            )
            inverted = direct is not None
        if direct is None:
            raise CurrencyRateUnavailableError(
                f"No valid {money.currency}/{target} quote for {as_of}"
            )

        applied_rate = Decimal("1") / direct.rate if inverted else direct.rate
        unrounded = money.amount * applied_rate
        rounded = unrounded.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        return CurrencyConversion(
            original=money,
            converted=TenderMoney(
                amount=rounded,
                currency=target,
                includes_vat=money.includes_vat,
            ),
            unrounded_amount=unrounded,
            applied_rate=applied_rate,
            quote=direct,
            as_of=as_of,
            inverted=inverted,
        )

    def _latest_quote(
        self,
        base_currency: str,
        quote_currency: str,
        *,
        as_of: date,
    ) -> ExchangeRateQuote | None:
        candidates = [
            item
            for item in self.quotes
            if item.base_currency == base_currency
            and item.quote_currency == quote_currency
            and item.effective_date <= as_of
            and (as_of - item.effective_date).days <= self.max_age_days
        ]
        return max(
            candidates,
            key=lambda item: (item.effective_date, item.retrieved_at),
            default=None,
        )


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("retrieved_at must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("retrieved_at must include a timezone")
    return parsed.astimezone(timezone.utc)


__all__ = [
    "CurrencyConversion",
    "CurrencyRateUnavailableError",
    "ExchangeRateBook",
    "ExchangeRateQuote",
]
