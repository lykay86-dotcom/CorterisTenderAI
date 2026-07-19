"""Complete Qt textual equivalent for immutable chart data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt

from app.ui.charts.contracts import ChartSpec, ChartState, ChartXValue
from app.ui.tables import TableColumnId, TableRevision, TableRole, TableRowId, TableState


@dataclass(frozen=True, slots=True)
class ChartTableRow:
    """One exact source-order table record."""

    state: str
    series_id: str
    series_label: str
    point_id: str
    point_order: int
    x: ChartXValue
    y: Decimal | None
    unit: str


def _display(value: ChartXValue | Decimal) -> str:
    return value.isoformat() if isinstance(value, datetime) else str(value)


def _table_state(state: ChartState) -> TableState:
    if state in {ChartState.STALE}:
        return TableState.PARTIAL
    if state in {ChartState.TOO_LARGE, ChartState.UNAVAILABLE}:
        return TableState.ERROR
    return TableState(state.value)


class ChartTableModel(QAbstractTableModel):
    """Read-only complete textual representation of a `ChartSpec`."""

    STATE_COLUMN = 0
    SERIES_COLUMN = 1
    SERIES_LABEL_COLUMN = 2
    POINT_COLUMN = 3
    X_COLUMN = 4
    Y_COLUMN = 5
    UNIT_COLUMN = 6

    _HEADERS = ("State", "Series ID", "Series", "Point ID", "X", "Y", "Unit")
    _COLUMN_IDS = ("state", "series_id", "series_label", "point_id", "x", "y", "unit")

    def __init__(self, spec: ChartSpec, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._spec = spec
        self._rows = self._build_rows(spec)

    @staticmethod
    def _build_rows(spec: ChartSpec) -> tuple[ChartTableRow, ...]:
        return tuple(
            ChartTableRow(
                state=spec.state.value,
                series_id=series.series_id,
                series_label=series.label,
                point_id=point.point_id,
                point_order=point_order,
                x=point.x,
                y=point.y,
                unit=spec.y_axis.unit,
            )
            for series in spec.series
            for point_order, point in enumerate(series.points)
        )

    @property
    def spec(self) -> ChartSpec:
        return self._spec

    def set_spec(self, spec: ChartSpec) -> None:
        self.beginResetModel()
        self._spec = spec
        self._rows = self._build_rows(spec)
        self.endResetModel()

    def row_record(self, row: int) -> ChartTableRow:
        if not 0 <= row < len(self._rows):
            raise IndexError(row)
        return self._rows[row]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._HEADERS)

    def data(
        self,
        index: QModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object | None:
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        row = self._rows[index.row()]
        values = (
            row.state,
            row.series_id,
            row.series_label,
            row.point_id,
            _display(row.x),
            "Missing" if row.y is None else str(row.y),
            row.unit,
        )
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.AccessibleTextRole):
            return values[index.column()]
        if role == TableRole.ROW_ID:
            return TableRowId("chart_point", f"{row.series_id}:{row.point_id}")
        if role == TableRole.ROW_REVISION:
            return TableRevision(
                f"{self._spec.chart_id}:{self._spec.state.value}:{row.series_id}:"
                f"{row.point_id}:{row.x}:{row.y}"
            )
        if role == TableRole.COLUMN_ID:
            return TableColumnId(self._COLUMN_IDS[index.column()])
        if role in {TableRole.SORT_VALUE, TableRole.EXPORT_VALUE}:
            raw_values = (
                row.state,
                row.series_id,
                row.series_label,
                row.point_id,
                row.x,
                row.y,
                row.unit,
            )
            return raw_values[index.column()]
        if role == TableRole.ACTION_IDS:
            return ("select",)
        if role == TableRole.STATE:
            return _table_state(self._spec.state)
        return None

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object | None:
        if orientation is Qt.Orientation.Horizontal and 0 <= section < len(self._HEADERS):
            if role in {Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.AccessibleTextRole}:
                return self._HEADERS[section]
            if role == TableRole.COLUMN_ID:
                return TableColumnId(self._COLUMN_IDS[section])
        if orientation is Qt.Orientation.Vertical and role == Qt.ItemDataRole.DisplayRole:
            return section + 1
        return None


__all__ = ["ChartTableModel", "ChartTableRow"]
