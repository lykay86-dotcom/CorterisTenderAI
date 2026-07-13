from __future__ import annotations
from dataclasses import dataclass


@dataclass(slots=True)
class EstimateRow:
    name: str
    quantity: float = 1
    unit: str = "шт."
    cost: float = 0
    markup_percent: float = 30
    vat_percent: float = 22

    @property
    def cost_total(self):
        return round(self.quantity * self.cost, 2)

    @property
    def price_without_vat(self):
        return round(self.cost_total * (1 + self.markup_percent / 100), 2)

    @property
    def vat_amount(self):
        return round(self.price_without_vat * self.vat_percent / 100, 2)

    @property
    def price_with_vat(self):
        return round(self.price_without_vat + self.vat_amount, 2)


def totals(rows: list[EstimateRow]) -> dict:
    cost = round(sum(x.cost_total for x in rows), 2)
    net = round(sum(x.price_without_vat for x in rows), 2)
    vat = round(sum(x.vat_amount for x in rows), 2)
    gross = round(net + vat, 2)
    profit = round(net - cost, 2)
    margin = round(profit / net * 100, 2) if net else 0
    return {
        "cost": cost,
        "net": net,
        "vat": vat,
        "gross": gross,
        "profit": profit,
        "margin": margin,
    }
