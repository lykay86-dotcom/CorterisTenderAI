"""Unit of Work для согласованной работы нескольких репозиториев."""
from __future__ import annotations

from sqlalchemy.orm import Session

from .repositories import AuditRepository, CompanyRepository, SettingsRepository
from .session import create_session


class UnitOfWork:
    def __init__(self, session: Session | None = None) -> None:
        self.session = session or create_session()
        self._owns_session = session is None
        self.companies = CompanyRepository(self.session)
        self.settings = SettingsRepository(self.session)
        self.audit = AuditRepository(self.session)

    def __enter__(self) -> "UnitOfWork":
        return self

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            if self._owns_session:
                self.session.close()
