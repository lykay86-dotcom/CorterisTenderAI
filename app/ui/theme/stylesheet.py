"""Qt Style Sheet builder for Corteris Tender AI."""

from __future__ import annotations

from app.ui.theme.colors import ThemePalette, get_palette
from app.ui.theme.tokens import BorderWidth, DESIGN_TOKENS, Radius, Spacing
from app.ui.theme.typography import Typography


def build_stylesheet(theme: str = "dark") -> str:
    """Return the global Qt Style Sheet for the selected theme."""
    p: ThemePalette = get_palette(theme)

    control = DESIGN_TOKENS.controls["medium"]
    return f"""
QWidget {{
    background-color: {p.app_background};
    color: {p.text_primary};
    {Typography.BODY_M.css()}
}}

QMainWindow {{
    background-color: {p.app_background};
}}

QFrame {{
    background-color: {p.panel_background};
    border: {int(BorderWidth.DEFAULT)}px solid {p.border_default};
    border-radius: {int(Radius.LARGE)}px;
}}

QPushButton {{
    background-color: {p.brand_primary};
    color: {p.text_on_brand};
    border: none;
    border-radius: {control.radius}px;
    padding: {control.vertical_padding}px {control.horizontal_padding}px;
    min-height: {control.height}px;
    {Typography.BUTTON.css()}
}}

QPushButton:hover {{
    background-color: {p.brand_primary_hover};
}}

QPushButton:pressed {{
    background-color: {p.brand_primary_pressed};
}}

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {{
    background-color: {p.input_background};
    color: {p.text_primary};
    border: {int(BorderWidth.DEFAULT)}px solid {p.border_default};
    border-radius: {int(Radius.MEDIUM)}px;
    padding: {int(Spacing.S)}px;
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus, QTimeEdit:focus {{
    border: {int(BorderWidth.FOCUS)}px solid {p.focus_ring};
}}

QPushButton:focus, QToolButton:focus, QCheckBox:focus, QRadioButton:focus,
QListView:focus, QTreeView:focus, QTableView:focus, QScrollArea:focus {{
    outline: none;
    border: {int(BorderWidth.FOCUS)}px solid {p.focus_ring};
}}

QTabBar::tab:focus {{
    border: {int(BorderWidth.FOCUS)}px solid {p.focus_ring};
}}

QPushButton:disabled, QToolButton:disabled, QLineEdit:disabled,
QTextEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled {{
    color: {p.text_disabled};
    background-color: {p.neutral_background};
    border-color: {p.border_subtle};
}}

QTableView {{
    background-color: {p.card_background};
    alternate-background-color: {p.hover_background};
    gridline-color: {p.divider};
    selection-background-color: {p.selected_background};
}}

QHeaderView::section {{
    background-color: {p.sidebar_background};
    color: {p.text_secondary};
    border: none;
    border-bottom: 1px solid {p.divider};
    padding: {int(Spacing.S)}px;
}}

QScrollBar:vertical {{
    background: transparent;
    width: {int(Spacing.M)}px;
}}

QScrollBar::handle:vertical {{
    background: {p.scrollbar};
    border-radius: {int(Radius.MEDIUM)}px;
}}

QScrollBar::handle:vertical:hover {{
    background: {p.scrollbar_hover};
}}

QStatusBar {{
    background-color: {p.topbar_background};
    color: {p.text_secondary};
}}

QLabel[semanticTone="success"] {{ color: {p.success}; {Typography.H3.css()} }}
QLabel[semanticTone="danger"] {{ color: {p.danger}; {Typography.H3.css()} }}
QLabel[semanticTone="warning"] {{ color: {p.warning}; {Typography.H3.css()} }}
QLabel[semanticTone="info"] {{ color: {p.info}; {Typography.H3.css()} }}
QLabel[semanticTone="neutral"] {{ color: {p.text_secondary}; {Typography.BODY_M.css()} }}
QLabel#DashboardPlaceholderTitle {{ color: {p.text_primary}; {Typography.H1.css()} }}
""".strip()


__all__ = ["build_stylesheet"]
