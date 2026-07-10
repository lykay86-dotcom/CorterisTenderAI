from __future__ import annotations

from sqlalchemy import select

from app.database.base import json_safe
from app.database.models import Analysis, Document, Tender
from app.database.session import session_scope


class TenderRepository:
    """Совместимый репозиторий тендеров поверх новой UUID-модели."""

    def create(self, **data) -> Tender:
        with session_scope() as session:
            obj = Tender(**data)
            session.add(obj)
            session.flush()
            return obj

    def list(self) -> list[Tender]:
        with session_scope() as session:
            stmt = (
                select(Tender)
                .where(Tender.is_deleted.is_(False))
                .order_by(Tender.created_at.desc())
            )
            return list(session.scalars(stmt).all())

    def get(self, tender_id: str) -> Tender | None:
        with session_scope() as session:
            return session.scalar(
                select(Tender).where(Tender.id == tender_id, Tender.is_deleted.is_(False))
            )

    def add_document(self, tender_id: str, **data) -> Document:
        with session_scope() as session:
            obj = Document(tender_id=tender_id, **data)
            session.add(obj)
            session.flush()
            return obj

    def documents(self, tender_id: str) -> list[Document]:
        with session_scope() as session:
            stmt = select(Document).where(
                Document.tender_id == tender_id,
                Document.is_deleted.is_(False),
            )
            return list(session.scalars(stmt).all())

    def save_analysis(self, tender_id: str, report: dict) -> Analysis:
        with session_scope() as session:
            analysis = Analysis(tender_id=tender_id, **report["metrics"], report=json_safe(report))
            session.add(analysis)
            tender = session.get(Tender, tender_id)
            if tender is None:
                raise ValueError(f"Тендер не найден: {tender_id}")
            tender.score = report["score"]
            tender.recommendation = report["recommendation"]
            tender.status = "Проанализирован"
            tender.touch()
            session.flush()
            return analysis


def create_tender(**kwargs) -> Tender:
    return TenderRepository().create(**kwargs)


def list_tenders() -> list[Tender]:
    return TenderRepository().list()


def get_tender(tender_id: str) -> Tender | None:
    return TenderRepository().get(tender_id)
