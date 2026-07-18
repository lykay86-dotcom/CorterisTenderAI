from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QLabel, QToolButton, QSizePolicy

from app.ui.theme.colors import ThemeName
from app.ui.theme.icons import IconId, get_icon_provider
from app.ui.theme.tokens import DESIGN_TOKENS


class TopBar(QWidget):
    """Top navigation bar for Corteris Tender AI."""

    search_requested = Signal(str)
    notifications_clicked = Signal()
    ai_clicked = Signal()
    theme_toggled = Signal()
    profile_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TopBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        self.page_title = QLabel("Dashboard")

        self.search = QLineEdit()
        self.search.setObjectName("TopBarTenderSearch")
        self.search.setPlaceholderText("Поиск тендеров…")
        self.search.setToolTip("Запустить поиск тендеров по выбранному профилю и источникам")
        self.search.returnPressed.connect(lambda: self.search_requested.emit(self.search.text()))
        self.search.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.ai_button = self._btn(IconId.TOPBAR_AI, "AI")
        self.ai_button.setObjectName("TopBarAiButton")
        self.ai_button.clicked.connect(self.ai_clicked)

        self.notify_button = self._btn(IconId.TOPBAR_NOTIFICATIONS, "Уведомления")
        self.notify_button.setObjectName("TopBarNotificationsButton")
        self.notify_button.clicked.connect(self.notifications_clicked)

        self.theme_button = self._btn(IconId.TOPBAR_THEME, "Тема")
        self.theme_button.setObjectName("TopBarThemeButton")
        self.theme_button.clicked.connect(self.theme_toggled)

        self.profile_button = self._btn(IconId.TOPBAR_PROFILE, "Профиль")
        self.profile_button.setObjectName("TopBarProfileButton")
        self.profile_button.clicked.connect(self.profile_clicked)

        layout.addWidget(self.page_title)
        layout.addSpacing(12)
        layout.addWidget(self.search, 1)
        layout.addWidget(self.ai_button)
        layout.addWidget(self.notify_button)
        layout.addWidget(self.theme_button)
        layout.addWidget(self.profile_button)

    def _btn(self, icon_id: IconId, tip: str) -> QToolButton:
        b = QToolButton()
        b.setIcon(get_icon_provider().icon(icon_id))
        side = DESIGN_TOKENS.controls["small"].height
        b.setFixedSize(side, side)
        b.setToolTip(tip)
        b.setAccessibleName(tip)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setAutoRaise(True)
        return b

    def apply_theme(self, theme: ThemeName | str) -> None:
        normalized = ThemeName(theme)
        provider = get_icon_provider()
        for button, icon_id in (
            (self.ai_button, IconId.TOPBAR_AI),
            (self.notify_button, IconId.TOPBAR_NOTIFICATIONS),
            (self.theme_button, IconId.TOPBAR_THEME),
            (self.profile_button, IconId.TOPBAR_PROFILE),
        ):
            button.setIcon(provider.icon(icon_id, theme=normalized))

    def set_page_title(self, title: str) -> None:
        self.page_title.setText(title)


__all__ = ["TopBar"]
