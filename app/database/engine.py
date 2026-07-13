"""Создание и настройка SQLAlchemy Engine."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url


def normalize_database_url(url_or_path: str | Path) -> str:
    """Преобразует путь SQLite или готовый URL в URL SQLAlchemy."""
    value = str(url_or_path)
    if "://" in value:
        return value
    path = Path(value).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path.as_posix()}"


def create_database_engine(url_or_path: str | Path, *, echo: bool = False) -> Engine:
    """Создаёт Engine, пригодный для SQLite и PostgreSQL."""
    url = normalize_database_url(url_or_path)
    parsed = make_url(url)
    connect_args: dict[str, object] = {}
    if parsed.drivername.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        connect_args["timeout"] = 30

    engine = create_engine(
        url,
        echo=echo,
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args,
    )

    if parsed.drivername.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()

    return engine
