from __future__ import annotations
from dataclasses import dataclass, asdict
from enum import StrEnum


class ProfitMode(StrEnum):
    MARKUP = "markup"
    REVENUE_MARGIN = "revenue_margin"


@dataclass(slots=True)
class EstimateItem:
    name: str
    quantity: float
    unit: str
    unit_cost: float
    markup_percent: float = 30.0

    @property
    def cost(self) -> float:
        return round(self.quantity * self.unit_cost, 2)


class EstimateCalculator:
    def calculate(
        self,
        items: list[EstimateItem],
        vat_percent: float = 22.0,
        risk_percent: float = 5.0,
        profit_percent: float = 30.0,
        profit_mode: ProfitMode | str = ProfitMode.MARKUP,
    ) -> dict:
        mode = ProfitMode(profit_mode)
        cost = round(sum(i.cost for i in items), 2)
        risk = round(cost * risk_percent / 100, 2)
        protected_cost = cost + risk
        if mode is ProfitMode.REVENUE_MARGIN:
            if profit_percent >= 100:
                raise ValueError("Целевая рентабельность должна быть меньше 100%")
            no_vat = protected_cost / (1 - profit_percent / 100)
        else:
            no_vat = protected_cost * (1 + profit_percent / 100)
        no_vat = round(no_vat, 2)
        profit = round(no_vat - protected_cost, 2)
        vat = round(no_vat * vat_percent / 100, 2)
        total = round(no_vat + vat, 2)
        revenue_margin = round(profit / no_vat * 100, 2) if no_vat else 0
        markup = round(profit / protected_cost * 100, 2) if protected_cost else 0
        priced_items = []
        ratio = no_vat / cost if cost else 0
        for item in items:
            priced_items.append(
                asdict(item)
                | {
                    "cost": item.cost,
                    "price": round(item.cost * ratio, 2),
                }
            )
        return {
            "items": priced_items,
            "cost_total": cost,
            "risk_reserve": risk,
            "protected_cost": round(protected_cost, 2),
            "profit_mode": mode.value,
            "target_profit_percent": profit_percent,
            "price_without_vat": no_vat,
            "vat_percent": vat_percent,
            "vat": vat,
            "total": total,
            "profit": profit,
            "margin_percent": revenue_margin,
            "markup_percent": markup,
            "minimum_safe_price_with_vat": total,
        }
