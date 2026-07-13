"""Базовые классы SQLAlchemy для всех моделей Corteris Tender AI."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    """Возвращает текущее время UTC с информацией о часовом поясе."""
    return datetime.now(timezone.utc)


def json_safe(value: Any) -> Any:
    """Рекурсивно преобразует значение в JSON-совместимый вид."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    return value


class Base(DeclarativeBase):
    """Единая декларативная база SQLAlchemy."""


class UUIDAuditMixin:
    """UUID, аудит времени, soft delete и версия записи."""

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    row_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    def soft_delete(self) -> None:
        self.is_deleted = True
        self.deleted_at = utc_now()
        self.row_version += 1

    def restore(self) -> None:
        self.is_deleted = False
        self.deleted_at = None
        self.row_version += 1

    def touch(self) -> None:
        self.updated_at = utc_now()
        self.row_version += 1

    def as_dict(self) -> dict[str, Any]:
        return json_safe(
            {column.name: getattr(self, column.name) for column in self.__table__.columns}
        )
