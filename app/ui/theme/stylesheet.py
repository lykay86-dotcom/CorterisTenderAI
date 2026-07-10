"""Qt Style Sheet builder for Corteris Tender AI."""

from __future__ import annotations

from app.ui.theme.colors import ThemePalette, get_palette


def build_stylesheet(theme: str = "dark") -> str:
    """Return the global Qt Style Sheet for the selected theme."""
    p: ThemePalette = get_palette(theme)

    return f"""
QWidget {{
    background-color: {p.app_background};
    color: {p.text_primary};
}}

QMainWindow {{
    background-color: {p.app_background};
}}

QFrame {{
    background-color: {p.panel_background};
    border: 1px solid {p.border_default};
    border-radius: 8px;
}}

QPushButton {{
    background-color: {p.brand_primary};
    color: {p.text_on_brand};
    border: none;
    border-radius: 6px;
    padding: 6px 12px;
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
    border: 1px solid {p.border_default};
    border-radius: 6px;
    padding: 4px;
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 2px solid {p.focus_ring};
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
    padding: 6px;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
}}

QScrollBar::handle:vertical {{
    background: {p.scrollbar};
    border-radius: 5px;
}}

QScrollBar::handle:vertical:hover {{
    background: {p.scrollbar_hover};
}}

QStatusBar {{
    background-color: {p.topbar_background};
    color: {p.text_secondary};
}}
""".strip()


__all__ = ["build_stylesheet"]
