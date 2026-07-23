"""Persistent contractor identity."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.contractors import ContractorInn

from ..base import Base, UUIDAuditMixin


class Contractor(UUIDAuditMixin, Base):
    __tablename__ = "contractors"

    inn: Mapped[str] = mapped_column(String(12), nullable=False, unique=True, index=True)

    @validates("inn")
    def _validate_inn(self, _key: str, value: object) -> str:
        return ContractorInn.parse(value).value
