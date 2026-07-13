from __future__ import annotations

from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget, QLabel

from app.ui.widgets.sidebar import create_default_sidebar
from app.ui.widgets.topbar import TopBar


class DashboardLayout(QWidget):
    """Main workspace layout combining Sidebar, TopBar and content area."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.sidebar = create_default_sidebar()
        self.topbar = TopBar()
        self.pages = QStackedWidget()

        shell = QHBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        shell.addWidget(self.sidebar)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)

        right.addWidget(self.topbar)
        right.addWidget(self.pages, 1)

        shell.addLayout(right, 1)

        self._page_index = {}

        self.sidebar.item_selected.connect(self._activate)

    def add_page(self, key: str, title: str, widget: QWidget) -> None:
        index = self.pages.addWidget(widget)
        self._page_index[key] = (index, title)

    def add_placeholder_page(self, key: str, title: str) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        label = QLabel(title)
        label.setStyleSheet("font-size:24px;font-weight:600;")
        layout.addStretch()
        layout.addWidget(label)
        layout.addStretch()
        self.add_page(key, title, page)

    def initialize_defaults(self) -> None:
        self.add_placeholder_page("dashboard", "🏠 Dashboard")
        self.add_placeholder_page("tenders", "🔎 Тендеры")
        self.add_placeholder_page("ai", "🤖 AI Анализ")
        self.add_placeholder_page("quotes", "📄 Коммерческие предложения")
        self.add_placeholder_page("estimates", "📊 Сметы")
        self.add_placeholder_page("documents", "📂 Документы")
        self.add_placeholder_page("clients", "👥 Клиенты")
        self.add_placeholder_page("analytics", "📈 Аналитика")
        self.add_placeholder_page("settings", "⚙ Настройки")
        self._activate("dashboard")

    def _activate(self, key: str) -> None:
        if key not in self._page_index:
            return
        index, title = self._page_index[key]
        self.pages.setCurrentIndex(index)
        self.topbar.set_page_title(title)


__all__ = ["DashboardLayout"]
