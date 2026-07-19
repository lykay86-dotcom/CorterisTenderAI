"""Tender repository compatible with both integer and UUID model revisions."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database.base import json_safe
from app.database.models import Analysis, Document, Tender
from app.database.session import session_scope
from app.ui.navigation.contracts import DashboardFilterId, RouteId


def _active_filter(model: type[Any]):
    attribute = getattr(model, "is_deleted", None)
    return attribute.is_(False) if attribute is not None else None


def _coerce_identifier(value: str | int) -> str | int:
    if isinstance(value, int):
        return value
    text = str(value).strip()
    return int(text) if text.isdigit() else text


def select_dashboard_tenders(
    entities: Iterable[Any],
    dashboard_filter: DashboardFilterId | str,
    *,
    at: datetime,
) -> list[Any]:
    """Apply one closed tender KPI cohort to already loaded active entities."""
    filter_id = DashboardFilterId(dashboard_filter)
    if filter_id.route_id is not RouteId.TENDERS:
        raise ValueError("Dashboard filter does not belong to tenders")
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("Dashboard tender filter time must be timezone-aware")

    result: list[Any] = []
    for entity in entities:
        if filter_id is DashboardFilterId.TENDERS_CREATED_TODAY:
            created_at = getattr(entity, "created_at", None)
            if not isinstance(created_at, datetime):
                continue
            if created_at.tzinfo is not None and created_at.utcoffset() is not None:
                created_at = created_at.astimezone(at.tzinfo)
            if created_at.date() == at.date():
                result.append(entity)
            continue

        try:
            score = Decimal(str(getattr(entity, "score", None)))
        except (InvalidOperation, TypeError, ValueError):
            continue
        if score >= Decimal("80"):
            result.append(entity)
    return result


class TenderRepository:
    """Repository for tenders, documents and saved analyses."""

    def create(self, **data) -> Tender:
        with session_scope() as session:
            obj = Tender(**data)
            session.add(obj)
            session.flush()
            session.expunge(obj)
            return obj

    def list(self) -> list[Tender]:
        with session_scope() as session:
            stmt = select(Tender).order_by(Tender.created_at.desc())
            active = _active_filter(Tender)
            if active is not None:
                stmt = stmt.where(active)
            return list(session.scalars(stmt).all())

    def list_for_dashboard(
        self,
        *,
        limit: int | None = 100,
    ) -> list[Tender]:
        with session_scope() as session:
            stmt = (
                select(Tender)
                .options(selectinload(Tender.analyses))
                .order_by(Tender.created_at.desc())
            )
            if limit is not None:
                normalized_limit = max(1, min(int(limit), 500))
                stmt = stmt.limit(normalized_limit)
            active = _active_filter(Tender)
            if active is not None:
                stmt = stmt.where(active)
            return list(session.scalars(stmt).all())

    def get(self, tender_id: str | int) -> Tender | None:
        identifier = _coerce_identifier(tender_id)
        with session_scope() as session:
            stmt = select(Tender).where(Tender.id == identifier)
            active = _active_filter(Tender)
            if active is not None:
                stmt = stmt.where(active)
            return session.scalar(stmt)

    def list_for_dashboard_filter(
        self,
        dashboard_filter: DashboardFilterId | str,
        *,
        at: datetime,
    ) -> list[Tender]:
        """Return the exact active tender cohort behind one Dashboard KPI."""
        return select_dashboard_tenders(
            self.list_for_dashboard(limit=None),
            dashboard_filter,
            at=at,
        )

    def add_document(
        self,
        tender_id: str | int,
        **data,
    ) -> Document:
        with session_scope() as session:
            obj = Document(
                tender_id=_coerce_identifier(tender_id),
                **data,
            )
            session.add(obj)
            session.flush()
            session.expunge(obj)
            return obj

    def documents(
        self,
        tender_id: str | int,
    ) -> list[Document]:
        identifier = _coerce_identifier(tender_id)
        with session_scope() as session:
            stmt = select(Document).where(Document.tender_id == identifier)
            active = _active_filter(Document)
            if active is not None:
                stmt = stmt.where(active)
            return list(session.scalars(stmt).all())

    def save_analysis(
        self,
        tender_id: str | int,
        report: dict,
    ) -> Analysis:
        identifier = _coerce_identifier(tender_id)
        with session_scope() as session:
            analysis = Analysis(
                tender_id=identifier,
                **report["metrics"],
                report=json_safe(report),
            )
            session.add(analysis)

            tender = session.get(Tender, identifier)
            if tender is None:
                raise ValueError(f"Тендер не найден: {tender_id}")

            tender.score = report["score"]
            tender.recommendation = report["recommendation"]
            tender.status = "Проанализирован"

            touch = getattr(tender, "touch", None)
            if callable(touch):
                touch()

            session.flush()
            session.expunge(analysis)
            return analysis


def create_tender(**kwargs) -> Tender:
    return TenderRepository().create(**kwargs)


def list_tenders() -> list[Tender]:
    return TenderRepository().list()


def get_tender(
    tender_id: str | int,
) -> Tender | None:
    return TenderRepository().get(tender_id)
