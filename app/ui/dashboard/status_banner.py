"""Dashboard status and feedback banner."""

from __future__ import annotations

from enum import StrEnum

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme.colors import ThemeName, get_palette
from app.ui.theme.typography import Typography
from app.ui.theme.icons import IconId, get_icon_provider
from app.ui.theme.tokens import BorderWidth, Radius, Spacing


class StatusTone(StrEnum):
    """Semantic state of a Dashboard notification."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    LOADING = "loading"


class DashboardStatusBanner(QFrame):
    """Dismissible status banner with an optional recovery action."""

    action_requested = Signal(str)
    dismissed = Signal()

    def __init__(
        self,
        *,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._theme = ThemeName(theme)
        self._tone = StatusTone.INFO
        self._action_key = ""

        self.setObjectName("DashboardStatusBanner")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAccessibleName("Статус рабочего стола")

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.clear)

        root = QHBoxLayout(self)
        root.setContentsMargins(int(Spacing.M), int(Spacing.S), int(Spacing.S), int(Spacing.S))
        root.setSpacing(int(Spacing.M))

        self.icon_label = QLabel("i", self)
        self.icon_label.setObjectName("DashboardStatusIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedSize(28, 28)

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(2)

        self.title_label = QLabel("", self)
        self.title_label.setObjectName("DashboardStatusTitle")

        self.message_label = QLabel("", self)
        self.message_label.setObjectName("DashboardStatusMessage")
        self.message_label.setWordWrap(True)

        text_column.addWidget(self.title_label)
        text_column.addWidget(self.message_label)

        self.action_button = QPushButton("", self)
        self.action_button.setObjectName("DashboardStatusAction")
        self.action_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.action_button.clicked.connect(self._emit_action)
        self.action_button.hide()

        self.close_button = QToolButton(self)
        self.close_button.setObjectName("DashboardStatusClose")
        self.close_button.setIcon(get_icon_provider().icon(IconId.ACTION_CLOSE, theme=self._theme))
        self.close_button.setToolTip("Скрыть уведомление")
        self.close_button.setAccessibleName("Скрыть уведомление")
        self.close_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.close_button.clicked.connect(self.clear)

        root.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(text_column, 1)
        root.addWidget(
            self.action_button,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        root.addWidget(
            self.close_button,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
        )

        self.apply_theme(self._theme)
        self.hide()

    @property
    def tone(self) -> StatusTone:
        return self._tone

    @property
    def action_key(self) -> str:
        return self._action_key

    def show_status(
        self,
        *,
        title: str,
        message: str = "",
        tone: StatusTone | str = StatusTone.INFO,
        action_text: str = "",
        action_key: str = "",
        auto_hide_ms: int = 0,
        dismissible: bool = True,
    ) -> None:
        """Display a new status and optionally hide it automatically."""
        self._hide_timer.stop()
        self._tone = StatusTone(tone)
        self._action_key = action_key.strip()

        self.title_label.setText(title.strip() or "Статус")
        self.message_label.setText(message.strip())
        self.message_label.setVisible(bool(message.strip()))

        normalized_action = action_text.strip()
        self.action_button.setText(normalized_action)
        self.action_button.setVisible(bool(normalized_action and self._action_key))
        self.close_button.setVisible(bool(dismissible))

        description = " ".join(
            part
            for part in (
                self.title_label.text(),
                self.message_label.text(),
            )
            if part
        )
        self.setAccessibleDescription(description)

        self.apply_theme(self._theme)
        self.show()

        if auto_hide_ms > 0:
            self._hide_timer.start(max(250, int(auto_hide_ms)))

    def clear(self) -> None:
        """Hide the banner and cancel pending automatic dismissal."""
        self._hide_timer.stop()
        was_visible = not self.isHidden()
        self.hide()
        self._action_key = ""
        if was_visible:
            self.dismissed.emit()

    def apply_theme(self, theme: ThemeName | str) -> None:
        """Apply theme and semantic tone colors."""
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)
        self.close_button.setIcon(get_icon_provider().icon(IconId.ACTION_CLOSE, theme=self._theme))

        tone_color = {
            StatusTone.INFO: palette.info,
            StatusTone.SUCCESS: palette.success,
            StatusTone.WARNING: palette.warning,
            StatusTone.ERROR: palette.danger,
            StatusTone.LOADING: palette.brand_accent,
        }[self._tone]

        icon_text = {
            StatusTone.INFO: "i",
            StatusTone.SUCCESS: "✓",
            StatusTone.WARNING: "!",
            StatusTone.ERROR: "×",
            StatusTone.LOADING: "…",
        }[self._tone]
        self.icon_label.setText(icon_text)

        self.setStyleSheet(
            f"""
            QFrame#DashboardStatusBanner {{
                background-color: {palette.elevated_background};
                border: {int(BorderWidth.DEFAULT)}px solid {tone_color};
                border-radius: {int(Radius.LARGE)}px;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
            QLabel#DashboardStatusIcon {{
                color: {tone_color};
                background-color: {palette.input_background};
                border: {int(BorderWidth.DEFAULT)}px solid {tone_color};
                border-radius: {int(Radius.MEDIUM)}px;
                {Typography.BUTTON.css()}
            }}
            QLabel#DashboardStatusTitle {{
                color: {palette.text_primary};
                {Typography.BUTTON.css()}
            }}
            QLabel#DashboardStatusMessage {{
                color: {palette.text_muted};
                {Typography.BODY_S.css()}
            }}
            QPushButton#DashboardStatusAction {{
                color: {tone_color};
                background: transparent;
                border: {int(BorderWidth.DEFAULT)}px solid {tone_color};
                border-radius: {int(Radius.MEDIUM)}px;
                padding: {int(Spacing.S)}px {int(Spacing.M)}px;
                {Typography.CAPTION.css()}
            }}
            QPushButton#DashboardStatusAction:hover {{
                background-color: {palette.hover_background};
            }}
            QToolButton#DashboardStatusClose {{
                color: {palette.text_muted};
                background: transparent;
                border: none;
                border-radius: {int(Radius.MEDIUM)}px;
                padding: {int(Spacing.XS)}px;
                {Typography.BUTTON.css()}
            }}
            QToolButton#DashboardStatusClose:hover {{
                color: {palette.text_primary};
                background-color: {palette.hover_background};
            }}
            """
        )

    def _emit_action(self) -> None:
        if self._action_key:
            self.action_requested.emit(self._action_key)


__all__ = ["DashboardStatusBanner", "StatusTone"]
