from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Text, Float, DateTime, Integer, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.session import Base


class Tender(Base):
    __tablename__ = "tenders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[str] = mapped_column(String(100), default="")
    title: Mapped[str] = mapped_column(String(500))
    source_url: Mapped[str] = mapped_column(Text, default="")
    platform: Mapped[str] = mapped_column(String(200), default="Ручной импорт")
    customer: Mapped[str] = mapped_column(String(500), default="")
    region: Mapped[str] = mapped_column(String(200), default="")
    law: Mapped[str] = mapped_column(String(50), default="Не определён")
    nmck: Mapped[float] = mapped_column(Float, default=0)
    deadline: Mapped[str] = mapped_column(String(50), default="")
    source_dir: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(50), default="Новый")
    score: Mapped[int] = mapped_column(Integer, default=0)
    recommendation: Mapped[str] = mapped_column(String(250), default="Не анализировался")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    documents: Mapped[list["Document"]] = relationship(
        back_populates="tender", cascade="all, delete-orphan"
    )
    analyses: Mapped[list["Analysis"]] = relationship(
        back_populates="tender", cascade="all, delete-orphan"
    )


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    tender_id: Mapped[int] = mapped_column(ForeignKey("tenders.id"))
    name: Mapped[str] = mapped_column(String(500))
    path: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(100), default="Не определён")
    text: Mapped[str] = mapped_column(Text, default="")
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    tender: Mapped[Tender] = relationship(back_populates="documents")


class Analysis(Base):
    __tablename__ = "analyses"
    id: Mapped[int] = mapped_column(primary_key=True)
    tender_id: Mapped[int] = mapped_column(ForeignKey("tenders.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    profile_score: Mapped[int] = mapped_column(Integer, default=0)
    legal_risk: Mapped[int] = mapped_column(Integer, default=0)
    competition_risk: Mapped[int] = mapped_column(Integer, default=0)
    technical_risk: Mapped[int] = mapped_column(Integer, default=0)
    financial_risk: Mapped[int] = mapped_column(Integer, default=0)
    estimate_total: Mapped[float] = mapped_column(Float, default=0)
    estimated_profit: Mapped[float] = mapped_column(Float, default=0)
    margin_percent: Mapped[float] = mapped_column(Float, default=0)
    report: Mapped[dict] = mapped_column(JSON, default=dict)
    tender: Mapped[Tender] = relationship(back_populates="analyses")
