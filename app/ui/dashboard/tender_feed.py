"""Modern tender feed table for Dashboard 1.0."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Sequence

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QPainter, QResizeEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHeaderView,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.ui.dashboard.data_state import (
    DataState,
    DataStateKind,
    DataStatePanel,
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


class TenderFeedDensity(StrEnum):
    """Visible column profile selected from the actual table width."""

    NARROW = "narrow"
    COMPACT = "compact"
    STANDARD = "standard"
    DETAILED = "detailed"


VISIBLE_COLUMNS: dict[TenderFeedDensity, tuple[str, ...]] = {
    TenderFeedDensity.NARROW: (
        "title",
        "deadline",
        "score",
    ),
    TenderFeedDensity.COMPACT: (
        "title",
        "customer",
        "deadline",
        "score",
    ),
    TenderFeedDensity.STANDARD: (
        "title",
        "customer",
        "nmck",
        "deadline",
        "score",
        "status",
    ),
    TenderFeedDensity.DETAILED: tuple(column.key for column in COLUMNS),
}


class TenderFeedDelegate(QStyledItemDelegate):
    """Paint AI Score and tender status as compact semantic pills."""

    def __init__(
        self,
        *,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = ThemeName(theme)

    def set_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)

    @staticmethod
    def score_level(score: int | None) -> str:
        if score is None:
            return "neutral"
        if score >= 80:
            return "success"
        if score >= 60:
            return "warning"
        return "danger"

    @staticmethod
    def status_level(status: str) -> str:
        normalized = status.strip().lower()
        if any(word in normalized for word in ("рекоменду", "приоритет", "допущ")):
            return "success"
        if any(word in normalized for word in ("вниман", "провер", "уточн", "риск")):
            return "warning"
        if any(word in normalized for word in ("отклон", "ошиб", "не участвовать")):
            return "danger"
        return "info"

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        column_key = COLUMNS[index.column()].key
        if column_key not in {"score", "status"}:
            super().paint(painter, option, index)
            return

        display_text = str(index.data(Qt.ItemDataRole.DisplayRole) or "—")
        option_copy = QStyleOptionViewItem(option)
        self.initStyleOption(option_copy, index)
        option_copy.text = ""

        style = (
            option_copy.widget.style() if option_copy.widget is not None else QApplication.style()
        )
        style.drawControl(
            QStyle.ControlElement.CE_ItemViewItem,
            option_copy,
            painter,
            option_copy.widget,
        )

        palette = get_palette(self._theme)
        if display_text == "—":
            accent = QColor(palette.text_muted)
        elif column_key == "score":
            tender = index.model().tender_at(index.row())
            score = tender.score if tender is not None else None
            level = self.score_level(score)
            accent = QColor(
                {
                    "success": palette.success,
                    "warning": palette.warning,
                    "danger": palette.danger,
                    "neutral": palette.text_muted,
                }[level]
            )
        else:
            level = self.status_level(display_text)
            accent = QColor(
                {
                    "success": palette.success,
                    "warning": palette.warning,
                    "danger": palette.danger,
                    "info": palette.info,
                }[level]
            )

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        font = option.font
        font.setBold(True)
        painter.setFont(font)

        metrics = painter.fontMetrics()
        target_width = min(
            max(46, metrics.horizontalAdvance(display_text) + 18),
            max(46, option.rect.width() - 12),
        )
        target_height = min(26, max(20, option.rect.height() - 12))

        pill = option.rect
        pill.setWidth(target_width)
        pill.setHeight(target_height)
        pill.moveCenter(option.rect.center())

        fill = QColor(accent)
        fill.setAlpha(34)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(pill, 8, 8)

        painter.setPen(accent)
        painter.drawText(
            pill,
            Qt.AlignmentFlag.AlignCenter,
            display_text,
        )
        painter.restore()


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
                return int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        if role == Qt.ItemDataRole.UserRole:
            return tender.number

        if role == Qt.ItemDataRole.ToolTipRole:
            return (
                f"{tender.number}\n{tender.title}\n{tender.customer}\n{tender.recommendation}"
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

        if orientation == Qt.Orientation.Vertical and role == Qt.ItemDataRole.DisplayRole:
            return section + 1

        return None

    def tender_at(self, row: int) -> RecentTender | None:
        if 0 <= row < len(self._tenders):
            return self._tenders[row]
        return None


class TenderFeed(QWidget):
    """Dashboard table with current tender status and AI score."""

    tender_open_requested = Signal(str)
    state_action_requested = Signal(str)

    def __init__(
        self,
        tenders: Sequence[RecentTender] = (),
        *,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._theme = ThemeName(theme)
        self._data_state = DataState.ready()
        self._density = TenderFeedDensity.DETAILED
        self.setObjectName("TenderFeed")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.state_panel = DataStatePanel(
            theme=self._theme,
            parent=self,
        )
        self.state_panel.action_requested.connect(self.state_action_requested)
        layout.addWidget(self.state_panel)

        self.table = QTableView(self)
        self.table.setObjectName("TenderFeedTable")
        self.table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.table.setAccessibleName("Последние тендеры")
        self.table.setAccessibleDescription("Стрелки меняют строку, Enter открывает тендер.")
        self.table.setModel(TenderFeedModel(tenders, self.table))
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setSortingEnabled(False)
        self.table.setWordWrap(False)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(46)
        self.table.setItemDelegate(
            TenderFeedDelegate(
                theme=self._theme,
                parent=self.table,
            )
        )

        header = self.table.horizontalHeader()
        header.setHighlightSections(False)
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(70)
        self._configure_columns()

        self.table.activated.connect(self._open_selected)
        layout.addWidget(self.table)

        self.apply_theme(self._theme)
        self.set_data_state(
            DataState.ready()
            if tenders
            else DataState.empty("Новые тендеры появятся после запуска поиска.")
        )

    @property
    def data_state(self) -> DataState:
        return self._data_state

    @property
    def density(self) -> TenderFeedDensity:
        return self._density

    @property
    def visible_column_keys(self) -> tuple[str, ...]:
        return VISIBLE_COLUMNS[self._density]

    @staticmethod
    def density_for_width(width: int) -> TenderFeedDensity:
        normalized = max(0, int(width))
        if normalized < 560:
            return TenderFeedDensity.NARROW
        if normalized < 760:
            return TenderFeedDensity.COMPACT
        if normalized < 980:
            return TenderFeedDensity.STANDARD
        return TenderFeedDensity.DETAILED

    def set_density(
        self,
        density: TenderFeedDensity | str,
    ) -> None:
        normalized = TenderFeedDensity(density)
        if normalized == self._density:
            return
        self._density = normalized
        self._configure_columns()

    @property
    def model(self) -> TenderFeedModel:
        model = self.table.model()
        assert isinstance(model, TenderFeedModel)
        return model

    def set_tenders(self, tenders: Sequence[RecentTender]) -> None:
        self.model.set_tenders(tenders)
        if self.model.rowCount() > 0:
            self.table.setCurrentIndex(self.model.index(0, 0))

    def set_data_state(self, state: DataState) -> None:
        """Apply a unified state to the table area."""
        self._data_state = state
        self.state_panel.set_state(state)

        content_visible = state.kind in {
            DataStateKind.READY,
            DataStateKind.PARTIAL,
        }
        self.table.setVisible(content_visible)
        self.table.setEnabled(content_visible)

        if state.kind == DataStateKind.READY:
            self.state_panel.hide()

    def set_state_compact(self, compact: bool) -> None:
        self.state_panel.set_compact(compact)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.set_density(self.density_for_width(event.size().width()))

    def _configure_columns(self) -> None:
        visible = set(VISIBLE_COLUMNS[self._density])
        header = self.table.horizontalHeader()

        for index, column in enumerate(COLUMNS):
            self.table.setColumnHidden(
                index,
                column.key not in visible,
            )

            if column.key == "title":
                header.setSectionResizeMode(
                    index,
                    QHeaderView.ResizeMode.Stretch,
                )
            elif column.key == "customer" and column.key in visible:
                header.setSectionResizeMode(
                    index,
                    QHeaderView.ResizeMode.Stretch,
                )
            else:
                header.setSectionResizeMode(
                    index,
                    QHeaderView.ResizeMode.Fixed,
                )
                compact_width = {
                    "number": 105,
                    "nmck": 118,
                    "deadline": 108,
                    "score": 84,
                    "status": 138,
                }.get(column.key, column.width)
                self.table.setColumnWidth(index, compact_width)

    def focus_table(self) -> None:
        """Move focus to content or to the recovery action."""
        if self._data_state.blocking:
            self.state_panel.focus_action()
            return

        if self.model.rowCount() > 0 and not self.table.currentIndex().isValid():
            self.table.setCurrentIndex(self.model.index(0, 0))
        self.table.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)

        self.state_panel.apply_theme(self._theme)
        delegate = self.table.itemDelegate()
        if isinstance(delegate, TenderFeedDelegate):
            delegate.set_theme(self._theme)

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
    "TenderFeedDelegate",
    "TenderFeedDensity",
    "TenderFeedModel",
    "VISIBLE_COLUMNS",
]
