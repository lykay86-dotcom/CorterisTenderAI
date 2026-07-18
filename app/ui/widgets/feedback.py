"""Reusable semantic feedback presentation primitives."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.ui.theme.colors import SemanticColor, ThemeName, get_palette
from app.ui.theme.tokens import BorderWidth, Radius, Spacing
from app.ui.theme.typography import Typography


class StatusBadge(QLabel):
    """Compact text badge whose meaning never relies on colour alone."""

    def __init__(
        self,
        text: str,
        *,
        tone: SemanticColor | str = SemanticColor.NEUTRAL,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self._tone = SemanticColor(tone)
        self._theme = ThemeName(theme)
        self.setObjectName("CorterisStatusBadge")
        self.setAccessibleName(text)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.apply_theme(self._theme)

    def setText(self, text: str) -> None:  # noqa: N802
        super().setText(text)
        self.setAccessibleName(text)

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        foreground, background = get_palette(self._theme).semantic(self._tone)
        self.setStyleSheet(
            f"QLabel#CorterisStatusBadge {{ color: {foreground}; background-color: {background}; "
            f"border: {int(BorderWidth.DEFAULT)}px solid {foreground}; "
            f"border-radius: {int(Radius.PILL)}px; padding: {int(Spacing.XS)}px {int(Spacing.S)}px; "
            f"{Typography.CAPTION.css()} }}"
        )


class InlineMessage(QFrame):
    """Title/details feedback surface with an explicit semantic identity."""

    def __init__(
        self,
        title: str,
        *,
        details: str = "",
        tone: SemanticColor | str = SemanticColor.INFO,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._tone = SemanticColor(tone)
        self._theme = ThemeName(theme)
        self.setObjectName("CorterisInlineMessage")
        self.setAccessibleName(title)
        self.setAccessibleDescription(" ".join(part for part in (title, details) if part))

        root = QHBoxLayout(self)
        root.setContentsMargins(int(Spacing.M), int(Spacing.S), int(Spacing.M), int(Spacing.S))
        root.setSpacing(int(Spacing.S))
        self.indicator_label = QLabel(self._tone.value.upper(), self)
        self.indicator_label.setObjectName("InlineMessageIdentity")
        column = QVBoxLayout()
        column.setSpacing(int(Spacing.XS))
        self.title_label = QLabel(title, self)
        self.title_label.setObjectName("InlineMessageTitle")
        self.details_label = QLabel(details, self)
        self.details_label.setObjectName("InlineMessageDetails")
        self.details_label.setWordWrap(True)
        self.details_label.setVisible(bool(details))
        column.addWidget(self.title_label)
        column.addWidget(self.details_label)
        root.addWidget(self.indicator_label, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(column, 1)
        self.apply_theme(self._theme)

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)
        foreground, background = palette.semantic(self._tone)
        self.setStyleSheet(
            f"""
            QFrame#CorterisInlineMessage {{ background-color: {background};
                border: {int(BorderWidth.DEFAULT)}px solid {foreground};
                border-radius: {int(Radius.MEDIUM)}px; }}
            QFrame#CorterisInlineMessage QLabel {{ background: transparent; border: none; }}
            QLabel#InlineMessageIdentity {{ color: {foreground}; {Typography.CAPTION.css()} }}
            QLabel#InlineMessageTitle {{ color: {palette.text_primary}; {Typography.BUTTON.css()} }}
            QLabel#InlineMessageDetails {{ color: {palette.text_secondary}; {Typography.BODY_S.css()} }}
            """
        )


__all__ = ["InlineMessage", "StatusBadge"]
