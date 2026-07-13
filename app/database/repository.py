"""Универсальный репозиторий SQLAlchemy."""

from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from .base import UUIDAuditMixin, utc_now
from .exceptions import EntityNotFoundError

ModelT = TypeVar("ModelT", bound=UUIDAuditMixin)


class Repository(Generic[ModelT]):
    def __init__(self, session: Session, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    def get(self, entity_id: str, *, include_deleted: bool = False) -> ModelT | None:
        stmt: Select[tuple[ModelT]] = select(self.model).where(self.model.id == entity_id)
        if not include_deleted:
            stmt = stmt.where(self.model.is_deleted.is_(False))
        return self.session.scalar(stmt)

    def require(self, entity_id: str, *, include_deleted: bool = False) -> ModelT:
        entity = self.get(entity_id, include_deleted=include_deleted)
        if entity is None:
            raise EntityNotFoundError(f"{self.model.__name__} не найден: {entity_id}")
        return entity

    def list(self, *, include_deleted: bool = False, limit: int = 1000) -> list[ModelT]:
        stmt: Select[tuple[ModelT]] = select(self.model).limit(limit)
        if not include_deleted:
            stmt = stmt.where(self.model.is_deleted.is_(False))
        return list(self.session.scalars(stmt).all())

    def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        self.session.flush()
        return entity

    def delete(self, entity: ModelT, *, hard: bool = False) -> None:
        if hard:
            self.session.delete(entity)
        else:
            entity.soft_delete()
            self.session.flush()

    def restore(self, entity: ModelT) -> ModelT:
        entity.restore()
        self.session.flush()
        return entity

    def update_fields(self, entity: ModelT, **fields: object) -> ModelT:
        for name, value in fields.items():
            if not hasattr(entity, name):
                raise AttributeError(f"Поле {name!r} отсутствует у {type(entity).__name__}")
            setattr(entity, name, value)
        entity.updated_at = utc_now()
        entity.row_version += 1
        self.session.flush()
        return entity
