"""Инспекция фактической структуры базы данных.

Модуль не зависит от ORM-моделей и безопасно работает со старыми SQLite-базами.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine, inspect, text


@dataclass(frozen=True, slots=True)
class ColumnInfo:
    name: str
    type_name: str
    nullable: bool
    default: str | None
    primary_key: bool


class SchemaInspector:
    """Читает таблицы, колонки и индексы из подключённой БД."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def table_names(self) -> set[str]:
        return set(inspect(self.engine).get_table_names())

    def table_exists(self, table_name: str) -> bool:
        return table_name in self.table_names()

    def columns(self, table_name: str) -> dict[str, ColumnInfo]:
        if not self.table_exists(table_name):
            return {}
        result: dict[str, ColumnInfo] = {}
        for column in inspect(self.engine).get_columns(table_name):
            result[str(column["name"])] = ColumnInfo(
                name=str(column["name"]),
                type_name=str(column["type"]).upper(),
                nullable=bool(column.get("nullable", True)),
                default=None if column.get("default") is None else str(column["default"]),
                primary_key=bool(column.get("primary_key", False)),
            )
        return result

    def column_exists(self, table_name: str, column_name: str) -> bool:
        return column_name in self.columns(table_name)

    def primary_key_type(self, table_name: str) -> str | None:
        for column in self.columns(table_name).values():
            if column.primary_key:
                return column.type_name
        return None

    def index_names(self, table_name: str) -> set[str]:
        if not self.table_exists(table_name):
            return set()
        return {str(item["name"]) for item in inspect(self.engine).get_indexes(table_name)}

    def row_count(self, table_name: str) -> int:
        if not self.table_exists(table_name):
            return 0
        quoted = table_name.replace('"', '""')
        with self.engine.connect() as connection:
            return int(connection.scalar(text(f'SELECT COUNT(*) FROM "{quoted}"')) or 0)
