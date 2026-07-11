"""Главная страница рабочего стола Corteris Tender AI."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme.colors import ThemeName
from app.ui.viewmodels.dashboard_viewmodel import (
    AiRecommendation,
    DashboardKpi,
    DashboardViewModel,
    RecentTender,
)
from app.ui.widgets.button import (
    OutlineButton,
    PrimaryButton,
    SecondaryButton,
)
from app.ui.widgets.card import Card, CardTone, KpiCard


class DashboardPage(QWidget):
    """Современный рабочий стол руководителя и тендерного специалиста."""

    find_tenders_requested = Signal()
    create_proposal_requested = Signal()
    create_estimate_requested = Signal()
    analyze_documents_requested = Signal()
    tender_open_requested = Signal(str)
    recommendation_action_requested = Signal(int)

    def __init__(
        self,
        viewmodel: DashboardViewModel | None = None,
        *,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._theme = ThemeName(theme)
        self.viewmodel = viewmodel or DashboardViewModel(self)
        self._kpi_cards: dict[str, KpiCard] = {}

        self.setObjectName("DashboardPage")
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._content = QWidget(self._scroll)
        self._content.setObjectName("DashboardContent")
        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(24, 20, 24, 24)
        self._layout.setSpacing(18)

        self._build_header()
        self._build_kpis()
        self._build_middle_section()
        self._build_quick_actions()

        self._scroll.setWidget(self._content)
        root.addWidget(self._scroll)

        self._connect_viewmodel()
        self.refresh_from_state()

    def _build_header(self) -> None:
        header = QHBoxLayout()
        header.setSpacing(12)

        title_column = QVBoxLayout()
        title_column.setSpacing(3)

        title = QLabel("Рабочий стол")
        title.setObjectName("DashboardTitle")

        subtitle = QLabel(
            "Главные показатели, последние тендеры и рекомендации AI."
        )
        subtitle.setObjectName("DashboardSubtitle")
        subtitle.setWordWrap(True)

        title_column.addWidget(title)
        title_column.addWidget(subtitle)

        self._updated_label = QLabel("Данные ещё не обновлялись")
        self._updated_label.setObjectName("DashboardUpdated")
        self._updated_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        refresh_button = OutlineButton(
            "Обновить",
            icon_text="↻",
            theme=self._theme,
        )
        refresh_button.clicked.connect(self.viewmodel.request_refresh)

        header.addLayout(title_column, 1)
        header.addWidget(self._updated_label)
        header.addWidget(refresh_button)

        self._layout.addLayout(header)

    def _build_kpis(self) -> None:
        self._kpi_grid = QGridLayout()
        self._kpi_grid.setContentsMargins(0, 0, 0, 0)
        self._kpi_grid.setHorizontalSpacing(14)
        self._kpi_grid.setVerticalSpacing(14)

        for index, kpi in enumerate(self.viewmodel.state.kpis.values()):
            card = self._create_kpi_card(kpi)
            self._kpi_cards[kpi.key] = card
            row, column = divmod(index, 4)
            self._kpi_grid.addWidget(card, row, column)

        for column in range(4):
            self._kpi_grid.setColumnStretch(column, 1)

        self._layout.addLayout(self._kpi_grid)

    def _create_kpi_card(self, kpi: DashboardKpi) -> KpiCard:
        card = KpiCard(
            kpi.title,
            kpi.value,
            trend=kpi.trend,
            trend_tone=self._tone(kpi.tone),
            icon_text=kpi.icon_text,
            theme=self._theme,
            clickable=True,
        )
        card.setMinimumHeight(138)
        return card

    def _build_middle_section(self) -> None:
        middle = QGridLayout()
        middle.setContentsMargins(0, 0, 0, 0)
        middle.setHorizontalSpacing(16)
        middle.setVerticalSpacing(16)

        recent_card = Card(
            "Последние тендеры",
            subtitle="Недавно добавленные и обновлённые закупки",
            icon_text="🔎",
            theme=self._theme,
        )
        self._recent_list = QListWidget()
        self._recent_list.setObjectName("RecentTenderList")
        self._recent_list.setAlternatingRowColors(True)
        self._recent_list.itemDoubleClicked.connect(
            lambda item: self.tender_open_requested.emit(
                str(item.data(Qt.ItemDataRole.UserRole))
            )
        )
        recent_card.add_widget(self._recent_list)

        ai_card = Card(
            "AI-рекомендации",
            subtitle="Действия, которые требуют внимания",
            icon_text="AI",
            tone=CardTone.INFO,
            theme=self._theme,
        )
        self._ai_list = QListWidget()
        self._ai_list.setObjectName("AiRecommendationList")
        self._ai_list.itemDoubleClicked.connect(
            lambda item: self.recommendation_action_requested.emit(
                int(item.data(Qt.ItemDataRole.UserRole))
            )
        )
        ai_card.add_widget(self._ai_list)

        middle.addWidget(recent_card, 0, 0)
        middle.addWidget(ai_card, 0, 1)
        middle.setColumnStretch(0, 3)
        middle.setColumnStretch(1, 2)

        self._layout.addLayout(middle)

    def _build_quick_actions(self) -> None:
        quick_card = Card(
            "Быстрые действия",
            subtitle="Основные операции без перехода по разделам",
            icon_text="⚡",
            theme=self._theme,
        )

        buttons = QHBoxLayout()
        buttons.setSpacing(10)

        find_button = PrimaryButton(
            "Найти тендеры",
            icon_text="🔎",
            theme=self._theme,
        )
        proposal_button = SecondaryButton(
            "Создать КП",
            icon_text="📄",
            theme=self._theme,
        )
        estimate_button = SecondaryButton(
            "Создать смету",
            icon_text="📊",
            theme=self._theme,
        )
        analyze_button = OutlineButton(
            "Проверить документацию",
            icon_text="AI",
            theme=self._theme,
        )

        find_button.clicked.connect(self.find_tenders_requested)
        proposal_button.clicked.connect(self.create_proposal_requested)
        estimate_button.clicked.connect(self.create_estimate_requested)
        analyze_button.clicked.connect(self.analyze_documents_requested)

        for button in (
            find_button,
            proposal_button,
            estimate_button,
            analyze_button,
        ):
            buttons.addWidget(button)

        buttons.addItem(
            QSpacerItem(
                20,
                20,
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Minimum,
            )
        )

        action_widget = QWidget()
        action_widget.setLayout(buttons)
        quick_card.add_widget(action_widget)
        self._layout.addWidget(quick_card)

    def _connect_viewmodel(self) -> None:
        self.viewmodel.kpi_changed.connect(self._on_kpi_changed)
        self.viewmodel.recent_tenders_changed.connect(
            self.set_recent_tenders
        )
        self.viewmodel.ai_recommendations_changed.connect(
            self.set_ai_recommendations
        )
        self.viewmodel.state_changed.connect(
            lambda _state: self._refresh_updated_label()
        )

    def refresh_from_state(self) -> None:
        """Обновляет экран из текущего состояния ViewModel."""
        for key, kpi in self.viewmodel.state.kpis.items():
            self._on_kpi_changed(key, kpi)
        self.set_recent_tenders(self.viewmodel.state.recent_tenders)
        self.set_ai_recommendations(
            self.viewmodel.state.ai_recommendations
        )
        self._refresh_updated_label()

    def set_kpi(
        self,
        key: str,
        value: str,
        *,
        trend: str | None = None,
        tone: str | None = None,
    ) -> None:
        """Удобный публичный метод обновления KPI."""
        self.viewmodel.set_kpi(
            key,
            value=value,
            trend=trend,
            tone=tone,
        )

    def set_recent_tenders(
        self,
        tenders: list[RecentTender],
    ) -> None:
        """Отображает последние тендеры."""
        self._recent_list.clear()

        if not tenders:
            item = QListWidgetItem(
                "Тендеры пока не добавлены. Используйте «Найти тендеры»."
            )
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._recent_list.addItem(item)
            return

        for tender in tenders:
            score = f" · {tender.score}/100" if tender.score is not None else ""
            deadline = f" · до {tender.deadline}" if tender.deadline else ""
            recommendation = (
                f"\n{tender.recommendation}"
                if tender.recommendation
                else ""
            )
            text = (
                f"{tender.number} — {tender.title}"
                f"\n{tender.customer}{deadline}{score}"
                f"{recommendation}"
            )
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, tender.number)
            self._recent_list.addItem(item)

    def set_ai_recommendations(
        self,
        recommendations: list[AiRecommendation],
    ) -> None:
        """Отображает список рекомендаций AI."""
        self._ai_list.clear()

        if not recommendations:
            item = QListWidgetItem(
                "Рекомендаций пока нет. Выполните анализ тендера."
            )
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._ai_list.addItem(item)
            return

        prefix_by_severity = {
            "success": "✓",
            "warning": "!",
            "danger": "×",
            "info": "i",
        }

        for index, recommendation in enumerate(recommendations):
            prefix = prefix_by_severity.get(
                recommendation.severity,
                "•",
            )
            action = (
                f"\nДействие: {recommendation.action_text}"
                if recommendation.action_text
                else ""
            )
            item = QListWidgetItem(
                f"{prefix} {recommendation.title}"
                f"\n{recommendation.description}"
                f"{action}"
            )
            item.setData(Qt.ItemDataRole.UserRole, index)
            self._ai_list.addItem(item)

    def set_theme(self, theme: ThemeName | str) -> None:
        """Применяет тему ко всем составным карточкам."""
        self._theme = ThemeName(theme)
        for card in self._kpi_cards.values():
            card.set_theme(self._theme)

    def _on_kpi_changed(
        self,
        key: str,
        kpi: DashboardKpi,
    ) -> None:
        card = self._kpi_cards.get(key)
        if card is None:
            return
        card.title = kpi.title
        card.value = kpi.value
        card.icon_text = kpi.icon_text
        card.set_trend(kpi.trend, self._tone(kpi.tone))

    def _refresh_updated_label(self) -> None:
        updated = self.viewmodel.state.last_updated
        self._updated_label.setText(
            f"Обновлено: {updated:%d.%m.%Y %H:%M:%S}"
            if updated is not None
            else "Данные ещё не обновлялись"
        )

    @staticmethod
    def _tone(value: str) -> CardTone:
        try:
            return CardTone(value)
        except ValueError:
            return CardTone.DEFAULT


__all__ = ["DashboardPage"]
