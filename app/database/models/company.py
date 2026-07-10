from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, UUIDAuditMixin


class Company(UUIDAuditMixin, Base):
    __tablename__ = "companies"

    full_name: Mapped[str] = mapped_column(String(300), nullable=False)
    short_name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    inn: Mapped[str] = mapped_column(String(12), default="", index=True)
    kpp: Mapped[str] = mapped_column(String(9), default="")
    ogrn: Mapped[str] = mapped_column(String(15), default="")
    legal_address: Mapped[str] = mapped_column(Text, default="")
    actual_address: Mapped[str] = mapped_column(Text, default="")
    bank_name: Mapped[str] = mapped_column(String(250), default="")
    bank_bik: Mapped[str] = mapped_column(String(9), default="")
    settlement_account: Mapped[str] = mapped_column(String(20), default="")
    correspondent_account: Mapped[str] = mapped_column(String(20), default="")
    director_name: Mapped[str] = mapped_column(String(250), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    email: Mapped[str] = mapped_column(String(250), default="")
    website: Mapped[str] = mapped_column(String(250), default="")
    tax_system: Mapped[str] = mapped_column(String(100), default="ОСНО")
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("22.00"))
    profit_mode: Mapped[str] = mapped_column(String(30), default="markup")
    profit_percent: Mapped[Decimal] = mapped_column(Numeric(7, 2), default=Decimal("30.00"))
    risk_reserve_percent: Mapped[Decimal] = mapped_column(Numeric(7, 2), default=Decimal("5.00"))
    logo_path: Mapped[str] = mapped_column(Text, default="")
    signature_path: Mapped[str] = mapped_column(Text, default="")
    stamp_path: Mapped[str] = mapped_column(Text, default="")
    licenses: Mapped[list] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
