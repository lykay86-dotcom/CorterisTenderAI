"""Qt projection, exact-ID selection and state host for RM-150 tables."""

from __future__ import annotations

from enum import IntEnum
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.ui.tables.contracts import (
    TableActionToken,
    TableRowId,
    TableSnapshot,
    TableState,
    TableSurfaceId,
)


class TableRole(IntEnum):
    ROW_ID = int(Qt.ItemDataRole.UserRole) + 100
    ROW_REVISION = int(Qt.ItemDataRole.UserRole) + 101
    COLUMN_ID = int(Qt.ItemDataRole.UserRole) + 102
    SORT_VALUE = int(Qt.ItemDataRole.UserRole) + 103
    EXPORT_VALUE = int(Qt.ItemDataRole.UserRole) + 104
    ACTION_IDS = int(Qt.ItemDataRole.UserRole) + 105
    STATE = int(Qt.ItemDataRole.UserRole) + 106
    SNAPSHOT_FINGERPRINT = int(Qt.ItemDataRole.UserRole) + 107


class ImmutableTableModel(QAbstractTableModel):
    """Read-only Qt projection over one immutable table snapshot."""

    def __init__(self, snapshot: TableSnapshot, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._snapshot = snapshot

    @property
    def snapshot(self) -> TableSnapshot:
        return self._snapshot

    def set_snapshot(self, snapshot: TableSnapshot) -> None:
        self.beginResetModel()
        self._snapshot = snapshot
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._snapshot.rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._snapshot.columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._snapshot.rows):
            return None
        if not 0 <= index.column() < len(self._snapshot.columns):
            return None
        row = self._snapshot.rows[index.row()]
        column = self._snapshot.columns[index.column()]
        cell = row.cells[index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            return cell.display
        if role == Qt.ItemDataRole.AccessibleTextRole:
            return cell.accessible_text or cell.display
        if role == TableRole.ROW_ID:
            return row.row_id
        if role == TableRole.ROW_REVISION:
            return row.revision
        if role == TableRole.COLUMN_ID:
            return column.column_id
        if role == TableRole.SORT_VALUE:
            return cell.sort_value
        if role == TableRole.EXPORT_VALUE:
            return cell.export_value
        if role == TableRole.ACTION_IDS:
            return row.action_ids
        if role == TableRole.STATE:
            return self._snapshot.state
        if role == TableRole.SNAPSHOT_FINGERPRINT:
            return self._snapshot.fingerprint
        return None

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if orientation is Qt.Orientation.Horizontal and 0 <= section < len(self._snapshot.columns):
            column = self._snapshot.columns[section]
            if role == Qt.ItemDataRole.DisplayRole:
                return column.header
            if role == Qt.ItemDataRole.AccessibleTextRole:
                return column.accessible_description or column.header
            if role == TableRole.COLUMN_ID:
                return column.column_id
        if orientation is Qt.Orientation.Vertical and role == Qt.ItemDataRole.DisplayRole:
            return section + 1
        return None


class TableSelectionController:
    """Restore view selection only through an exact immutable row identity."""

    def __init__(self, view: QTableView, model: ImmutableTableModel) -> None:
        self._view = view
        self._model = model
        self._pending_row_id: TableRowId | None = None
        model.modelAboutToBeReset.connect(self._capture_before_reset)
        model.modelReset.connect(self._restore_after_reset)

    @property
    def selected_row_id(self) -> TableRowId | None:
        selection = self._view.selectionModel()
        if selection is None:
            return None
        selected = selection.selectedRows(0)
        if not selected:
            return None
        value = selected[0].data(TableRole.ROW_ID)
        return value if isinstance(value, TableRowId) else None

    def select_row_id(self, row_id: TableRowId) -> bool:
        for row in range(self._model.rowCount()):
            index = self._model.index(row, 0)
            if index.data(TableRole.ROW_ID) != row_id:
                continue
            self._view.setCurrentIndex(index)
            self._view.selectRow(row)
            return True
        self.clear()
        return False

    def clear(self) -> None:
        self._view.clearSelection()
        self._view.setCurrentIndex(QModelIndex())

    def _capture_before_reset(self) -> None:
        self._pending_row_id = self.selected_row_id

    def _restore_after_reset(self) -> None:
        pending = self._pending_row_id
        self._pending_row_id = None
        if pending is None or not self.select_row_id(pending):
            self.clear()


class TableStateHost(QWidget):
    """Small reusable table host with a sibling semantic state region."""

    action_requested = Signal(object)

    def __init__(
        self,
        *,
        surface_id: TableSurfaceId,
        accessible_name: str,
        accessible_description: str,
        primary_action_id: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._surface_id = surface_id
        self._primary_action_id = primary_action_id.strip()
        initial = _empty_snapshot(surface_id)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.state_region = QLabel(self)
        self.state_region.setObjectName("TableStateRegion")
        self.state_region.setAccessibleName("Table data state")
        self.state_region.setWordWrap(True)
        layout.addWidget(self.state_region)
        self.table = QTableView(self)
        self.table.setAccessibleName(accessible_name)
        self.table.setAccessibleDescription(accessible_description)
        self.table.setTabKeyNavigation(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.model = ImmutableTableModel(initial, self.table)
        self.table.setModel(self.model)
        self.selection = TableSelectionController(self.table, self.model)
        self.table.activated.connect(lambda _index: self.activate_selected())
        layout.addWidget(self.table)
        self.set_snapshot(initial)

    def set_snapshot(self, snapshot: TableSnapshot) -> None:
        if snapshot.surface_id != self._surface_id:
            raise ValueError("snapshot belongs to another table surface")
        self.model.set_snapshot(snapshot)
        is_ready = snapshot.state is TableState.READY
        self.table.setVisible(snapshot.state in {TableState.READY, TableState.PARTIAL})
        self.table.setEnabled(snapshot.state in {TableState.READY, TableState.PARTIAL})
        self.state_region.setText(snapshot.state_message or _state_message(snapshot.state))
        self.state_region.setAccessibleDescription(self.state_region.text())
        self.state_region.setVisible(not is_ready)

    def activate_selected(self) -> None:
        row_id = self.selection.selected_row_id
        if row_id is None or not self._primary_action_id:
            return
        snapshot = self.model.snapshot
        row = snapshot.row(row_id)
        if row is None or self._primary_action_id not in row.action_ids:
            return
        self.action_requested.emit(
            TableActionToken(
                snapshot.surface_id,
                self._primary_action_id,
                row.row_id,
                row.revision,
                snapshot.fingerprint,
            )
        )


def _empty_snapshot(surface_id: TableSurfaceId) -> TableSnapshot:
    from app.ui.tables.contracts import TableColumn, TableColumnId

    return TableSnapshot(
        surface_id,
        "initial-empty",
        TableState.EMPTY,
        (TableColumn(TableColumnId("status"), "Status", sortable=False),),
        (),
    )


def _state_message(state: TableState) -> str:
    return {
        TableState.LOADING: "Loading data",
        TableState.EMPTY: "No data",
        TableState.ERROR: "Unable to load data",
        TableState.PARTIAL: "Data is partially available",
        TableState.READY: "",
    }[state]


__all__ = [
    "ImmutableTableModel",
    "TableRole",
    "TableSelectionController",
    "TableStateHost",
]
