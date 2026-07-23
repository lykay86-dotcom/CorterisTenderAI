"""Repository for the RM-156 contractor identity aggregate."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.contractors import ContractorInn

from ..exceptions import DuplicateEntityError
from ..models import Contractor
from ..repository import Repository


class ContractorRepository(Repository[Contractor]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Contractor)

    def get_by_inn(
        self,
        inn: object,
        *,
        include_deleted: bool = False,
    ) -> Contractor | None:
        canonical = ContractorInn.parse(inn).value
        stmt = select(Contractor).where(Contractor.inn == canonical)
        if not include_deleted:
            stmt = stmt.where(Contractor.is_deleted.is_(False))
        return self.session.scalar(stmt)

    def create(self, inn: object) -> Contractor:
        canonical = ContractorInn.parse(inn).value
        if self.get_by_inn(canonical, include_deleted=True) is not None:
            raise DuplicateEntityError(f"Контрагент с ИНН {canonical} уже существует")
        contractor = Contractor(inn=canonical)
        try:
            with self.session.begin_nested():
                self.session.add(contractor)
                self.session.flush()
        except IntegrityError as exc:
            raise DuplicateEntityError(f"Контрагент с ИНН {canonical} уже существует") from exc
        return contractor
