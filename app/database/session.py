"""Управление сессиями и транзакциями."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from .base import Base
from .engine import create_database_engine
from .exceptions import DatabaseNotInitializedError

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def init_database(
    url_or_path: str | Path,
    *,
    echo: bool = False,
    run_migrations: bool = True,
    backup_dir: Path | None = None,
) -> Engine:
    """Инициализирует глобальный Engine и фабрику сессий."""
    global _engine, _session_factory
    _engine = create_database_engine(url_or_path, echo=echo)
    _session_factory = sessionmaker(bind=_engine, class_=Session, expire_on_commit=False)

    # Импорт моделей регистрирует таблицы в metadata.
    from . import models as _models  # noqa: F401

    if run_migrations:
        from .migration import MigrationManager

        MigrationManager(_engine, backup_dir=backup_dir).upgrade()
    else:
        Base.metadata.create_all(_engine)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        raise DatabaseNotInitializedError("База данных не инициализирована")
    return _engine


def create_session() -> Session:
    if _session_factory is None:
        raise DatabaseNotInitializedError("База данных не инициализирована")
    return _session_factory()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Контекст транзакции: commit при успехе, rollback при ошибке."""
    session = create_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_database_state() -> None:
    """Освобождает глобальный Engine. Используется тестами."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
