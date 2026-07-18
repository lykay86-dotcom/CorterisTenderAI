"""Reusable card widgets for the Corteris Tender AI interface."""

from __future__ import annotations

from enum import StrEnum

from PySide6.QtCore import Property, Qt, Signal
from PySide6.QtGui import QCursor, QEnterEvent, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme.colors import SemanticColor, ThemeName, ThemePalette, get_palette
from app.ui.theme.typography import Typography
from app.ui.theme.tokens import BorderWidth, DESIGN_TOKENS, Radius, Spacing


class CardTone(StrEnum):
    """Semantic visual tone of a card."""

    DEFAULT = "default"
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    DANGER = "danger"
    NEUTRAL = "neutral"


class Card(QFrame):
    """Modern themed content card.

    The widget can be used as a generic container or as a compact KPI card.
    Content widgets may be added through :meth:`add_widget`.

    Signals:
        clicked: Emitted when a clickable card is pressed.
    """

    clicked = Signal()

    def __init__(
        self,
        title: str = "",
        *,
        subtitle: str = "",
        value: str = "",
        icon_text: str = "",
        tone: CardTone | str = CardTone.DEFAULT,
        theme: ThemeName | str = ThemeName.DARK,
        clickable: bool = False,
        shadow: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._theme = ThemeName(theme)
        self._tone = CardTone(tone)
        self._clickable = clickable
        self._shadow_enabled = shadow
        self._hovered = False
        self._pressed = False
        self._shadow_effect: QGraphicsDropShadowEffect | None = None

        self.setObjectName("CorterisCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus if clickable else Qt.FocusPolicy.NoFocus)
        self.setCursor(
            QCursor(Qt.CursorShape.PointingHandCursor)
            if clickable
            else QCursor(Qt.CursorShape.ArrowCursor)
        )

        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(
            int(Spacing.L), int(Spacing.L), int(Spacing.L), int(Spacing.L)
        )
        self._root_layout.setSpacing(int(Spacing.M))

        self._header_layout = QHBoxLayout()
        self._header_layout.setContentsMargins(0, 0, 0, 0)
        self._header_layout.setSpacing(10)

        self._icon_label = QLabel(icon_text)
        self._icon_label.setObjectName("CardIcon")
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setFixedSize(34, 34)
        self._icon_label.setVisible(bool(icon_text))

        self._title_column = QVBoxLayout()
        self._title_column.setContentsMargins(0, 0, 0, 0)
        self._title_column.setSpacing(2)

        self._title_label = QLabel(title)
        self._title_label.setObjectName("CardTitle")
        self._title_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._title_label.setWordWrap(True)

        self._subtitle_label = QLabel(subtitle)
        self._subtitle_label.setObjectName("CardSubtitle")
        self._subtitle_label.setWordWrap(True)
        self._subtitle_label.setVisible(bool(subtitle))

        self._title_column.addWidget(self._title_label)
        self._title_column.addWidget(self._subtitle_label)

        self._header_layout.addWidget(self._icon_label, 0, Qt.AlignmentFlag.AlignTop)
        self._header_layout.addLayout(self._title_column, 1)
        self._root_layout.addLayout(self._header_layout)

        self._value_label = QLabel(value)
        self._value_label.setObjectName("CardValue")
        self._value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._value_label.setWordWrap(True)
        self._value_label.setVisible(bool(value))
        self._root_layout.addWidget(self._value_label)

        self._content = QWidget(self)
        self._content.setObjectName("CardContent")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(8)
        self._content.setVisible(False)
        self._root_layout.addWidget(self._content)

        self._footer = QWidget(self)
        self._footer.setObjectName("CardFooter")
        self._footer_layout = QHBoxLayout(self._footer)
        self._footer_layout.setContentsMargins(0, 0, 0, 0)
        self._footer_layout.setSpacing(8)
        self._footer.setVisible(False)
        self._root_layout.addWidget(self._footer)

        self._apply_shadow()
        self._apply_theme()

        accessible_name = title or "Карточка"
        self.setAccessibleName(accessible_name)
        self.setAccessibleDescription(subtitle)

    @property
    def title(self) -> str:
        return self._title_label.text()

    @title.setter
    def title(self, value: str) -> None:
        self._title_label.setText(value)
        self.setAccessibleName(value or "Карточка")

    @property
    def subtitle(self) -> str:
        return self._subtitle_label.text()

    @subtitle.setter
    def subtitle(self, value: str) -> None:
        self._subtitle_label.setText(value)
        self._subtitle_label.setVisible(bool(value))
        self.setAccessibleDescription(value)

    @property
    def value(self) -> str:
        return self._value_label.text()

    @value.setter
    def value(self, text: str) -> None:
        self._value_label.setText(text)
        self._value_label.setVisible(bool(text))

    @property
    def icon_text(self) -> str:
        return self._icon_label.text()

    @icon_text.setter
    def icon_text(self, text: str) -> None:
        self._icon_label.setText(text)
        self._icon_label.setVisible(bool(text))

    def get_theme(self) -> str:
        return self._theme.value

    def set_theme(self, theme: ThemeName | str) -> None:
        normalized = ThemeName(theme)
        if normalized == self._theme:
            return
        self._theme = normalized
        self._apply_theme()

    theme = Property(str, get_theme, set_theme)

    def get_tone(self) -> str:
        return self._tone.value

    def set_tone(self, tone: CardTone | str) -> None:
        normalized = CardTone(tone)
        if normalized == self._tone:
            return
        self._tone = normalized
        self._apply_theme()

    tone = Property(str, get_tone, set_tone)

    def is_clickable(self) -> bool:
        return self._clickable

    def set_clickable(self, enabled: bool) -> None:
        self._clickable = bool(enabled)
        self.setCursor(
            QCursor(Qt.CursorShape.PointingHandCursor)
            if self._clickable
            else QCursor(Qt.CursorShape.ArrowCursor)
        )
        self.setFocusPolicy(
            Qt.FocusPolicy.StrongFocus if self._clickable else Qt.FocusPolicy.NoFocus
        )
        self._apply_theme()

    clickable = Property(bool, is_clickable, set_clickable)

    def add_widget(
        self,
        widget: QWidget,
        *,
        stretch: int = 0,
        alignment: Qt.AlignmentFlag = Qt.AlignmentFlag(0),
    ) -> None:
        """Add a widget to the main content section."""
        self._content.setVisible(True)
        self._content_layout.addWidget(widget, stretch, alignment)

    def add_footer_widget(
        self,
        widget: QWidget,
        *,
        stretch: int = 0,
        alignment: Qt.AlignmentFlag = Qt.AlignmentFlag(0),
    ) -> None:
        """Add a widget to the footer section."""
        self._footer.setVisible(True)
        self._footer_layout.addWidget(widget, stretch, alignment)

    def clear_content(self) -> None:
        """Remove all widgets from the content section."""
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        self._content.setVisible(False)

    def set_compact(self, compact: bool) -> None:
        """Switch between normal and compact card spacing."""
        margins = (
            (int(Spacing.M), int(Spacing.S), int(Spacing.M), int(Spacing.S))
            if compact
            else (int(Spacing.L), int(Spacing.L), int(Spacing.L), int(Spacing.L))
        )
        self._root_layout.setContentsMargins(*margins)
        self._root_layout.setSpacing(7 if compact else 10)

    def _tone_colors(self, palette: ThemePalette) -> tuple[str, str]:
        if self._tone == CardTone.INFO:
            return palette.semantic(SemanticColor.INFO)
        if self._tone == CardTone.SUCCESS:
            return palette.semantic(SemanticColor.SUCCESS)
        if self._tone == CardTone.WARNING:
            return palette.semantic(SemanticColor.WARNING)
        if self._tone == CardTone.DANGER:
            return palette.semantic(SemanticColor.DANGER)
        if self._tone == CardTone.NEUTRAL:
            return palette.semantic(SemanticColor.NEUTRAL)
        return palette.brand_accent, palette.card_background

    def _apply_shadow(self) -> None:
        if not self._shadow_enabled:
            self.setGraphicsEffect(None)
            return

        palette = get_palette(self._theme)
        if self._shadow_effect is None:
            self._shadow_effect = QGraphicsDropShadowEffect(self)
            self.setGraphicsEffect(self._shadow_effect)
        self._shadow_effect.setBlurRadius(DESIGN_TOKENS.elevation.card_blur)
        self._shadow_effect.setOffset(0, DESIGN_TOKENS.elevation.card_offset_y)
        self._shadow_effect.setColor(palette.shadow)

    def _apply_theme(self) -> None:
        palette = get_palette(self._theme)
        accent, tone_background = self._tone_colors(palette)

        if self._pressed and self._clickable:
            background = palette.selected_background
            border = palette.brand_primary_pressed
        elif self._hovered and self._clickable:
            background = palette.hover_background
            border = palette.brand_primary_hover
        elif self._tone == CardTone.DEFAULT:
            background = palette.card_background
            border = palette.border_default
        else:
            background = tone_background
            border = accent

        self.setStyleSheet(
            f"""
            QFrame#CorterisCard {{
                background-color: {background};
                border: {int(BorderWidth.DEFAULT)}px solid {border};
                border-radius: {int(Radius.LARGE)}px;
            }}
            QFrame#CorterisCard QLabel {{
                background: transparent;
                border: none;
            }}
            QLabel#CardIcon {{
                background-color: {palette.brand_accent_soft};
                color: {accent};
                border-radius: 9px;
                font-family: '{Typography.FAMILY}';
                font-size: 14pt;
                font-weight: 600;
            }}
            QLabel#CardTitle {{
                color: {palette.text_secondary};
                {Typography.BODY_M.css()}
            }}
            QLabel#CardSubtitle {{
                color: {palette.text_muted};
                {Typography.CAPTION.css()}
            }}
            QLabel#CardValue {{
                color: {palette.text_primary};
                {Typography.H2.css()}
            }}
            QWidget#CardContent, QWidget#CardFooter {{
                background: transparent;
                border: none;
            }}
            QFrame#CorterisCard:focus {{
                border: {int(BorderWidth.FOCUS)}px solid {palette.focus_ring};
            }}
            """
        )
        self._apply_shadow()
        self.update()

    def enterEvent(self, event: QEnterEvent) -> None:
        self._hovered = True
        if self._clickable:
            self._apply_theme()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._pressed = False
        if self._clickable:
            self._apply_theme()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._clickable and event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self._apply_theme()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._clickable and event.button() == Qt.MouseButton.LeftButton:
            was_pressed = self._pressed
            self._pressed = False
            self._apply_theme()
            if was_pressed and self.rect().contains(event.position().toPoint()):
                self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._clickable and event.key() in {
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Space,
        }:
            self.clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class KpiCard(Card):
    """Specialized card for a KPI value with an optional trend label."""

    def __init__(
        self,
        title: str,
        value: str,
        *,
        subtitle: str = "",
        trend: str = "",
        trend_tone: CardTone | str = CardTone.DEFAULT,
        icon_text: str = "",
        theme: ThemeName | str = ThemeName.DARK,
        clickable: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            title,
            subtitle=subtitle,
            value=value,
            icon_text=icon_text,
            theme=theme,
            clickable=clickable,
            parent=parent,
        )

        self._trend_tone = CardTone(trend_tone)
        self._trend_label = QLabel(trend)
        self._trend_label.setObjectName("KpiTrend")
        self._trend_label.setVisible(bool(trend))
        self.add_footer_widget(self._trend_label)
        self._apply_trend_theme()

    def set_trend(
        self,
        text: str,
        tone: CardTone | str | None = None,
    ) -> None:
        """Update the trend text and its semantic tone."""
        self._trend_label.setText(text)
        self._trend_label.setVisible(bool(text))
        if tone is not None:
            self._trend_tone = CardTone(tone)
        self._apply_trend_theme()

    def set_theme(self, theme: ThemeName | str) -> None:
        super().set_theme(theme)
        if hasattr(self, "_trend_label"):
            self._apply_trend_theme()

    def _apply_trend_theme(self) -> None:
        palette = get_palette(self._theme)
        if self._trend_tone == CardTone.SUCCESS:
            foreground, background = palette.semantic(SemanticColor.SUCCESS)
        elif self._trend_tone == CardTone.WARNING:
            foreground, background = palette.semantic(SemanticColor.WARNING)
        elif self._trend_tone == CardTone.DANGER:
            foreground, background = palette.semantic(SemanticColor.DANGER)
        elif self._trend_tone == CardTone.INFO:
            foreground, background = palette.semantic(SemanticColor.INFO)
        else:
            foreground, background = palette.semantic(SemanticColor.NEUTRAL)

        self._trend_label.setStyleSheet(
            f"""
            QLabel#KpiTrend {{
                color: {foreground};
                background-color: {background};
                border: none;
                border-radius: {int(Radius.PILL)}px;
                padding: {int(Spacing.XS)}px {int(Spacing.S)}px;
                {Typography.CAPTION.css()}
            }}
            """
        )


__all__ = ["Card", "CardTone", "KpiCard"]
