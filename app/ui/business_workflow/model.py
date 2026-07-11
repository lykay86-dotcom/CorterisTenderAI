"""Models and transition rules for business workflow UI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import Any

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
)
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

from app.repositories.business_metrics import (
    BusinessRecordKind,
    BusinessStatus,
    BusinessWorkflowRecord,
)
from app.ui.theme.colors import ThemeName, get_palette


KIND_LABELS: dict[BusinessRecordKind, str] = {
    BusinessRecordKind.PROPOSAL: "Коммерческое предложение",
    BusinessRecordKind.ESTIMATE: "Смета",
    BusinessRecordKind.PROJECT: "Проект",
}

STATUS_LABELS: dict[BusinessStatus, str] = {
    BusinessStatus.DRAFT: "Черновик",
    BusinessStatus.REVIEW: "На проверке",
    BusinessStatus.APPROVED: "Согласовано",
    BusinessStatus.READY: "Готово к отправке",
    BusinessStatus.SENT: "Отправлено",
    BusinessStatus.ACCEPTED: "Принято заказчиком",
    BusinessStatus.PLANNED: "Запланировано",
    BusinessStatus.ACTIVE: "В работе",
    BusinessStatus.INSTALLATION: "Монтаж",
    BusinessStatus.COMMISSIONING: "Пусконаладка",
    BusinessStatus.COMPLETED: "Завершено",
    BusinessStatus.CANCELLED: "Отменено",
    BusinessStatus.BLOCKED: "Заблокировано",
}

KIND_STATUSES: dict[
    BusinessRecordKind,
    tuple[BusinessStatus, ...],
] = {
    BusinessRecordKind.ESTIMATE: (
        BusinessStatus.DRAFT,
        BusinessStatus.REVIEW,
        BusinessStatus.APPROVED,
        BusinessStatus.COMPLETED,
        BusinessStatus.BLOCKED,
        BusinessStatus.CANCELLED,
    ),
    BusinessRecordKind.PROPOSAL: (
        BusinessStatus.DRAFT,
        BusinessStatus.REVIEW,
        BusinessStatus.READY,
        BusinessStatus.SENT,
        BusinessStatus.ACCEPTED,
        BusinessStatus.COMPLETED,
        BusinessStatus.BLOCKED,
        BusinessStatus.CANCELLED,
    ),
    BusinessRecordKind.PROJECT: (
        BusinessStatus.PLANNED,
        BusinessStatus.ACTIVE,
        BusinessStatus.INSTALLATION,
        BusinessStatus.COMMISSIONING,
        BusinessStatus.COMPLETED,
        BusinessStatus.BLOCKED,
        BusinessStatus.CANCELLED,
    ),
}

ALLOWED_TRANSITIONS: dict[
    tuple[BusinessRecordKind, BusinessStatus],
    tuple[BusinessStatus, ...],
] = {
    (BusinessRecordKind.ESTIMATE, BusinessStatus.DRAFT): (
        BusinessStatus.REVIEW,
        BusinessStatus.CANCELLED,
    ),
    (BusinessRecordKind.ESTIMATE, BusinessStatus.REVIEW): (
        BusinessStatus.APPROVED,
        BusinessStatus.DRAFT,
        BusinessStatus.BLOCKED,
        BusinessStatus.CANCELLED,
    ),
    (BusinessRecordKind.ESTIMATE, BusinessStatus.APPROVED): (
        BusinessStatus.COMPLETED,
        BusinessStatus.REVIEW,
    ),
    (BusinessRecordKind.ESTIMATE, BusinessStatus.BLOCKED): (
        BusinessStatus.REVIEW,
        BusinessStatus.CANCELLED,
    ),
    (BusinessRecordKind.PROPOSAL, BusinessStatus.DRAFT): (
        BusinessStatus.REVIEW,
        BusinessStatus.CANCELLED,
    ),
    (BusinessRecordKind.PROPOSAL, BusinessStatus.REVIEW): (
        BusinessStatus.READY,
        BusinessStatus.DRAFT,
        BusinessStatus.BLOCKED,
        BusinessStatus.CANCELLED,
    ),
    (BusinessRecordKind.PROPOSAL, BusinessStatus.READY): (
        BusinessStatus.SENT,
        BusinessStatus.REVIEW,
        BusinessStatus.CANCELLED,
    ),
    (BusinessRecordKind.PROPOSAL, BusinessStatus.SENT): (
        BusinessStatus.ACCEPTED,
        BusinessStatus.BLOCKED,
        BusinessStatus.CANCELLED,
    ),
    (BusinessRecordKind.PROPOSAL, BusinessStatus.ACCEPTED): (
        BusinessStatus.COMPLETED,
    ),
    (BusinessRecordKind.PROPOSAL, BusinessStatus.BLOCKED): (
        BusinessStatus.REVIEW,
        BusinessStatus.CANCELLED,
    ),
    (BusinessRecordKind.PROJECT, BusinessStatus.PLANNED): (
        BusinessStatus.ACTIVE,
        BusinessStatus.CANCELLED,
    ),
    (BusinessRecordKind.PROJECT, BusinessStatus.ACTIVE): (
        BusinessStatus.INSTALLATION,
        BusinessStatus.BLOCKED,
        BusinessStatus.CANCELLED,
    ),
    (BusinessRecordKind.PROJECT, BusinessStatus.INSTALLATION): (
        BusinessStatus.COMMISSIONING,
        BusinessStatus.BLOCKED,
        BusinessStatus.CANCELLED,
    ),
    (BusinessRecordKind.PROJECT, BusinessStatus.COMMISSIONING): (
        BusinessStatus.COMPLETED,
        BusinessStatus.BLOCKED,
    ),
    (BusinessRecordKind.PROJECT, BusinessStatus.BLOCKED): (
        BusinessStatus.ACTIVE,
        BusinessStatus.INSTALLATION,
        BusinessStatus.COMMISSIONING,
        BusinessStatus.CANCELLED,
    ),
}


def kind_label(kind: BusinessRecordKind | str) -> str:
    try:
        return KIND_LABELS[BusinessRecordKind(kind)]
    except ValueError:
        return str(kind)


def status_label(status: BusinessStatus | str) -> str:
    try:
        return STATUS_LABELS[BusinessStatus(status)]
    except ValueError:
        return str(status)


def statuses_for_kind(
    kind: BusinessRecordKind | str,
) -> tuple[BusinessStatus, ...]:
    return KIND_STATUSES[BusinessRecordKind(kind)]


def allowed_transitions(
    kind: BusinessRecordKind | str,
    current: BusinessStatus | str,
) -> tuple[BusinessStatus, ...]:
    return ALLOWED_TRANSITIONS.get(
        (BusinessRecordKind(kind), BusinessStatus(current)),
        (),
    )


def preferred_next_status(
    kind: BusinessRecordKind | str,
    current: BusinessStatus | str,
) -> BusinessStatus | None:
    """Return the normal forward transition, excluding exceptional states."""
    exceptional = {
        BusinessStatus.CANCELLED,
        BusinessStatus.BLOCKED,
        BusinessStatus.DRAFT,
        BusinessStatus.REVIEW,
    }
    options = allowed_transitions(kind, current)
    for option in options:
        if option not in exceptional:
            return option
    return options[0] if options else None


class WorkflowRole(IntEnum):
    RECORD = int(Qt.ItemDataRole.UserRole) + 1
    KIND = int(Qt.ItemDataRole.UserRole) + 2
    STATUS = int(Qt.ItemDataRole.UserRole) + 3
    SORT = int(Qt.ItemDataRole.UserRole) + 4


@dataclass(frozen=True, slots=True)
class WorkflowColumn:
    key: str
    title: str
    width: int
    numeric: bool = False


WORKFLOW_COLUMNS: tuple[WorkflowColumn, ...] = (
    WorkflowColumn("kind", "Тип", 155),
    WorkflowColumn("title", "Наименование", 310),
    WorkflowColumn("tender_id", "Тендер", 110),
    WorkflowColumn("status", "Статус", 155),
    WorkflowColumn("total", "Сумма", 135, True),
    WorkflowColumn("profit", "Прибыль", 125, True),
    WorkflowColumn("margin", "Маржа", 82, True),
    WorkflowColumn("due_date", "Срок", 105),
    WorkflowColumn("updated_at", "Обновлено", 135),
)


class WorkflowTableModel(QAbstractTableModel):
    """Table model for estimates, proposals and projects."""

    def __init__(
        self,
        records: list[BusinessWorkflowRecord] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._records: list[BusinessWorkflowRecord] = []
        self.set_records(records or [])

    @property
    def records(self) -> tuple[BusinessWorkflowRecord, ...]:
        return tuple(self._records)

    def set_records(
        self,
        records: list[BusinessWorkflowRecord],
    ) -> None:
        self.beginResetModel()
        self._records = sorted(
            records,
            key=self._updated_datetime,
            reverse=True,
        )
        self.endResetModel()

    def record_at(self, row: int) -> BusinessWorkflowRecord | None:
        if 0 <= row < len(self._records):
            return self._records[row]
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._records)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(WORKFLOW_COLUMNS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
            and 0 <= section < len(WORKFLOW_COLUMNS)
        ):
            return WORKFLOW_COLUMNS[section].title
        return None

    def data(
        self,
        index: QModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid():
            return None

        record = self.record_at(index.row())
        if record is None:
            return None

        column = WORKFLOW_COLUMNS[index.column()]
        kind = self._kind(record)
        status = self._status(record)

        if role == WorkflowRole.RECORD:
            return record
        if role == WorkflowRole.KIND:
            return kind.value
        if role == WorkflowRole.STATUS:
            return status.value
        if role == WorkflowRole.SORT:
            return self._sort_value(record, column.key)

        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(
                Qt.AlignmentFlag.AlignRight
                | Qt.AlignmentFlag.AlignVCenter
                if column.numeric
                else Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignVCenter
            )

        if role == Qt.ItemDataRole.ToolTipRole:
            return self._tooltip(record)

        if role != Qt.ItemDataRole.DisplayRole:
            return None

        values: dict[str, str] = {
            "kind": kind_label(kind),
            "title": record.title,
            "tender_id": record.tender_id or "—",
            "status": status_label(status),
            "total": self._money(record.total),
            "profit": self._money(record.profit),
            "margin": (
                f"{record.margin_percent:.1f}%"
                if record.margin_percent
                else "—"
            ),
            "due_date": record.due_date or "—",
            "updated_at": self._format_datetime(record.updated_at),
        }
        return values[column.key]

    @staticmethod
    def _kind(record: BusinessWorkflowRecord) -> BusinessRecordKind:
        try:
            return BusinessRecordKind(record.kind)
        except ValueError:
            return BusinessRecordKind.PROPOSAL

    @staticmethod
    def _status(record: BusinessWorkflowRecord) -> BusinessStatus:
        try:
            return BusinessStatus(record.status)
        except ValueError:
            return BusinessStatus.DRAFT

    @staticmethod
    def _money(value: float) -> str:
        return f"{value:,.0f} ₽".replace(",", " ")

    @staticmethod
    def _format_datetime(value: str) -> str:
        try:
            return datetime.fromisoformat(value).strftime("%d.%m.%Y %H:%M")
        except ValueError:
            return value or "—"

    @staticmethod
    def _updated_datetime(
        record: BusinessWorkflowRecord,
    ) -> datetime:
        try:
            return datetime.fromisoformat(record.updated_at)
        except ValueError:
            return datetime.min

    def _sort_value(
        self,
        record: BusinessWorkflowRecord,
        key: str,
    ) -> Any:
        if key in {"total", "profit"}:
            return float(getattr(record, key))
        if key == "margin":
            return float(record.margin_percent)
        if key == "updated_at":
            return self._updated_datetime(record)
        if key == "kind":
            return kind_label(record.kind)
        if key == "status":
            return status_label(record.status)
        return str(getattr(record, key, "")).lower()

    @staticmethod
    def _tooltip(record: BusinessWorkflowRecord) -> str:
        parts = [
            record.title,
            f"Тендер: {record.tender_id or 'не указан'}",
            f"Статус: {status_label(record.status)}",
        ]
        if record.file_path:
            parts.append(f"Файл: {record.file_path}")
        return "\n".join(parts)


class WorkflowFilterProxyModel(QSortFilterProxyModel):
    """Search, kind and status filtering for the workflow table."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._search = ""
        self._kind = ""
        self._status = ""
        self.setDynamicSortFilter(True)
        self.setSortRole(WorkflowRole.SORT)

    def set_search(self, text: str) -> None:
        self._search = text.strip().lower()
        self._refresh_rows()

    def set_kind(
        self,
        kind: BusinessRecordKind | str | None,
    ) -> None:
        self._kind = (
            BusinessRecordKind(kind).value
            if kind not in {None, ""}
            else ""
        )
        self._refresh_rows()

    def set_status(
        self,
        status: BusinessStatus | str | None,
    ) -> None:
        self._status = (
            BusinessStatus(status).value
            if status not in {None, ""}
            else ""
        )
        self._refresh_rows()

    def _refresh_rows(self) -> None:
        """Refresh row filtering without deprecated Qt API calls."""
        begin_change = getattr(self, "beginFilterChange", None)
        end_change = getattr(self, "endFilterChange", None)
        direction_enum = getattr(
            QSortFilterProxyModel,
            "Direction",
            None,
        )

        if callable(begin_change) and callable(end_change):
            begin_change()
            if direction_enum is not None:
                end_change(direction_enum.Rows)
            else:
                end_change()
            return

        # Compatibility fallback for PySide6 versions before
        # beginFilterChange()/endFilterChange().
        self.invalidateFilter()

    def filterAcceptsRow(
        self,
        source_row: int,
        source_parent: QModelIndex,
    ) -> bool:
        model = self.sourceModel()
        if not isinstance(model, WorkflowTableModel):
            return True

        record = model.record_at(source_row)
        if record is None:
            return False

        if self._kind and record.kind != self._kind:
            return False
        if self._status and record.status != self._status:
            return False

        if not self._search:
            return True

        haystack = " ".join(
            (
                record.title,
                record.tender_id,
                record.kind,
                record.status,
                record.file_path,
                kind_label(record.kind),
                status_label(record.status),
            )
        ).lower()
        return self._search in haystack


class WorkflowStatusDelegate(QStyledItemDelegate):
    """Paint status cells as semantic pills."""

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

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        if WORKFLOW_COLUMNS[index.column()].key != "status":
            super().paint(painter, option, index)
            return

        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "—")
        raw_status = str(index.data(WorkflowRole.STATUS) or "")
        option_copy = QStyleOptionViewItem(option)
        self.initStyleOption(option_copy, index)
        option_copy.text = ""

        style = (
            option_copy.widget.style()
            if option_copy.widget is not None
            else QApplication.style()
        )
        style.drawControl(
            QStyle.ControlElement.CE_ItemViewItem,
            option_copy,
            painter,
            option_copy.widget,
        )

        palette = get_palette(self._theme)
        color = {
            BusinessStatus.COMPLETED.value: palette.success,
            BusinessStatus.ACCEPTED.value: palette.success,
            BusinessStatus.APPROVED.value: palette.success,
            BusinessStatus.READY.value: palette.info,
            BusinessStatus.SENT.value: palette.info,
            BusinessStatus.ACTIVE.value: palette.info,
            BusinessStatus.INSTALLATION.value: palette.warning,
            BusinessStatus.COMMISSIONING.value: palette.warning,
            BusinessStatus.REVIEW.value: palette.warning,
            BusinessStatus.BLOCKED.value: palette.danger,
            BusinessStatus.CANCELLED.value: palette.danger,
        }.get(raw_status, palette.neutral)

        accent = QColor(color)
        fill = QColor(accent)
        fill.setAlpha(34)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = option.font
        font.setBold(True)
        painter.setFont(font)

        width = min(
            painter.fontMetrics().horizontalAdvance(text) + 18,
            max(48, option.rect.width() - 10),
        )
        height = min(26, max(20, option.rect.height() - 10))
        pill = option.rect
        pill.setWidth(width)
        pill.setHeight(height)
        pill.moveCenter(option.rect.center())

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(pill, 8, 8)
        painter.setPen(accent)
        painter.drawText(
            pill,
            Qt.AlignmentFlag.AlignCenter,
            text,
        )
        painter.restore()


__all__ = [
    "ALLOWED_TRANSITIONS",
    "KIND_LABELS",
    "KIND_STATUSES",
    "STATUS_LABELS",
    "WORKFLOW_COLUMNS",
    "WorkflowColumn",
    "WorkflowFilterProxyModel",
    "WorkflowRole",
    "WorkflowStatusDelegate",
    "WorkflowTableModel",
    "allowed_transitions",
    "kind_label",
    "preferred_next_status",
    "status_label",
    "statuses_for_kind",
]
