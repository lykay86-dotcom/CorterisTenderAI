"""Deterministic aggregation and immutable financial snapshots."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import hashlib
import json

from app.financial.contracts import (
    CurrencyCode,
    FinancialAnalyticsSnapshot,
    FinancialMetricId,
    FinancialMetricValue,
    FinancialUnit,
    FinancialValueState,
    MoneyAmount,
    WorkflowFinancialFact,
)
from app.financial.decimal_codec import quantize_percentage
from app.financial.errors import FinancialCurrencyError


_INACTIVE = frozenset({"cancelled", "completed"})


class FinancialAnalyticsService:
    """Own selection, currency checks, Decimal sums, margin and fingerprints."""

    @staticmethod
    def sum_money(values: tuple[MoneyAmount, ...]) -> MoneyAmount:
        available = tuple(value for value in values if value.is_available)
        currencies = {value.currency for value in available}
        if len(currencies) > 1 or CurrencyCode.UNKNOWN in currencies:
            raise FinancialCurrencyError("money aggregation requires one known currency")
        currency = next(iter(currencies), CurrencyCode.RUB)
        return MoneyAmount(
            sum((value.amount for value in available if value.amount is not None), Decimal("0")),
            currency,
        )

    def build(
        self,
        facts: tuple[WorkflowFinancialFact, ...],
        *,
        generated_at: datetime,
    ) -> FinancialAnalyticsSnapshot:
        ordered = tuple(sorted(facts, key=lambda fact: fact.record_id))
        active = tuple(
            fact
            for fact in ordered
            if not fact.archived and fact.status.casefold() not in _INACTIVE
        )
        total_facts = tuple(fact for fact in active if fact.total.is_available)
        total_money = self.sum_money(tuple(fact.total for fact in total_facts))

        by_tender: dict[str, WorkflowFinancialFact] = {}
        for fact in active:
            if (
                not fact.profit.is_available
                or fact.profit.amount is None
                or fact.profit.amount <= 0
            ):
                continue
            current = by_tender.get(fact.tender_id)
            if current is None or (fact.kind == "project" and current.kind != "project"):
                by_tender[fact.tender_id] = fact
        profit_facts = tuple(sorted(by_tender.values(), key=lambda fact: fact.record_id))
        profit_money = self.sum_money(tuple(fact.profit for fact in profit_facts))
        compatible_margin = tuple(
            fact
            for fact in profit_facts
            if fact.total.is_available and fact.total.currency is fact.profit.currency
        )
        margin_total = self.sum_money(tuple(fact.total for fact in compatible_margin))
        margin_profit = self.sum_money(tuple(fact.profit for fact in compatible_margin))
        margin_value = None
        if (
            margin_total.amount is not None
            and margin_total.amount > 0
            and margin_profit.amount is not None
        ):
            margin_value = quantize_percentage(
                margin_profit.amount / margin_total.amount * Decimal("100")
            )

        metrics = (
            FinancialMetricValue(
                FinancialMetricId.CURRENT_TOTAL,
                "financial-current-total-v1",
                total_money.amount,
                FinancialUnit.MONEY,
                total_money.currency,
                FinancialValueState.AVAILABLE,
                tuple(fact.record_id for fact in total_facts),
            ),
            FinancialMetricValue(
                FinancialMetricId.POTENTIAL_PROFIT,
                "workflow-potential-profit-v1",
                profit_money.amount,
                FinancialUnit.MONEY,
                profit_money.currency,
                FinancialValueState.AVAILABLE,
                tuple(fact.record_id for fact in profit_facts),
            ),
            FinancialMetricValue(
                FinancialMetricId.WEIGHTED_MARGIN,
                "workflow-weighted-margin-v1",
                margin_value,
                FinancialUnit.PERCENTAGE_POINT,
                CurrencyCode.RUB,
                (
                    FinancialValueState.AVAILABLE
                    if margin_value is not None
                    else FinancialValueState.MISSING
                ),
                tuple(fact.record_id for fact in compatible_margin),
            ),
        )
        source_projection = [
            {
                "id": fact.record_id,
                "tender": fact.tender_id,
                "kind": fact.kind,
                "status": fact.status,
                "total": str(fact.total.amount) if fact.total.amount is not None else None,
                "profit": str(fact.profit.amount) if fact.profit.amount is not None else None,
                "currency": fact.total.currency.value,
                "archived": fact.archived,
            }
            for fact in ordered
        ]
        source_fingerprint = _fingerprint(source_projection)
        semantic = {
            "generated_at": generated_at.isoformat(timespec="seconds"),
            "source": source_fingerprint,
            "metrics": [_metric_projection(metric) for metric in metrics],
        }
        return FinancialAnalyticsSnapshot(
            generated_at,
            metrics,
            source_fingerprint,
            _fingerprint(semantic),
        )


def _metric_projection(metric: FinancialMetricValue) -> dict[str, object]:
    from app.financial.decimal_codec import canonical_money, canonical_percentage

    value = None
    if metric.exact_value is not None:
        value = (
            canonical_money(metric.exact_value)
            if metric.unit is FinancialUnit.MONEY
            else canonical_percentage(metric.exact_value)
        )
    return {
        "metric_id": metric.metric_id.value,
        "version": metric.version,
        "value": value,
        "unit": metric.unit.value,
        "currency": metric.currency.value if metric.currency is not None else None,
        "state": metric.state.value,
        "contributors": metric.contributor_ids,
        "excluded": metric.excluded_ids,
        "reasons": metric.exclusion_reasons,
    }


def _fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()


__all__ = ["FinancialAnalyticsService"]
