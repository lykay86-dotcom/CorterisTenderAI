"""Reusable structural sections for Dashboard 1.0."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme.colors import ThemeName, get_palette
from app.ui.theme.typography import Typography


class DashboardSection(QFrame):
    """A titled dashboard panel with a dedicated content area."""

    def __init__(
        self,
        title: str,
        *,
        subtitle: str = "",
        badge: str = "",
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = ThemeName(theme)

        self.setObjectName("DashboardSection")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(14)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)

        title_column = QVBoxLayout()
        title_column.setContentsMargins(0, 0, 0, 0)
        title_column.setSpacing(3)

        self.title_label = QLabel(title, self)
        self.title_label.setObjectName("DashboardSectionTitle")

        self.subtitle_label = QLabel(subtitle, self)
        self.subtitle_label.setObjectName("DashboardSectionSubtitle")
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setVisible(bool(subtitle))

        title_column.addWidget(self.title_label)
        title_column.addWidget(self.subtitle_label)

        self.badge_label = QLabel(badge, self)
        self.badge_label.setObjectName("DashboardSectionBadge")
        self.badge_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge_label.setVisible(bool(badge))

        header.addLayout(title_column, 1)
        header.addWidget(
            self.badge_label,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
        )

        self.content = QWidget(self)
        self.content.setObjectName("DashboardSectionContent")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(10)

        root.addLayout(header)
        root.addWidget(self.content, 1)

        self.apply_theme(self._theme)

    def add_widget(self, widget: QWidget, *, stretch: int = 0) -> None:
        """Add a widget to the section body."""
        self.content_layout.addWidget(widget, stretch)

    def set_badge(self, value: str) -> None:
        self.badge_label.setText(value)
        self.badge_label.setVisible(bool(value))

    def apply_theme(self, theme: ThemeName | str) -> None:
        """Apply theme colors to the section."""
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)

        self.setStyleSheet(
            f"""
            QFrame#DashboardSection {{
                background-color: {palette.card_background};
                border: 1px solid {palette.border_subtle};
                border-radius: 14px;
            }}
            QLabel#DashboardSectionTitle {{
                color: {palette.text_primary};
                background: transparent;
                border: none;
                {Typography.H3.css()}
            }}
            QLabel#DashboardSectionSubtitle {{
                color: {palette.text_muted};
                background: transparent;
                border: none;
                {Typography.BODY_S.css()}
            }}
            QLabel#DashboardSectionBadge {{
                color: {palette.brand_accent};
                background-color: {palette.brand_accent_soft};
                border: none;
                border-radius: 8px;
                padding: 4px 8px;
                {Typography.CAPTION.css()}
            }}
            QWidget#DashboardSectionContent {{
                background: transparent;
                border: none;
            }}
            """
        )


__all__ = ["DashboardSection"]
