"""Quick Actions panel for Corteris Tender AI Dashboard 1.0."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor, QEnterEvent, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme.colors import ThemeName, get_palette
from app.ui.theme.typography import Typography


class QuickActionTone(StrEnum):
    """Visual tone of a quick action."""

    PRIMARY = "primary"
    INFO = "info"
    SUCCESS = "success"
    NEUTRAL = "neutral"


@dataclass(frozen=True, slots=True)
class QuickActionSpec:
    """Description of one dashboard action."""

    key: str
    title: str
    description: str
    icon_text: str
    tone: QuickActionTone = QuickActionTone.NEUTRAL
    shortcut: str = ""
    badge: str = ""


DEFAULT_QUICK_ACTIONS: tuple[QuickActionSpec, ...] = (
    QuickActionSpec(
        key="find_tenders",
        title="Найти тендеры",
        description="Открыть поиск и загрузить новые закупки.",
        icon_text="T",
        tone=QuickActionTone.PRIMARY,
        shortcut="Ctrl+F",
    ),
    QuickActionSpec(
        key="analyze_documents",
        title="AI-анализ",
        description="Проверить требования, риски и документацию.",
        icon_text="AI",
        tone=QuickActionTone.INFO,
        shortcut="Ctrl+A",
    ),
    QuickActionSpec(
        key="create_proposal",
        title="Создать КП",
        description="Подготовить коммерческое предложение по тендеру.",
        icon_text="КП",
        tone=QuickActionTone.SUCCESS,
        shortcut="Ctrl+K",
    ),
    QuickActionSpec(
        key="create_estimate",
        title="Создать смету",
        description="Рассчитать оборудование, работы и прибыль.",
        icon_text="₽",
        tone=QuickActionTone.NEUTRAL,
        shortcut="Ctrl+S",
    ),
)


class QuickActionTile(QFrame):
    """Clickable card-like action tile."""

    clicked = Signal(str)

    def __init__(
        self,
        spec: QuickActionSpec,
        *,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.spec = spec
        self._theme = ThemeName(theme)
        self._hovered = False
        self._pressed = False

        self.setObjectName("QuickActionTile")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self.setMinimumHeight(104)
        self.setAccessibleName(spec.title)
        self.setAccessibleDescription(spec.description)
        self.setToolTip(
            f"{spec.description}"
            + (f"\nГорячая клавиша: {spec.shortcut}" if spec.shortcut else "")
        )

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 13, 14, 13)
        root.setSpacing(12)

        self.icon_label = QLabel(spec.icon_text, self)
        self.icon_label.setObjectName("QuickActionIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedSize(40, 40)

        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(4)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(7)

        self.title_label = QLabel(spec.title, self)
        self.title_label.setObjectName("QuickActionTitle")

        self.badge_label = QLabel(spec.badge, self)
        self.badge_label.setObjectName("QuickActionBadge")
        self.badge_label.setVisible(bool(spec.badge))

        title_row.addWidget(self.title_label)
        title_row.addWidget(self.badge_label)
        title_row.addStretch(1)

        self.description_label = QLabel(spec.description, self)
        self.description_label.setObjectName("QuickActionDescription")
        self.description_label.setWordWrap(True)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)

        self.shortcut_label = QLabel(spec.shortcut, self)
        self.shortcut_label.setObjectName("QuickActionShortcut")
        self.shortcut_label.setVisible(bool(spec.shortcut))

        self.arrow_label = QLabel("→", self)
        self.arrow_label.setObjectName("QuickActionArrow")

        footer.addWidget(self.shortcut_label)
        footer.addStretch(1)
        footer.addWidget(self.arrow_label)

        content.addLayout(title_row)
        content.addWidget(self.description_label)
        content.addStretch(1)
        content.addLayout(footer)

        root.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(content, 1)

        self.apply_theme(self._theme)

    def apply_theme(self, theme: ThemeName | str) -> None:
        """Apply current theme and interaction state."""
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)

        tone_colors = {
            QuickActionTone.PRIMARY: (
                palette.brand_primary,
                palette.brand_accent_soft,
            ),
            QuickActionTone.INFO: (
                palette.info,
                palette.info_background,
            ),
            QuickActionTone.SUCCESS: (
                palette.success,
                palette.success_background,
            ),
            QuickActionTone.NEUTRAL: (
                palette.text_secondary,
                palette.neutral_background,
            ),
        }
        accent, accent_background = tone_colors[self.spec.tone]

        if self._pressed:
            background = palette.selected_background
            border = accent
        elif self._hovered:
            background = palette.hover_background
            border = accent
        else:
            background = palette.input_background
            border = palette.border_subtle

        self.setStyleSheet(
            f"""
            QFrame#QuickActionTile {{
                background-color: {background};
                border: 1px solid {border};
                border-radius: 12px;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
            QLabel#QuickActionIcon {{
                color: {accent};
                background-color: {accent_background};
                border-radius: 10px;
                {Typography.BUTTON.css()}
            }}
            QLabel#QuickActionTitle {{
                color: {palette.text_primary};
                {Typography.BUTTON.css()}
            }}
            QLabel#QuickActionDescription {{
                color: {palette.text_muted};
                {Typography.BODY_S.css()}
            }}
            QLabel#QuickActionBadge {{
                color: {accent};
                background-color: {accent_background};
                border-radius: 7px;
                padding: 2px 6px;
                {Typography.CAPTION.css()}
            }}
            QLabel#QuickActionShortcut {{
                color: {palette.text_disabled};
                background-color: {palette.elevated_background};
                border: 1px solid {palette.border_subtle};
                border-radius: 5px;
                padding: 2px 5px;
                {Typography.CAPTION.css()}
            }}
            QLabel#QuickActionArrow {{
                color: {accent};
                {Typography.BUTTON.css()}
            }}
            """
        )

    def enterEvent(self, event: QEnterEvent) -> None:
        self._hovered = True
        self.apply_theme(self._theme)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._pressed = False
        self.apply_theme(self._theme)
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self.apply_theme(self._theme)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            was_pressed = self._pressed
            self._pressed = False
            self.apply_theme(self._theme)

            if was_pressed and self.rect().contains(event.position().toPoint()):
                self.clicked.emit(self.spec.key)

            event.accept()
            return
        super().mouseReleaseEvent(event)


class QuickActions(QWidget):
    """Responsive grid of primary Dashboard actions."""

    action_requested = Signal(str)

    def __init__(
        self,
        actions: Iterable[QuickActionSpec] = DEFAULT_QUICK_ACTIONS,
        *,
        theme: ThemeName | str = ThemeName.DARK,
        columns: int = 2,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        if columns < 1:
            raise ValueError("columns must be >= 1")

        self._theme = ThemeName(theme)
        self._columns = columns
        self._actions = tuple(actions)
        self._tiles: dict[str, QuickActionTile] = {}

        self.setObjectName("QuickActions")
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(10)
        self._layout.setVerticalSpacing(10)

        self._build()

    @property
    def action_keys(self) -> tuple[str, ...]:
        """Return action keys in visual order."""
        return tuple(action.key for action in self._actions)

    @property
    def columns(self) -> int:
        return self._columns

    def set_columns(self, columns: int) -> None:
        """Change the grid column count without recreating tiles."""
        if columns < 1:
            raise ValueError("columns must be >= 1")
        if columns == self._columns:
            return

        self._columns = columns
        self._relayout()

    def set_badge(self, key: str, value: str) -> None:
        """Update a tile badge."""
        tile = self._tiles.get(key)
        if tile is None:
            raise KeyError(key)

        tile.badge_label.setText(value)
        tile.badge_label.setVisible(bool(value))

    def set_enabled(self, key: str, enabled: bool) -> None:
        """Enable or disable one action tile."""
        tile = self._tiles.get(key)
        if tile is None:
            raise KeyError(key)

        tile.setEnabled(bool(enabled))
        tile.setCursor(
            QCursor(Qt.CursorShape.PointingHandCursor)
            if enabled
            else QCursor(Qt.CursorShape.ForbiddenCursor)
        )

    def apply_theme(self, theme: ThemeName | str) -> None:
        """Apply theme to all tiles."""
        self._theme = ThemeName(theme)
        for tile in self._tiles.values():
            tile.apply_theme(self._theme)

    def trigger(self, key: str) -> None:
        """Programmatically trigger an enabled action."""
        tile = self._tiles.get(key)
        if tile is None:
            raise KeyError(key)
        if tile.isEnabled():
            self.action_requested.emit(key)

    def _build(self) -> None:
        for index, spec in enumerate(self._actions):
            if spec.key in self._tiles:
                raise ValueError(f"Duplicate quick action key: {spec.key}")

            tile = QuickActionTile(
                spec,
                theme=self._theme,
                parent=self,
            )
            tile.clicked.connect(self.action_requested)
            self._tiles[spec.key] = tile

        self._relayout()

    def _relayout(self) -> None:
        while self._layout.count():
            self._layout.takeAt(0)

        for index, tile in enumerate(self._tiles.values()):
            row, column = divmod(index, self._columns)
            self._layout.addWidget(tile, row, column)

        max_columns = max(self._columns, len(self._tiles), 1)
        for column in range(max_columns):
            self._layout.setColumnStretch(
                column,
                1 if column < self._columns else 0,
            )


__all__ = [
    "DEFAULT_QUICK_ACTIONS",
    "QuickActionSpec",
    "QuickActionTile",
    "QuickActionTone",
    "QuickActions",
]
