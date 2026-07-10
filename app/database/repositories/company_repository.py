from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Company
from ..repository import Repository


class CompanyRepository(Repository[Company]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Company)

    def get_active(self) -> Company | None:
        stmt = select(Company).where(Company.is_deleted.is_(False), Company.is_active.is_(True))
        return self.session.scalar(stmt)

    def get_by_inn(self, inn: str) -> Company | None:
        stmt = select(Company).where(Company.inn == inn, Company.is_deleted.is_(False))
        return self.session.scalar(stmt)
