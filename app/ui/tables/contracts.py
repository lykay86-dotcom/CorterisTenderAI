"""Qt-free immutable contracts for deterministic table projections."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from functools import cmp_to_key
import hashlib
import json
import re
import unicodedata
from typing import TypeAlias


_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_HOSTILE_BIDI = {"RLO", "LRO", "RLE", "LRE", "PDF", "RLI", "LRI", "FSI", "PDI"}
TableScalar: TypeAlias = str | int | bool | Decimal | date | datetime | None


def _bounded_text(value: object, *, label: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be str")
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise ValueError(f"{label} must contain 1..{maximum} characters")
    if any(
        ord(character) < 32 or unicodedata.bidirectional(character) in _HOSTILE_BIDI
        for character in normalized
    ):
        raise ValueError(f"{label} contains hostile control characters")
    return normalized


@dataclass(frozen=True, slots=True)
class TableSurfaceId:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "value", _bounded_text(self.value, label="surface ID", maximum=128)
        )


@dataclass(frozen=True, slots=True)
class TableColumnId:
    value: str

    def __post_init__(self) -> None:
        normalized = _bounded_text(self.value, label="column ID", maximum=64)
        if not _ID_PATTERN.fullmatch(normalized):
            raise ValueError("column ID has an invalid format")
        object.__setattr__(self, "value", normalized)


@dataclass(frozen=True, slots=True)
class TableRowId:
    namespace: str
    value: str

    def __post_init__(self) -> None:
        namespace = _bounded_text(self.namespace, label="row namespace", maximum=64)
        if not _ID_PATTERN.fullmatch(namespace):
            raise ValueError("row namespace has an invalid format")
        object.__setattr__(self, "namespace", namespace)
        object.__setattr__(self, "value", _bounded_text(self.value, label="row ID", maximum=512))

    @property
    def public_id(self) -> str:
        return f"{self.namespace}:{self.value}"


@dataclass(frozen=True, slots=True)
class TableRevision:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _bounded_text(self.value, label="revision", maximum=512))


class TableState(StrEnum):
    LOADING = "loading"
    EMPTY = "empty"
    ERROR = "error"
    PARTIAL = "partial"
    READY = "ready"


class TableValueKind(StrEnum):
    TEXT = "text"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"


class SortDirection(StrEnum):
    ASCENDING = "ascending"
    DESCENDING = "descending"


class NullPolicy(StrEnum):
    FIRST = "first"
    LAST = "last"


@dataclass(frozen=True, slots=True)
class TableCell:
    display: str
    sort_value: TableScalar = None
    export_value: TableScalar = None
    accessible_text: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.display, str):
            raise TypeError("cell display must be str")
        if not isinstance(self.accessible_text, str):
            raise TypeError("cell accessible text must be str")
        for label, value in (("sort", self.sort_value), ("export", self.export_value)):
            if isinstance(value, float):
                raise TypeError(f"cell {label} value must not be float")


@dataclass(frozen=True, slots=True)
class TableColumn:
    column_id: TableColumnId
    header: str
    value_kind: TableValueKind = TableValueKind.TEXT
    filterable: bool = False
    sortable: bool = True
    exportable: bool = True
    null_policy: NullPolicy = NullPolicy.LAST
    accessible_description: str = ""

    def __post_init__(self) -> None:
        _bounded_text(self.header, label="column header", maximum=256)
        if not isinstance(self.accessible_description, str):
            raise TypeError("accessible description must be str")


@dataclass(frozen=True, slots=True)
class TableRow:
    row_id: TableRowId
    revision: TableRevision
    cells: tuple[TableCell, ...]
    action_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "cells", tuple(self.cells))
        normalized_actions = tuple(
            _bounded_text(action, label="action ID", maximum=128) for action in self.action_ids
        )
        if len(normalized_actions) != len(set(normalized_actions)):
            raise ValueError("duplicate action ID")
        object.__setattr__(self, "action_ids", normalized_actions)

    def validate_for(self, columns: tuple[TableColumn, ...]) -> None:
        if len(self.cells) != len(columns):
            raise ValueError("row cell count does not match table columns")
        for column, cell in zip(columns, self.cells, strict=True):
            _validate_cell_kind(column, cell)


def _validate_cell_kind(column: TableColumn, cell: TableCell) -> None:
    value = cell.sort_value
    if value is None:
        return
    valid = {
        TableValueKind.TEXT: isinstance(value, str),
        TableValueKind.INTEGER: isinstance(value, int) and not isinstance(value, bool),
        TableValueKind.DECIMAL: isinstance(value, Decimal),
        TableValueKind.BOOLEAN: isinstance(value, bool),
        TableValueKind.DATE: isinstance(value, date) and not isinstance(value, datetime),
        TableValueKind.DATETIME: isinstance(value, datetime),
    }[column.value_kind]
    if not valid:
        raise TypeError(
            f"cell sort value for {column.column_id.value} does not match {column.value_kind.value}"
        )


@dataclass(frozen=True, slots=True)
class TableSnapshot:
    surface_id: TableSurfaceId
    fingerprint: str
    state: TableState
    columns: tuple[TableColumn, ...]
    rows: tuple[TableRow, ...]
    state_message: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "fingerprint", _bounded_text(self.fingerprint, label="fingerprint", maximum=512)
        )
        object.__setattr__(self, "columns", tuple(self.columns))
        object.__setattr__(self, "rows", tuple(self.rows))
        if not self.columns:
            raise ValueError("table must define at least one column")
        column_ids = tuple(column.column_id for column in self.columns)
        if len(column_ids) != len(set(column_ids)):
            raise ValueError("duplicate table column ID")
        row_ids = tuple(row.row_id for row in self.rows)
        if len(row_ids) != len(set(row_ids)):
            raise ValueError("duplicate table row ID")
        for row in self.rows:
            row.validate_for(self.columns)
        if self.state in {TableState.LOADING, TableState.EMPTY, TableState.ERROR} and self.rows:
            raise ValueError(f"{self.state.name} table state cannot contain rows")
        if self.state is TableState.READY and not self.rows:
            raise ValueError("READY table state with no rows must use EMPTY")
        if self.state in {TableState.ERROR, TableState.PARTIAL} and not self.state_message.strip():
            raise ValueError(f"{self.state.name} table state requires a message")

    def row(self, row_id: TableRowId) -> TableRow | None:
        return next((row for row in self.rows if row.row_id == row_id), None)


@dataclass(frozen=True, slots=True)
class SortKey:
    column_id: TableColumnId
    direction: SortDirection = SortDirection.ASCENDING
    null_policy: NullPolicy | None = None


@dataclass(frozen=True, slots=True)
class SortSpec:
    keys: tuple[SortKey, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "keys", tuple(self.keys))
        ids = tuple(key.column_id for key in self.keys)
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate sort column")


@dataclass(frozen=True, slots=True)
class TextFilter:
    query: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.query, str):
            raise TypeError("filter query must be str")
        object.__setattr__(self, "query", self.query.strip().casefold())


@dataclass(frozen=True, slots=True)
class VisibleTableSnapshot:
    surface_id: TableSurfaceId
    source_fingerprint: str
    visible_fingerprint: str
    state: TableState
    columns: tuple[TableColumn, ...]
    rows: tuple[TableRow, ...]
    state_message: str = ""

    def row(self, row_id: TableRowId) -> TableRow | None:
        return next((row for row in self.rows if row.row_id == row_id), None)


def _compare_values(left: TableScalar, right: TableScalar, null_policy: NullPolicy) -> int:
    if left is None or right is None:
        if left is right:
            return 0
        if left is None:
            return -1 if null_policy is NullPolicy.FIRST else 1
        return 1 if null_policy is NullPolicy.FIRST else -1
    left_value = left.casefold() if isinstance(left, str) else left
    right_value = right.casefold() if isinstance(right, str) else right
    return (left_value > right_value) - (left_value < right_value)


def project_snapshot(
    snapshot: TableSnapshot,
    *,
    sort: SortSpec = SortSpec(),
    text_filter: TextFilter = TextFilter(),
) -> VisibleTableSnapshot:
    column_positions = {column.column_id: index for index, column in enumerate(snapshot.columns)}
    for key in sort.keys:
        column = next(
            (column for column in snapshot.columns if column.column_id == key.column_id), None
        )
        if column is None or not column.sortable:
            raise ValueError(f"unknown or unsortable column: {key.column_id.value}")

    filter_positions = tuple(
        index for index, column in enumerate(snapshot.columns) if column.filterable
    )
    rows = tuple(
        row
        for row in snapshot.rows
        if not text_filter.query
        or any(
            text_filter.query in row.cells[index].display.casefold() for index in filter_positions
        )
    )

    if sort.keys:

        def compare(left: TableRow, right: TableRow) -> int:
            for key in sort.keys:
                index = column_positions[key.column_id]
                column = snapshot.columns[index]
                result = _compare_values(
                    left_value := left.cells[index].sort_value,
                    right_value := right.cells[index].sort_value,
                    key.null_policy or column.null_policy,
                )
                if result:
                    if left_value is None or right_value is None:
                        return result
                    return result if key.direction is SortDirection.ASCENDING else -result
            return (left.row_id.public_id > right.row_id.public_id) - (
                left.row_id.public_id < right.row_id.public_id
            )

        rows = tuple(sorted(rows, key=cmp_to_key(compare)))

    fingerprint_payload = {
        "source": snapshot.fingerprint,
        "columns": [column.column_id.value for column in snapshot.columns],
        "rows": [row.row_id.public_id for row in rows],
        "sort": [
            (
                key.column_id.value,
                key.direction.value,
                (key.null_policy or "").value if key.null_policy else "",
            )
            for key in sort.keys
        ],
        "filter": text_filter.query,
    }
    visible_fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return VisibleTableSnapshot(
        snapshot.surface_id,
        snapshot.fingerprint,
        visible_fingerprint,
        snapshot.state,
        snapshot.columns,
        rows,
        snapshot.state_message,
    )


@dataclass(frozen=True, slots=True)
class ExportProjection:
    source_fingerprint: str
    visible_fingerprint: str
    column_ids: tuple[TableColumnId, ...]
    row_ids: tuple[TableRowId, ...]
    values: tuple[tuple[TableScalar, ...], ...]


def export_projection(snapshot: VisibleTableSnapshot) -> ExportProjection:
    export_positions = tuple(
        index for index, column in enumerate(snapshot.columns) if column.exportable
    )
    return ExportProjection(
        snapshot.source_fingerprint,
        snapshot.visible_fingerprint,
        tuple(snapshot.columns[index].column_id for index in export_positions),
        tuple(row.row_id for row in snapshot.rows),
        tuple(
            tuple(row.cells[index].export_value for index in export_positions)
            for row in snapshot.rows
        ),
    )


@dataclass(frozen=True, slots=True)
class TableSelection:
    row_id: TableRowId | None = None

    def reconcile(self, snapshot: TableSnapshot | VisibleTableSnapshot) -> TableSelection:
        if self.row_id is None or snapshot.row(self.row_id) is None:
            return TableSelection()
        return self


@dataclass(frozen=True, slots=True)
class TableActionToken:
    surface_id: TableSurfaceId
    action_id: str
    row_id: TableRowId
    row_revision: TableRevision
    snapshot_fingerprint: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "action_id", _bounded_text(self.action_id, label="action ID", maximum=128)
        )
        object.__setattr__(
            self,
            "snapshot_fingerprint",
            _bounded_text(self.snapshot_fingerprint, label="snapshot fingerprint", maximum=512),
        )


@dataclass(frozen=True, slots=True)
class ActionValidation:
    allowed: bool
    reason_code: str = ""


def validate_action_token(token: TableActionToken, snapshot: TableSnapshot) -> ActionValidation:
    if token.surface_id != snapshot.surface_id:
        return ActionValidation(False, "surface_mismatch")
    if token.snapshot_fingerprint != snapshot.fingerprint:
        return ActionValidation(False, "snapshot_stale")
    row = snapshot.row(token.row_id)
    if row is None:
        return ActionValidation(False, "row_missing")
    if row.revision != token.row_revision:
        return ActionValidation(False, "row_stale")
    if token.action_id not in row.action_ids:
        return ActionValidation(False, "action_unavailable")
    return ActionValidation(True)


__all__ = [
    "ActionValidation",
    "ExportProjection",
    "NullPolicy",
    "SortDirection",
    "SortKey",
    "SortSpec",
    "TableActionToken",
    "TableCell",
    "TableColumn",
    "TableColumnId",
    "TableRevision",
    "TableRow",
    "TableRowId",
    "TableScalar",
    "TableSelection",
    "TableSnapshot",
    "TableState",
    "TableSurfaceId",
    "TableValueKind",
    "TextFilter",
    "VisibleTableSnapshot",
    "export_projection",
    "project_snapshot",
    "validate_action_token",
]
