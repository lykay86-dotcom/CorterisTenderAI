"""Activity Feed for Corteris Tender AI Dashboard 1.0."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QCursor,
    QFocusEvent,
    QKeyEvent,
    QMouseEvent,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme.colors import ThemeName, get_palette
from app.ui.theme.typography import Typography


class ActivityTone(StrEnum):
    """Visual category of an activity entry."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    DANGER = "danger"
    NEUTRAL = "neutral"


@dataclass(frozen=True, slots=True)
class ActivityEntry:
    """One event displayed in the Dashboard activity timeline."""

    key: str
    title: str
    description: str = ""
    timestamp: datetime | None = None
    tone: ActivityTone = ActivityTone.NEUTRAL
    icon_text: str = "•"
    action_text: str = ""
    action_key: str = ""

    @property
    def time_text(self) -> str:
        if self.timestamp is None:
            return ""
        return self.timestamp.strftime("%H:%M")


class ActivityFeedItem(QFrame):
    """One clickable timeline item."""

    activated = Signal(str)
    action_requested = Signal(str)

    def __init__(
        self,
        entry: ActivityEntry,
        *,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.entry = entry
        self._theme = ThemeName(theme)
        self._focused = False

        self.setObjectName("ActivityFeedItem")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(entry.title)
        self.setAccessibleDescription(entry.description)

        root = QHBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        self.icon_label = QLabel(entry.icon_text, self)
        self.icon_label.setObjectName("ActivityFeedIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedSize(30, 30)

        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(3)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)

        self.title_label = QLabel(entry.title, self)
        self.title_label.setObjectName("ActivityFeedTitle")
        self.title_label.setWordWrap(True)

        self.time_label = QLabel(entry.time_text, self)
        self.time_label.setObjectName("ActivityFeedTime")
        self.time_label.setVisible(bool(entry.time_text))

        title_row.addWidget(self.title_label, 1)
        title_row.addWidget(
            self.time_label,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
        )

        self.description_label = QLabel(entry.description, self)
        self.description_label.setObjectName("ActivityFeedDescription")
        self.description_label.setWordWrap(True)
        self.description_label.setVisible(bool(entry.description))

        content.addLayout(title_row)
        content.addWidget(self.description_label)

        root.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(content, 1)

        self.action_button = QPushButton(entry.action_text, self)
        self.action_button.setObjectName("ActivityFeedAction")
        self.action_button.setCursor(
            QCursor(Qt.CursorShape.PointingHandCursor)
        )
        self.action_button.setVisible(
            bool(entry.action_text and entry.action_key)
        )
        self.action_button.clicked.connect(
            lambda: self.action_requested.emit(entry.action_key)
        )
        root.addWidget(
            self.action_button,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )

        self.apply_theme(self._theme)

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)

        tone_color = {
            ActivityTone.INFO: palette.info,
            ActivityTone.SUCCESS: palette.success,
            ActivityTone.WARNING: palette.warning,
            ActivityTone.DANGER: palette.danger,
            ActivityTone.NEUTRAL: palette.text_secondary,
        }[self.entry.tone]
        background = (
            palette.hover_background
            if self._focused
            else palette.input_background
        )
        border = tone_color if self._focused else palette.border_subtle
        border_width = 2 if self._focused else 1

        self.setStyleSheet(
            f"""
            QFrame#ActivityFeedItem {{
                background-color: {background};
                border: {border_width}px solid {border};
                border-radius: 10px;
            }}
            QFrame#ActivityFeedItem:hover {{
                background-color: {palette.hover_background};
                border-color: {tone_color};
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
            QLabel#ActivityFeedIcon {{
                color: {tone_color};
                background-color: {palette.elevated_background};
                border: 1px solid {palette.border_subtle};
                border-radius: 8px;
                {Typography.BUTTON.css()}
            }}
            QLabel#ActivityFeedTitle {{
                color: {palette.text_primary};
                {Typography.BUTTON.css()}
            }}
            QLabel#ActivityFeedDescription {{
                color: {palette.text_muted};
                {Typography.BODY_S.css()}
            }}
            QLabel#ActivityFeedTime {{
                color: {palette.text_disabled};
                {Typography.CAPTION.css()}
            }}
            QPushButton#ActivityFeedAction {{
                color: {tone_color};
                background: transparent;
                border: 1px solid {tone_color};
                border-radius: 7px;
                padding: 5px 9px;
                {Typography.CAPTION.css()}
            }}
            QPushButton#ActivityFeedAction:hover {{
                background-color: {palette.hover_background};
            }}
            """
        )

    def focusInEvent(self, event: QFocusEvent) -> None:
        self._focused = True
        self.apply_theme(self._theme)
        super().focusInEvent(event)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        self._focused = False
        self.apply_theme(self._theme)
        super().focusOutEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in {
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Space,
        }:
            self.activated.emit(self.entry.key)
            event.accept()
            return
        super().keyPressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self.activated.emit(self.entry.key)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class ActivityFeed(QWidget):
    """Scrollable activity timeline with a useful empty state."""

    entry_activated = Signal(str)
    action_requested = Signal(str)

    def __init__(
        self,
        entries: Iterable[ActivityEntry] = (),
        *,
        theme: ThemeName | str = ThemeName.DARK,
        max_entries: int = 50,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        if max_entries < 1:
            raise ValueError("max_entries must be >= 1")

        self._theme = ThemeName(theme)
        self._max_entries = max_entries
        self._entries: list[ActivityEntry] = []
        self._items: list[ActivityFeedItem] = []

        self.setObjectName("ActivityFeed")
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea(self)
        self.scroll.setObjectName("ActivityFeedScroll")
        self.scroll.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.scroll.setAccessibleName("Лента событий")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.canvas = QWidget(self.scroll)
        self.canvas.setObjectName("ActivityFeedCanvas")
        self.items_layout = QVBoxLayout(self.canvas)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(8)

        self.empty_label = QLabel(
            "События появятся после поиска тендеров, анализа документов "
            "и создания коммерческих предложений.",
            self.canvas,
        )
        self.empty_label.setObjectName("ActivityFeedEmpty")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.empty_label.setMinimumHeight(140)

        self.items_layout.addWidget(self.empty_label)
        self.items_layout.addStretch(1)

        self.scroll.setWidget(self.canvas)
        root.addWidget(self.scroll)

        self.set_entries(entries)
        self.apply_theme(self._theme)

    @property
    def entries(self) -> tuple[ActivityEntry, ...]:
        return tuple(self._entries)

    @property
    def items(self) -> tuple[ActivityFeedItem, ...]:
        return tuple(self._items)

    def focus_first(self) -> None:
        """Move keyboard focus to the newest event."""
        if self._items:
            self._items[0].setFocus(
                Qt.FocusReason.ShortcutFocusReason
            )
        else:
            self.scroll.setFocus(
                Qt.FocusReason.ShortcutFocusReason
            )

    def set_entries(self, entries: Iterable[ActivityEntry]) -> None:
        """Replace entries and render newest events first."""
        normalized = sorted(
            list(entries),
            key=lambda entry: entry.timestamp or datetime.min,
            reverse=True,
        )
        self._entries = normalized[: self._max_entries]
        self._rebuild()

    def add_entry(self, entry: ActivityEntry) -> None:
        """Add one event and keep the configured history limit."""
        self.set_entries([entry, *self._entries])

    def clear(self) -> None:
        self._entries.clear()
        self._rebuild()

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)

        self.setStyleSheet(
            f"""
            QWidget#ActivityFeed,
            QWidget#ActivityFeedCanvas,
            QScrollArea#ActivityFeedScroll {{
                background: transparent;
                border: none;
            }}
            QLabel#ActivityFeedEmpty {{
                color: {palette.text_muted};
                background-color: {palette.input_background};
                border: 1px dashed {palette.border_subtle};
                border-radius: 10px;
                padding: 18px;
                {Typography.BODY_S.css()}
            }}
            """
        )

        for item in self._items:
            item.apply_theme(self._theme)

    def trigger_action(self, action_key: str) -> None:
        """Programmatically request an activity action."""
        if action_key:
            self.action_requested.emit(action_key)

    def _rebuild(self) -> None:
        while self.items_layout.count():
            item = self.items_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self._items.clear()

        if not self._entries:
            self.empty_label = QLabel(
                "События появятся после поиска тендеров, анализа документов "
                "и создания коммерческих предложений.",
                self.canvas,
            )
            self.empty_label.setObjectName("ActivityFeedEmpty")
            self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.empty_label.setWordWrap(True)
            self.empty_label.setMinimumHeight(140)
            self.items_layout.addWidget(self.empty_label)
        else:
            previous: ActivityFeedItem | None = None
            for entry in self._entries:
                item = ActivityFeedItem(
                    entry,
                    theme=self._theme,
                    parent=self.canvas,
                )
                item.activated.connect(self.entry_activated)
                item.action_requested.connect(self.action_requested)
                self._items.append(item)
                self.items_layout.addWidget(item)
                if previous is not None:
                    QWidget.setTabOrder(previous, item)
                previous = item

        self.items_layout.addStretch(1)
        self.apply_theme(self._theme)


__all__ = [
    "ActivityEntry",
    "ActivityFeed",
    "ActivityFeedItem",
    "ActivityTone",
]
