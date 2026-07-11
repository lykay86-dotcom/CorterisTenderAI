from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,QHBoxLayout,QLineEdit,QLabel,QToolButton,QSizePolicy
)

class TopBar(QWidget):
    """Top navigation bar for Corteris Tender AI."""

    search_requested=Signal(str)
    notifications_clicked=Signal()
    ai_clicked=Signal()
    theme_toggled=Signal()
    profile_clicked=Signal()

    def __init__(self,parent=None):
        super().__init__(parent)
        self.setObjectName("TopBar")

        layout=QHBoxLayout(self)
        layout.setContentsMargins(16,12,16,12)
        layout.setSpacing(10)

        self.page_title=QLabel("Dashboard")

        self.search=QLineEdit()
        self.search.setPlaceholderText("Поиск тендеров, клиентов, документов…")
        self.search.returnPressed.connect(
            lambda: self.search_requested.emit(self.search.text())
        )
        self.search.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )

        self.ai_button=self._btn("🤖","AI")
        self.ai_button.clicked.connect(self.ai_clicked)

        self.notify_button=self._btn("🔔","Уведомления")
        self.notify_button.clicked.connect(self.notifications_clicked)

        self.theme_button=self._btn("🌙","Тема")
        self.theme_button.clicked.connect(self.theme_toggled)

        self.profile_button=self._btn("👤","Профиль")
        self.profile_button.clicked.connect(self.profile_clicked)

        layout.addWidget(self.page_title)
        layout.addSpacing(12)
        layout.addWidget(self.search,1)
        layout.addWidget(self.ai_button)
        layout.addWidget(self.notify_button)
        layout.addWidget(self.theme_button)
        layout.addWidget(self.profile_button)

    def _btn(self,text:str,tip:str)->QToolButton:
        b=QToolButton()
        b.setText(text)
        b.setToolTip(tip)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setAutoRaise(True)
        return b

    def set_page_title(self,title:str)->None:
        self.page_title.setText(title)

__all__=["TopBar"]
