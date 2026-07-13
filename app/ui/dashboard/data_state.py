"""Unified loading, empty, error and partial data states."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme.colors import ThemeName, get_palette
from app.ui.theme.typography import Typography


class DataStateKind(StrEnum):
    """Availability state of data displayed by a Dashboard component."""

    READY = "ready"
    LOADING = "loading"
    EMPTY = "empty"
    ERROR = "error"
    PARTIAL = "partial"


@dataclass(frozen=True, slots=True)
class DataState:
    """Semantic state shared by Dashboard data components."""

    kind: DataStateKind = DataStateKind.READY
    title: str = ""
    message: str = ""
    action_text: str = ""
    action_key: str = ""

    @property
    def blocking(self) -> bool:
        return self.kind in {
            DataStateKind.LOADING,
            DataStateKind.EMPTY,
            DataStateKind.ERROR,
        }

    @property
    def has_action(self) -> bool:
        return bool(self.action_text.strip() and self.action_key.strip())

    @classmethod
    def ready(cls) -> DataState:
        return cls(DataStateKind.READY)

    @classmethod
    def loading(
        cls,
        message: str = "Получаем актуальные данные.",
    ) -> DataState:
        return cls(
            DataStateKind.LOADING,
            title="Загрузка данных",
            message=message,
        )

    @classmethod
    def empty(
        cls,
        message: str = "Данных пока нет.",
        *,
        action_text: str = "Найти тендеры",
        action_key: str = "find_tenders",
    ) -> DataState:
        return cls(
            DataStateKind.EMPTY,
            title="Нет данных",
            message=message,
            action_text=action_text,
            action_key=action_key,
        )

    @classmethod
    def error(
        cls,
        message: str,
        *,
        action_text: str = "Повторить",
        action_key: str = "refresh_dashboard",
    ) -> DataState:
        return cls(
            DataStateKind.ERROR,
            title="Не удалось загрузить данные",
            message=message,
            action_text=action_text,
            action_key=action_key,
        )

    @classmethod
    def partial(
        cls,
        message: str = "Часть данных временно недоступна.",
        *,
        action_text: str = "Обновить",
        action_key: str = "refresh_dashboard",
    ) -> DataState:
        return cls(
            DataStateKind.PARTIAL,
            title="Данные загружены частично",
            message=message,
            action_text=action_text,
            action_key=action_key,
        )


class DataStatePanel(QFrame):
    """Reusable semantic panel displayed above or instead of content."""

    action_requested = Signal(str)

    def __init__(
        self,
        *,
        theme: ThemeName | str = ThemeName.DARK,
        compact: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._theme = ThemeName(theme)
        self._state = DataState.ready()
        self._compact = bool(compact)

        self.setObjectName("DataStatePanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAccessibleName("Состояние данных")

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(11)

        self.indicator_label = QLabel("i", self)
        self.indicator_label.setObjectName("DataStateIndicator")
        self.indicator_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.indicator_label.setFixedSize(30, 30)

        self.progress = QProgressBar(self)
        self.progress.setObjectName("DataStateProgress")
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedSize(30, 8)
        self.progress.hide()

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(2)

        self.title_label = QLabel("", self)
        self.title_label.setObjectName("DataStateTitle")

        self.message_label = QLabel("", self)
        self.message_label.setObjectName("DataStateMessage")
        self.message_label.setWordWrap(True)

        text_column.addWidget(self.title_label)
        text_column.addWidget(self.message_label)

        self.action_button = QPushButton("", self)
        self.action_button.setObjectName("DataStateAction")
        self.action_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.action_button.clicked.connect(self._emit_action)
        self.action_button.hide()

        root.addWidget(
            self.indicator_label,
            0,
            Qt.AlignmentFlag.AlignTop,
        )
        root.addWidget(
            self.progress,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )
        root.addLayout(text_column, 1)
        root.addWidget(
            self.action_button,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )

        self.set_state(self._state)

    @property
    def state(self) -> DataState:
        return self._state

    def set_state(self, state: DataState) -> None:
        """Render a semantic data state."""
        self._state = state
        if state.kind == DataStateKind.READY:
            self.hide()
            return

        defaults = {
            DataStateKind.LOADING: (
                "Загрузка данных",
                "Получаем актуальную информацию.",
            ),
            DataStateKind.EMPTY: (
                "Нет данных",
                "Данные появятся после первой загрузки.",
            ),
            DataStateKind.ERROR: (
                "Не удалось загрузить данные",
                "Повторите попытку.",
            ),
            DataStateKind.PARTIAL: (
                "Данные загружены частично",
                "Часть информации временно недоступна.",
            ),
        }
        default_title, default_message = defaults[state.kind]

        self.title_label.setText(state.title.strip() or default_title)
        self.message_label.setText(state.message.strip() or default_message)
        self.message_label.setVisible(bool(self.message_label.text()))

        is_loading = state.kind == DataStateKind.LOADING
        self.indicator_label.setVisible(not is_loading)
        self.progress.setVisible(is_loading)

        self.action_button.setText(state.action_text.strip())
        self.action_button.setVisible(state.has_action)

        description = " ".join(
            value
            for value in (
                self.title_label.text(),
                self.message_label.text(),
            )
            if value
        )
        self.setAccessibleDescription(description)
        self.apply_theme(self._theme)
        self.show()

    def set_compact(self, compact: bool) -> None:
        self._compact = bool(compact)
        layout = self.layout()
        if layout is not None:
            layout.setContentsMargins(
                10 if self._compact else 14,
                8 if self._compact else 12,
                10 if self._compact else 14,
                8 if self._compact else 12,
            )
        self.message_label.setVisible(bool(self.message_label.text()) and not self._compact)

    def focus_action(self) -> None:
        if self.action_button.isVisible():
            self.action_button.setFocus(Qt.FocusReason.ShortcutFocusReason)
        else:
            self.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)

        tone = {
            DataStateKind.READY: palette.success,
            DataStateKind.LOADING: palette.info,
            DataStateKind.EMPTY: palette.text_secondary,
            DataStateKind.ERROR: palette.danger,
            DataStateKind.PARTIAL: palette.warning,
        }[self._state.kind]

        indicator = {
            DataStateKind.READY: "✓",
            DataStateKind.LOADING: "…",
            DataStateKind.EMPTY: "—",
            DataStateKind.ERROR: "×",
            DataStateKind.PARTIAL: "!",
        }[self._state.kind]
        self.indicator_label.setText(indicator)

        self.setStyleSheet(
            f"""
            QFrame#DataStatePanel {{
                background-color: {palette.elevated_background};
                border: 1px solid {tone};
                border-radius: 10px;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
            QLabel#DataStateIndicator {{
                color: {tone};
                background-color: {palette.input_background};
                border: 1px solid {tone};
                border-radius: 8px;
                {Typography.BUTTON.css()}
            }}
            QLabel#DataStateTitle {{
                color: {palette.text_primary};
                {Typography.BUTTON.css()}
            }}
            QLabel#DataStateMessage {{
                color: {palette.text_muted};
                {Typography.BODY_S.css()}
            }}
            QProgressBar#DataStateProgress {{
                background-color: {palette.border_subtle};
                border: none;
                border-radius: 4px;
            }}
            QProgressBar#DataStateProgress::chunk {{
                background-color: {tone};
                border-radius: 4px;
            }}
            QPushButton#DataStateAction {{
                color: {tone};
                background: transparent;
                border: 1px solid {tone};
                border-radius: 7px;
                padding: 6px 10px;
                {Typography.CAPTION.css()}
            }}
            QPushButton#DataStateAction:hover {{
                background-color: {palette.hover_background};
            }}
            """
        )

    def _emit_action(self) -> None:
        if self._state.action_key:
            self.action_requested.emit(self._state.action_key)


__all__ = [
    "DataState",
    "DataStateKind",
    "DataStatePanel",
]
