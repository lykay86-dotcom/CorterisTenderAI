"""Immutable Qt-free contracts for exact workflow finance."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Final


NUMERIC_CONTRACT_VERSION: Final = "financial-numeric-v1"
SNAPSHOT_CONTRACT_VERSION: Final = "financial-analytics-v1"
MARGIN_CONTRACT_VERSION: Final = "workflow-revenue-margin-v1"


class CurrencyCode(StrEnum):
    RUB = "RUB"
    UNKNOWN = "UNKNOWN"


class FinancialUnit(StrEnum):
    MONEY = "money"
    PERCENTAGE_POINT = "percentage_point"
    COUNT = "count"
    RATIO = "ratio"


class FinancialValueState(StrEnum):
    AVAILABLE = "available"
    MISSING = "missing"
    INVALID = "invalid"
    CONFLICTED = "conflicted"
    UNSUPPORTED_CURRENCY = "unsupported_currency"
    OUT_OF_RANGE = "out_of_range"
    STALE = "stale"
    ERROR = "error"


class FinancialMetricId(StrEnum):
    CURRENT_TOTAL = "fa-01"
    POTENTIAL_PROFIT = "fa-02"
    WEIGHTED_MARGIN = "fa-03"
    FINANCIAL_FLOW = "fa-04"


def _finite_decimal(value: Decimal | None, field_name: str) -> Decimal | None:
    if value is None:
        return None
    if not isinstance(value, Decimal):
        raise TypeError(f"{field_name} must be Decimal or None")
    if not value.is_finite():
        raise ValueError(f"{field_name} must be finite")
    return value


def _aware(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


@dataclass(frozen=True, slots=True)
class MoneyAmount:
    amount: Decimal | None
    currency: CurrencyCode = CurrencyCode.RUB
    state: FinancialValueState = FinancialValueState.AVAILABLE
    issue: str = ""

    def __post_init__(self) -> None:
        _finite_decimal(self.amount, "amount")
        if not isinstance(self.currency, CurrencyCode):
            raise TypeError("currency must be CurrencyCode")
        if not isinstance(self.state, FinancialValueState):
            raise TypeError("state must be FinancialValueState")
        if not isinstance(self.issue, str):
            raise TypeError("issue must be text")
        if self.amount is None and self.state is FinancialValueState.AVAILABLE:
            object.__setattr__(self, "state", FinancialValueState.MISSING)

    @property
    def unit(self) -> FinancialUnit:
        return FinancialUnit.MONEY

    @property
    def is_available(self) -> bool:
        return self.amount is not None and self.state is FinancialValueState.AVAILABLE


@dataclass(frozen=True, slots=True)
class PercentageValue:
    value: Decimal | None
    state: FinancialValueState = FinancialValueState.AVAILABLE
    issue: str = ""

    def __post_init__(self) -> None:
        _finite_decimal(self.value, "percentage value")
        if not isinstance(self.state, FinancialValueState):
            raise TypeError("state must be FinancialValueState")
        if self.value is None and self.state is FinancialValueState.AVAILABLE:
            object.__setattr__(self, "state", FinancialValueState.MISSING)

    @property
    def unit(self) -> FinancialUnit:
        return FinancialUnit.PERCENTAGE_POINT

    @property
    def display_value(self) -> str:
        if self.value is None:
            return ""
        from app.financial.decimal_codec import canonical_percentage

        return canonical_percentage(self.value)


@dataclass(frozen=True, slots=True)
class WorkflowFinancialFact:
    record_id: str
    tender_id: str
    kind: str
    status: str
    total: MoneyAmount
    profit: MoneyAmount
    created_at: datetime | None = None
    archived: bool = False

    def __post_init__(self) -> None:
        for field_name in ("record_id", "tender_id", "kind", "status"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be non-empty text")
        if not isinstance(self.total, MoneyAmount) or not isinstance(self.profit, MoneyAmount):
            raise TypeError("total and profit must be MoneyAmount")
        if self.created_at is not None:
            _aware(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class FinancialMetricValue:
    metric_id: FinancialMetricId
    version: str
    exact_value: Decimal | None
    unit: FinancialUnit
    currency: CurrencyCode | None
    state: FinancialValueState
    contributor_ids: tuple[str, ...]
    excluded_ids: tuple[str, ...] = ()
    exclusion_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _finite_decimal(self.exact_value, "metric value")
        if tuple(sorted(set(self.contributor_ids))) != self.contributor_ids:
            raise ValueError("contributor_ids must be sorted and unique")
        if tuple(sorted(set(self.excluded_ids))) != self.excluded_ids:
            raise ValueError("excluded_ids must be sorted and unique")

    def as_money(self) -> MoneyAmount:
        if self.unit is not FinancialUnit.MONEY or self.currency is None:
            raise TypeError("metric is not money")
        return MoneyAmount(self.exact_value, self.currency, self.state)


@dataclass(frozen=True, slots=True)
class FinancialAnalyticsSnapshot:
    generated_at: datetime
    metrics: tuple[FinancialMetricValue, ...]
    source_fingerprint: str
    fingerprint: str
    contract_version: str = SNAPSHOT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _aware(self.generated_at, "generated_at")
        if self.contract_version != SNAPSHOT_CONTRACT_VERSION:
            raise ValueError("unsupported snapshot contract")
        metric_ids = tuple(metric.metric_id for metric in self.metrics)
        if len(set(metric_ids)) != len(metric_ids):
            raise ValueError("duplicate financial metric")

    def metric(self, metric_id: FinancialMetricId) -> FinancialMetricValue:
        return next(metric for metric in self.metrics if metric.metric_id is metric_id)


__all__ = [
    "MARGIN_CONTRACT_VERSION",
    "NUMERIC_CONTRACT_VERSION",
    "SNAPSHOT_CONTRACT_VERSION",
    "CurrencyCode",
    "FinancialAnalyticsSnapshot",
    "FinancialMetricId",
    "FinancialMetricValue",
    "FinancialUnit",
    "FinancialValueState",
    "MoneyAmount",
    "PercentageValue",
    "WorkflowFinancialFact",
]
