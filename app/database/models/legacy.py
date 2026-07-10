"""Совместимые модели MVP, переведённые на UUID."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, UUIDAuditMixin


class Tender(UUIDAuditMixin, Base):
    __tablename__ = "tenders"

    number: Mapped[str] = mapped_column(String(100), default="", index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, default="")
    platform: Mapped[str] = mapped_column(String(200), default="Ручной импорт")
    customer: Mapped[str] = mapped_column(String(500), default="", index=True)
    region: Mapped[str] = mapped_column(String(200), default="")
    law: Mapped[str] = mapped_column(String(50), default="Не определён")
    nmck: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    deadline: Mapped[str] = mapped_column(String(50), default="")
    source_dir: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(50), default="Новый", index=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    recommendation: Mapped[str] = mapped_column(String(250), default="Не анализировался")

    documents: Mapped[list["Document"]] = relationship(
        back_populates="tender", cascade="all, delete-orphan"
    )
    analyses: Mapped[list["Analysis"]] = relationship(
        back_populates="tender", cascade="all, delete-orphan"
    )


class Document(UUIDAuditMixin, Base):
    __tablename__ = "documents"

    tender_id: Mapped[str] = mapped_column(ForeignKey("tenders.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(100), default="Не определён", index=True)
    text: Mapped[str] = mapped_column(Text, default="")
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    tender: Mapped[Tender] = relationship(back_populates="documents")


class Analysis(UUIDAuditMixin, Base):
    __tablename__ = "analyses"

    tender_id: Mapped[str] = mapped_column(ForeignKey("tenders.id", ondelete="CASCADE"), index=True)
    profile_score: Mapped[int] = mapped_column(Integer, default=0)
    legal_risk: Mapped[int] = mapped_column(Integer, default=0)
    competition_risk: Mapped[int] = mapped_column(Integer, default=0)
    technical_risk: Mapped[int] = mapped_column(Integer, default=0)
    financial_risk: Mapped[int] = mapped_column(Integer, default=0)
    estimate_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    estimated_profit: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    margin_percent: Mapped[Decimal] = mapped_column(Numeric(7, 2), default=Decimal("0"))
    report: Mapped[dict] = mapped_column(JSON, default=dict)
    tender: Mapped[Tender] = relationship(back_populates="analyses")
