"""Modern tender feed table for Dashboard 1.0."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme.colors import ThemeName, get_palette
from app.ui.theme.typography import Typography
from app.ui.viewmodels.dashboard_viewmodel import RecentTender


@dataclass(frozen=True, slots=True)
class TenderColumn:
    key: str
    title: str
    width: int


COLUMNS: tuple[TenderColumn, ...] = (
    TenderColumn("number", "Номер", 120),
    TenderColumn("title", "Название", 330),
    TenderColumn("customer", "Заказчик", 220),
    TenderColumn("nmck", "НМЦК", 130),
    TenderColumn("deadline", "Срок подачи", 120),
    TenderColumn("score", "AI Score", 90),
    TenderColumn("status", "Статус", 150),
)


class TenderFeedModel(QAbstractTableModel):
    """Qt model for the recent tender feed."""

    def __init__(
        self,
        tenders: Sequence[RecentTender] = (),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._tenders = list(tenders)

    @property
    def tenders(self) -> list[RecentTender]:
        return list(self._tenders)

    def set_tenders(self, tenders: Sequence[RecentTender]) -> None:
        self.beginResetModel()
        self._tenders = list(tenders)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._tenders)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(COLUMNS)

    def data(
        self,
        index: QModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if not index.isValid():
            return None

        tender = self._tenders[index.row()]
        column = COLUMNS[index.column()]
        value = getattr(tender, column.key)

        if role == Qt.ItemDataRole.DisplayRole:
            if column.key == "score":
                return "—" if value is None else f"{value}/100"
            return str(value or "—")

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if column.key in {"nmck", "deadline", "score", "status"}:
                return int(
                    Qt.AlignmentFlag.AlignCenter
                    | Qt.AlignmentFlag.AlignVCenter
                )
            return int(
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignVCenter
            )

        if role == Qt.ItemDataRole.UserRole:
            return tender.number

        if role == Qt.ItemDataRole.ToolTipRole:
            return (
                f"{tender.number}\n"
                f"{tender.title}\n"
                f"{tender.customer}\n"
                f"{tender.recommendation}"
            ).strip()

        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(COLUMNS)
        ):
            return COLUMNS[section].title

        if (
            orientation == Qt.Orientation.Vertical
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return section + 1

        return None

    def tender_at(self, row: int) -> RecentTender | None:
        if 0 <= row < len(self._tenders):
            return self._tenders[row]
        return None


class TenderFeed(QWidget):
    """Dashboard table with current tender status and AI score."""

    tender_open_requested = Signal(str)

    def __init__(
        self,
        tenders: Sequence[RecentTender] = (),
        *,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._theme = ThemeName(theme)
        self.setObjectName("TenderFeed")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableView(self)
        self.table.setObjectName("TenderFeedTable")
        self.table.setModel(TenderFeedModel(tenders, self.table))
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setShowGrid(False)
        self.table.setSortingEnabled(False)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(42)

        header = self.table.horizontalHeader()
        header.setHighlightSections(False)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.Stretch,
        )

        for index, column in enumerate(COLUMNS):
            if index not in {1, 2}:
                header.setSectionResizeMode(
                    index,
                    QHeaderView.ResizeMode.Fixed,
                )
                self.table.setColumnWidth(index, column.width)

        self.table.doubleClicked.connect(self._open_selected)
        layout.addWidget(self.table)

        self.apply_theme(self._theme)

    @property
    def model(self) -> TenderFeedModel:
        model = self.table.model()
        assert isinstance(model, TenderFeedModel)
        return model

    def set_tenders(self, tenders: Sequence[RecentTender]) -> None:
        self.model.set_tenders(tenders)

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)

        self.setStyleSheet(
            f"""
            QWidget#TenderFeed {{
                background: transparent;
                border: none;
            }}
            QTableView#TenderFeedTable {{
                background-color: {palette.input_background};
                alternate-background-color: {palette.hover_background};
                color: {palette.text_primary};
                border: 1px solid {palette.border_subtle};
                border-radius: 10px;
                selection-background-color: {palette.selected_background};
                selection-color: {palette.text_primary};
                outline: none;
                {Typography.BODY_S.css()}
            }}
            QTableView#TenderFeedTable::item {{
                border-bottom: 1px solid {palette.divider};
                padding: 8px 10px;
            }}
            QHeaderView::section {{
                background-color: {palette.panel_background};
                color: {palette.text_secondary};
                border: none;
                border-bottom: 1px solid {palette.border_default};
                padding: 10px;
                {Typography.CAPTION.css()}
            }}
            """
        )

    def _open_selected(self, index: QModelIndex) -> None:
        tender = self.model.tender_at(index.row())
        if tender is not None:
            self.tender_open_requested.emit(tender.number)


__all__ = [
    "COLUMNS",
    "TenderColumn",
    "TenderFeed",
    "TenderFeedModel",
]
