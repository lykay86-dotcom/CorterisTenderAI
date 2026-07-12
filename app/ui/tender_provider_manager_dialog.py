"""Qt interface for enabling and checking tender sources."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.tenders.collector.provider_control import (
    ProviderDisplayState,
    ProviderUiState,
)
from app.ui.theme.colors import ThemeName, get_palette


class TenderProviderManagerDialog(QDialog):
    """Display source switches, health and explicit connection checks."""

    provider_enabled_changed = Signal(str, bool)
    provider_check_requested = Signal(str)
    check_all_requested = Signal()

    def __init__(
        self,
        states: Iterable[ProviderDisplayState] = (),
        *,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        try:
            self._theme = ThemeName(theme)
        except (ValueError, TypeError, AttributeError):
            self._theme = ThemeName.DARK

        self._states: tuple[ProviderDisplayState, ...] = ()
        self._checking: set[str] = set()
        self._updating_table = False
        self._check_buttons: dict[str, QPushButton] = {}

        self.setWindowTitle(
            "Corteris Tender Collector — источники"
        )
        self.setModal(False)
        self.resize(1220, 720)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        heading = QFrame(self)
        heading.setObjectName("ProviderHeading")
        heading_layout = QVBoxLayout(heading)
        heading_layout.setContentsMargins(14, 12, 14, 12)
        title = QLabel("Источники тендеров", heading)
        title.setObjectName("ProviderTitle")
        subtitle = QLabel(
            (
                "Включайте источники и проверяйте соединение вручную. "
                "Открытие окна не выполняет сетевых запросов."
            ),
            heading,
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("ProviderSubtitle")
        heading_layout.addWidget(title)
        heading_layout.addWidget(subtitle)
        root.addWidget(heading)

        self.table = QTableWidget(self)
        self.table.setObjectName("TenderProviderTable")
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            (
                "Вкл.",
                "Состояние",
                "Источник",
                "Режим подключения",
                "Последняя успешная",
                "Последняя ошибка",
                "Проверка",
            )
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            5,
            QHeaderView.ResizeMode.Stretch,
        )
        self.table.itemChanged.connect(
            self._on_item_changed
        )
        self.table.itemSelectionChanged.connect(
            self._render_selected_details
        )
        root.addWidget(self.table, 1)

        details_frame = QFrame(self)
        details_frame.setObjectName("ProviderDetailsFrame")
        details_layout = QVBoxLayout(details_frame)
        details_layout.setContentsMargins(12, 10, 12, 10)
        details_title = QLabel(
            "Подробности выбранного источника",
            details_frame,
        )
        details_title.setObjectName("ProviderDetailsTitle")
        self.details = QTextBrowser(details_frame)
        self.details.setObjectName("ProviderDetails")
        self.details.setOpenExternalLinks(True)
        self.details.setMaximumHeight(170)
        details_layout.addWidget(details_title)
        details_layout.addWidget(self.details)
        root.addWidget(details_frame)

        actions = QHBoxLayout()
        self.check_all_button = QPushButton(
            "Проверить все включённые",
            self,
        )
        self.check_all_button.setObjectName(
            "PrimaryActionButton"
        )
        self.check_all_button.clicked.connect(
            self.check_all_requested.emit
        )
        self.refresh_button = QPushButton(
            "Обновить состояния",
            self,
        )
        actions.addWidget(self.check_all_button)
        actions.addWidget(self.refresh_button)
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

        self.status_label = QLabel("", self)
        self.status_label.setObjectName("ProviderStatusMessage")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.apply_theme(self._theme)
        self.set_states(tuple(states))

    @property
    def states(self) -> tuple[ProviderDisplayState, ...]:
        return self._states

    def set_states(
        self,
        states: Iterable[ProviderDisplayState],
    ) -> None:
        selected_id = self.selected_provider_id()
        self._states = tuple(states)
        self._updating_table = True
        try:
            self.table.setRowCount(len(self._states))
            self._check_buttons.clear()
            for row, state in enumerate(self._states):
                self._populate_row(row, state)
        finally:
            self._updating_table = False

        selected_row = 0
        for row, state in enumerate(self._states):
            if state.provider_id == selected_id:
                selected_row = row
                break
        if self._states:
            self.table.selectRow(selected_row)
        self._render_selected_details()
        self._update_check_all_state()

    def set_checking(
        self,
        provider_ids: Iterable[str],
        checking: bool,
    ) -> None:
        normalized = {
            item.strip().casefold()
            for item in provider_ids
            if item.strip()
        }
        if checking:
            self._checking.update(normalized)
        else:
            self._checking.difference_update(normalized)

        for provider_id, button in self._check_buttons.items():
            active = provider_id in self._checking
            state = self._state_by_id(provider_id)
            button.setEnabled(
                not active and state is not None and state.enabled
            )
            button.setText(
                "Проверка…"
                if active
                else "Проверить"
            )
        self._update_check_all_state()

    def selected_provider_id(self) -> str:
        row = self.table.currentRow()
        if not 0 <= row < len(self._states):
            return ""
        return self._states[row].provider_id

    def set_status(
        self,
        message: str,
        *,
        error: bool = False,
    ) -> None:
        self.status_label.setText(message)
        self.status_label.setProperty("error", error)
        self.status_label.style().unpolish(
            self.status_label
        )
        self.status_label.style().polish(
            self.status_label
        )

    def _populate_row(
        self,
        row: int,
        state: ProviderDisplayState,
    ) -> None:
        enabled_item = QTableWidgetItem()
        enabled_item.setFlags(
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsUserCheckable
        )
        enabled_item.setCheckState(
            Qt.CheckState.Checked
            if state.enabled
            else Qt.CheckState.Unchecked
        )
        enabled_item.setData(
            Qt.ItemDataRole.UserRole,
            state.provider_id,
        )
        self.table.setItem(row, 0, enabled_item)

        status_item = QTableWidgetItem(
            f"● {state.status_text}"
        )
        status_item.setForeground(
            QColor(self._status_color(state.ui_state))
        )
        status_item.setData(
            Qt.ItemDataRole.UserRole,
            state.provider_id,
        )
        self.table.setItem(row, 1, status_item)

        self.table.setItem(
            row,
            2,
            QTableWidgetItem(state.display_name),
        )
        self.table.setItem(
            row,
            3,
            QTableWidgetItem(state.connection_mode),
        )
        self.table.setItem(
            row,
            4,
            QTableWidgetItem(
                _format_timestamp(state.last_success_at)
            ),
        )
        error_item = QTableWidgetItem(
            state.last_error or "—"
        )
        error_item.setToolTip(state.last_error)
        self.table.setItem(row, 5, error_item)

        button = QPushButton("Проверить", self.table)
        button.setObjectName(
            f"checkProvider_{state.provider_id}"
        )
        button.setEnabled(
            state.enabled
            and state.provider_id not in self._checking
        )
        button.clicked.connect(
            lambda _checked=False, provider_id=state.provider_id: (
                self.provider_check_requested.emit(provider_id)
            )
        )
        self._check_buttons[state.provider_id] = button
        self.table.setCellWidget(row, 6, button)

    def _on_item_changed(
        self,
        item: QTableWidgetItem,
    ) -> None:
        if self._updating_table or item.column() != 0:
            return
        provider_id = str(
            item.data(Qt.ItemDataRole.UserRole) or ""
        ).strip()
        if not provider_id:
            return
        enabled = (
            item.checkState() == Qt.CheckState.Checked
        )
        self.provider_enabled_changed.emit(
            provider_id,
            enabled,
        )

    def _render_selected_details(self) -> None:
        provider_id = self.selected_provider_id()
        state = self._state_by_id(provider_id)
        if state is None:
            self.details.clear()
            return

        latency = (
            f"{state.latency_ms} мс"
            if state.latency_ms is not None
            else "не измерена"
        )
        configuration = "<br>".join(
            _escape_html(item)
            for item in state.configuration_details
        )
        self.details.setHtml(
            (
                f"<b>{_escape_html(state.display_name)}</b><br>"
                f"ID: <code>{_escape_html(state.provider_id)}</code><br>"
                f"Состояние: {_escape_html(state.status_text)}<br>"
                f"Режим: {_escape_html(state.connection_mode)}<br>"
                f"Реализация: "
                f"{_escape_html(state.implementation_status)}<br>"
                f"Последняя проверка: "
                f"{_format_timestamp(state.last_checked_at)}<br>"
                f"Последний успех: "
                f"{_format_timestamp(state.last_success_at)}<br>"
                f"Задержка: {_escape_html(latency)}<br>"
                f"Последняя ошибка: "
                f"{_escape_html(state.last_error or '—')}<br><br>"
                f"{configuration}<br><br>"
                f'<a href="{_escape_html(state.homepage_url)}">'
                "Открыть сайт источника</a>"
            )
        )

    def _state_by_id(
        self,
        provider_id: str,
    ) -> ProviderDisplayState | None:
        for state in self._states:
            if state.provider_id == provider_id:
                return state
        return None

    def _update_check_all_state(self) -> None:
        enabled_count = sum(
            state.enabled for state in self._states
        )
        self.check_all_button.setEnabled(
            bool(enabled_count) and not self._checking
        )

    def _status_color(
        self,
        state: ProviderUiState,
    ) -> str:
        palette = get_palette(self._theme)
        return {
            ProviderUiState.WORKING: palette.success,
            ProviderUiState.LIMITED: palette.warning,
            ProviderUiState.ERROR: palette.danger,
            ProviderUiState.DISABLED: palette.neutral,
            ProviderUiState.NOT_CONFIGURED: palette.warning,
            ProviderUiState.UNKNOWN: palette.info,
            ProviderUiState.UNVERIFIED: palette.info,
        }[state]

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
            QFrame#ProviderHeading,
            QFrame#ProviderDetailsFrame {{
                background-color: {palette.card_background};
                border: 1px solid {palette.border_default};
                border-radius: 9px;
            }}
            QLabel#ProviderTitle {{
                color: {palette.text_primary};
                font-size: 21px;
                font-weight: 700;
            }}
            QLabel#ProviderSubtitle,
            QLabel#ProviderStatusMessage {{
                color: {palette.text_secondary};
            }}
            QLabel#ProviderStatusMessage[error="true"] {{
                color: {palette.danger};
            }}
            QLabel#ProviderDetailsTitle {{
                color: {palette.text_primary};
                font-weight: 700;
            }}
            QTableWidget#TenderProviderTable {{
                color: {palette.text_primary};
                background-color: {palette.input_background};
                alternate-background-color: {palette.panel_background};
                border: 1px solid {palette.border_default};
                gridline-color: {palette.divider};
                selection-background-color: {palette.selected_background};
                selection-color: {palette.text_primary};
            }}
            QHeaderView::section {{
                color: {palette.text_secondary};
                background-color: {palette.elevated_background};
                border: none;
                border-right: 1px solid {palette.divider};
                border-bottom: 1px solid {palette.divider};
                padding: 7px;
                font-weight: 600;
            }}
            QTextBrowser#ProviderDetails {{
                color: {palette.text_primary};
                background-color: {palette.input_background};
                border: 1px solid {palette.border_default};
                border-radius: 6px;
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
            QPushButton:hover {{
                background-color: {palette.hover_background};
            }}
            QPushButton:disabled {{
                color: {palette.text_disabled};
                background-color: {palette.neutral_background};
            }}
            QPushButton#PrimaryActionButton {{
                color: {palette.text_on_brand};
                background-color: {palette.brand_primary};
                border-color: {palette.brand_primary};
            }}
            """
        )


def _format_timestamp(value: str) -> str:
    if not value:
        return "—"
    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except ValueError:
        return value
    return parsed.astimezone().strftime(
        "%d.%m.%Y %H:%M"
    )


def _escape_html(value: str) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


__all__ = ["TenderProviderManagerDialog"]
