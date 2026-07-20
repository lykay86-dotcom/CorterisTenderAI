from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.ui.navigation import DEFAULT_ROUTE_REGISTRY, RouteRegistry, RouteSpec
from app.ui.theme.icons import get_icon_provider
from app.ui.theme.tokens import DESIGN_TOKENS


@dataclass(slots=True, frozen=True)
class SidebarItem:
    key: str
    title: str
    icon: str


class Sidebar(QWidget):
    """Navigation sidebar for Corteris Tender AI."""

    item_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._buttons: dict[str, QPushButton] = {}
        self._current = ""
        self.setMinimumWidth(DESIGN_TOKENS.layout.sidebar_width)

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

    def add_item(self, item: SidebarItem) -> None:
        btn = QPushButton(item.title)
        btn.setObjectName(f"SidebarRoute_{item.key}")
        btn.setIcon(get_icon_provider().icon(item.icon))
        btn.setAccessibleName(item.title)
        btn.setToolTip(item.title)
        btn.setCheckable(True)
        btn.clicked.connect(lambda _, k=item.key: self.select(k))
        self._buttons[item.key] = btn
        self._container.addWidget(btn)

    def set_current(self, key: str) -> None:
        """Update the visible primary item without emitting a new intent."""
        for k, b in self._buttons.items():
            b.setChecked(k == key)
        if key in self._buttons:
            self._current = key

    def select(self, key: str) -> None:
        """Emit a legacy/canonical intent, including hidden compatibility aliases."""
        self.set_current(key)
        self.item_selected.emit(key)

    def keyboard_focus_chain(self) -> tuple[QPushButton, ...]:
        """Return primary routes in their visible navigation order."""

        return tuple(self._buttons.values())

    @property
    def current_item(self) -> str:
        return self._current


def _primary_sidebar_key(spec: RouteSpec) -> str:
    if spec.aliases:
        return spec.aliases[0]
    return spec.route_id.value.rsplit(".", 1)[-1]


def create_default_sidebar(
    registry: RouteRegistry = DEFAULT_ROUTE_REGISTRY,
) -> Sidebar:
    sb = Sidebar()
    for spec in registry.primary_routes:
        sb.add_item(
            SidebarItem(
                key=_primary_sidebar_key(spec),
                title=spec.title,
                icon=spec.icon,
            )
        )
    if registry.primary_routes:
        sb.set_current(_primary_sidebar_key(registry.primary_routes[0]))
    return sb


__all__ = ["Sidebar", "SidebarItem", "create_default_sidebar"]
