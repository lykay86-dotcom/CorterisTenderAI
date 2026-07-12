"""Qt notification history for Tender Collector."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.tenders.collector.notifications import (
    CollectorNotification,
)
from app.ui.theme.colors import ThemeName, get_palette


class TenderCollectorNotificationsDialog(QDialog):
    """Show persisted in-application collector notifications."""

    mark_all_read_requested = Signal()
    registry_requested = Signal()

    def __init__(
        self,
        *,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = ThemeName(theme)
        self.setWindowTitle(
            "Уведомления Tender Collector"
        )
        self.resize(880, 520)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        title = QLabel("Уведомления сборщика", self)
        title.setObjectName("NotificationTitle")
        root.addWidget(title)

        self.table = QTableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ("Дата", "Тип", "Событие", "Сообщение")
        )
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(
            True
        )
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        root.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.read_button = QPushButton(
            "Отметить всё прочитанным",
            self,
        )
        self.registry_button = QPushButton(
            "Открыть реестр",
            self,
        )
        actions.addWidget(self.read_button)
        actions.addWidget(self.registry_button)
        actions.addStretch(1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close,
            self,
        )
        buttons.button(
            QDialogButtonBox.StandardButton.Close
        ).setText("Закрыть")
        buttons.rejected.connect(self.reject)
        actions.addWidget(buttons)
        root.addLayout(actions)

        self.read_button.clicked.connect(
            self.mark_all_read_requested.emit
        )
        self.registry_button.clicked.connect(
            self.registry_requested.emit
        )
        self.apply_theme(self._theme)

    def set_notifications(
        self,
        items: Iterable[CollectorNotification],
    ) -> None:
        notifications = tuple(items)
        self.table.setRowCount(len(notifications))
        for row, item in enumerate(notifications):
            self.table.setItem(
                row,
                0,
                QTableWidgetItem(
                    _format_time(item.created_at)
                ),
            )
            self.table.setItem(
                row,
                1,
                QTableWidgetItem(item.kind.value),
            )
            title = (
                item.title
                if not item.read
                else f"{item.title} · прочитано"
            )
            self.table.setItem(
                row,
                2,
                QTableWidgetItem(title),
            )
            message = QTableWidgetItem(item.message)
            message.setToolTip(item.message)
            self.table.setItem(row, 3, message)

    def apply_theme(
        self,
        theme: ThemeName | str,
    ) -> None:
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)
        self.setStyleSheet(
            f"""
            QDialog {{
                color: {palette.text_primary};
                background-color: {palette.app_background};
            }}
            QLabel#NotificationTitle {{
                font-size: 21px;
                font-weight: 700;
            }}
            QTableWidget {{
                color: {palette.text_primary};
                background-color: {palette.input_background};
                alternate-background-color: {palette.panel_background};
                border: 1px solid {palette.border_default};
            }}
            QPushButton {{
                min-height: 31px;
                color: {palette.text_primary};
                background-color: {palette.elevated_background};
                border: 1px solid {palette.border_default};
                border-radius: 7px;
                padding: 4px 10px;
                font-weight: 600;
            }}
            """
        )


def _format_time(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except ValueError:
        return value
    return parsed.astimezone().strftime(
        "%d.%m.%Y %H:%M"
    )


__all__ = ["TenderCollectorNotificationsDialog"]
