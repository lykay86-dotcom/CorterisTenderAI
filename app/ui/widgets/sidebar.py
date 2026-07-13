from __future__ import annotations

from dataclasses import dataclass
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout


@dataclass(slots=True, frozen=True)
class SidebarItem:
    key: str
    title: str
    icon: str


class Sidebar(QWidget):
    """Navigation sidebar for Corteris Tender AI."""

    item_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buttons = {}
        self._current = ""
        self.setMinimumWidth(250)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("CORTERIS\nTender AI")
        title.setObjectName("SidebarTitle")
        layout.addWidget(title)

        self._container = QVBoxLayout()
        layout.addLayout(self._container)
        layout.addStretch()

        footer = QHBoxLayout()
        footer.addWidget(QLabel("v1.3"))
        layout.addLayout(footer)

    def add_item(self, item: SidebarItem):
        btn = QPushButton(f"{item.icon}  {item.title}")
        btn.setCheckable(True)
        btn.clicked.connect(lambda _, k=item.key: self.select(k))
        self._buttons[item.key] = btn
        self._container.addWidget(btn)

    def select(self, key: str):
        if key not in self._buttons:
            return
        for k, b in self._buttons.items():
            b.setChecked(k == key)
        self._current = key
        self.item_selected.emit(key)

    @property
    def current_item(self) -> str:
        return self._current


def create_default_sidebar() -> Sidebar:
    sb = Sidebar()
    for key, title, icon in [
        ("dashboard", "Dashboard", "🏠"),
        ("tenders", "Тендеры", "🔎"),
        ("ai", "AI Анализ", "🤖"),
        ("quotes", "КП", "📄"),
        ("estimates", "Сметы", "📊"),
        ("documents", "Документы", "📂"),
        ("clients", "Клиенты", "👥"),
        ("analytics", "Аналитика", "📈"),
        ("settings", "Настройки", "⚙"),
    ]:
        sb.add_item(SidebarItem(key, title, icon))
    sb.select("dashboard")
    return sb


__all__ = ["Sidebar", "SidebarItem", "create_default_sidebar"]
