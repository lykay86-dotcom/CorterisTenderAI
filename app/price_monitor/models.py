from __future__ import annotations
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(slots=True)
class PriceOffer:
    supplier: str
    brand: str
    model: str
    unit_price: float
    currency: str = "RUB"
    vat_included: bool = True
    vat_percent: float = 22.0
    delivery_cost: float = 0.0
    discount_percent: float = 0.0
    minimum_order_qty: float = 1.0
    stock: float = 0.0
    lead_time_days: int = 0
    warranty_months: int = 0
    official_supply: bool = False
    source: str = "Ручной ввод"
    source_url: str = ""
    article: str = ""
    category: str = ""
    characteristics: dict[str, str] = field(default_factory=dict)
    certificate_available: bool = False
    checked_at: str = field(default_factory=utc_now_iso)

    @property
    def key(self) -> str:
        return f"{self.supplier}|{self.brand}|{self.model}|{self.article}|{self.source}".lower()

    def net_unit_price(self) -> float:
        price = max(0.0, self.unit_price) * (1 - max(0.0, self.discount_percent) / 100)
        if self.vat_included and self.vat_percent > 0:
            price /= 1 + self.vat_percent / 100
        return round(price, 2)

    def total_cost(self, quantity: float, target_vat_percent: float = 22.0) -> dict[str, float]:
        billable_qty = max(quantity, self.minimum_order_qty, 0)
        net_goods = self.net_unit_price() * billable_qty
        delivery_net = self.delivery_cost
        if self.vat_included and self.vat_percent > 0:
            delivery_net /= 1 + self.vat_percent / 100
        total_net = round(net_goods + delivery_net, 2)
        vat = round(total_net * target_vat_percent / 100, 2)
        return {
            "billable_quantity": billable_qty,
            "goods_net": round(net_goods, 2),
            "delivery_net": round(delivery_net, 2),
            "total_net": total_net,
            "vat": vat,
            "total_gross": round(total_net + vat, 2),
            "unit_effective_net": round(total_net / quantity, 2) if quantity else 0.0,
        }

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class TenderRequirement:
    name: str
    quantity: float = 1.0
    unit: str = "шт."
    required_brand: str = ""
    required_model: str = ""
    allow_equivalent: bool = True
    max_lead_time_days: int = 0
    min_warranty_months: int = 0
    required_characteristics: dict[str, str] = field(default_factory=dict)
    require_certificate: bool = False
    require_official_supply: bool = False


@dataclass(slots=True)
class MatchResult:
    offer: PriceOffer
    requirement: TenderRequirement
    compliant: bool
    confidence: float
    reasons: list[str]
    neutral_notes: list[str]
    total: dict[str, float]

    @property
    def rank_key(self) -> tuple:
        return (
            0 if self.compliant else 1,
            self.total.get("total_net", float("inf")),
            -self.confidence,
        )
