"""Dashboard 1.0 with KPI Center for Corteris Tender AI."""

from __future__ import annotations

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
    QVBoxLayout,
    QWidget,
)

from app.ui.dashboard.kpi_center import KpiCenter
from app.ui.dashboard.section import DashboardSection
from app.ui.theme.colors import ThemeName, get_palette
from app.ui.theme.typography import Typography
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
from app.ui.widgets.card import CardTone


class DashboardPage(QWidget):
    """Responsive Dashboard 1.0 shell with a six-card KPI Center."""

    find_tenders_requested = Signal()
    create_proposal_requested = Signal()
    create_estimate_requested = Signal()
    analyze_documents_requested = Signal()
    tender_open_requested = Signal(str)
    recommendation_action_requested = Signal(int)
    kpi_action_requested = Signal(str)

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
        self._themed_sections: list[DashboardSection] = []

        self.setObjectName("DashboardPage")
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea(self)
        self.scroll.setObjectName("DashboardScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.canvas = QWidget(self.scroll)
        self.canvas.setObjectName("DashboardCanvas")
        self.canvas.setMinimumWidth(900)

        self.main_layout = QVBoxLayout(self.canvas)
        self.main_layout.setContentsMargins(24, 22, 24, 28)
        self.main_layout.setSpacing(16)

        self._build_header()
        self._build_kpi_zone()
        self._build_primary_zone()
        self._build_secondary_zone()

        self.scroll.setWidget(self.canvas)
        root.addWidget(self.scroll)

        self._connect_viewmodel()
        self._apply_page_theme()
        self.refresh_from_state()

    def _build_header(self) -> None:
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 2)
        header.setSpacing(14)

        title_column = QVBoxLayout()
        title_column.setSpacing(4)

        self.title_label = QLabel("Рабочий стол")
        self.title_label.setObjectName("DashboardTitle")

        self.subtitle_label = QLabel(
            "Ключевые показатели, тендеры и действия на сегодня."
        )
        self.subtitle_label.setObjectName("DashboardSubtitle")

        title_column.addWidget(self.title_label)
        title_column.addWidget(self.subtitle_label)

        self.updated_label = QLabel("Данные ещё не обновлялись")
        self.updated_label.setObjectName("DashboardUpdated")
        self.updated_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        refresh = OutlineButton(
            "Обновить",
            icon_text="↻",
            theme=self._theme,
        )
        refresh.clicked.connect(self.viewmodel.request_refresh)

        header.addLayout(title_column, 1)
        header.addWidget(self.updated_label)
        header.addWidget(refresh)
        self.main_layout.addLayout(header)

    def _build_kpi_zone(self) -> None:
        self.kpi_center = KpiCenter(
            self.viewmodel.ordered_kpis(),
            theme=self._theme,
            columns=3,
            parent=self.canvas,
        )
        self.kpi_center.kpi_clicked.connect(self.kpi_action_requested)
        self.main_layout.addWidget(self.kpi_center)

    def _build_primary_zone(self) -> None:
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)

        self.tender_section = self._section(
            "Последние тендеры",
            subtitle="Новые и недавно обновлённые закупки",
            badge="Тендеры",
        )
        self.recent_list = QListWidget()
        self.recent_list.setObjectName("RecentTenderList")
        self.recent_list.setAlternatingRowColors(True)
        self.recent_list.setMinimumHeight(260)
        self.recent_list.itemDoubleClicked.connect(
            lambda item: self.tender_open_requested.emit(
                str(item.data(Qt.ItemDataRole.UserRole))
            )
        )
        self.tender_section.add_widget(self.recent_list)

        self.ai_section = self._section(
            "AI Advisor",
            subtitle="Риски и следующие рекомендуемые действия",
            badge="AI",
        )
        self.ai_list = QListWidget()
        self.ai_list.setObjectName("AiRecommendationList")
        self.ai_list.setMinimumHeight(260)
        self.ai_list.itemDoubleClicked.connect(
            lambda item: self.recommendation_action_requested.emit(
                int(item.data(Qt.ItemDataRole.UserRole))
            )
        )
        self.ai_section.add_widget(self.ai_list)

        grid.addWidget(self.tender_section, 0, 0)
        grid.addWidget(self.ai_section, 0, 1)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)

        self.main_layout.addLayout(grid)

    def _build_secondary_zone(self) -> None:
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)

        quick = self._section(
            "Быстрые действия",
            subtitle="Частые операции без перехода по меню",
        )
        quick_row = QHBoxLayout()
        quick_row.setSpacing(10)

        find_button = PrimaryButton(
            "Найти тендеры",
            theme=self._theme,
        )
        proposal_button = SecondaryButton(
            "Создать КП",
            theme=self._theme,
        )
        estimate_button = SecondaryButton(
            "Создать смету",
            theme=self._theme,
        )
        analyze_button = OutlineButton(
            "Анализ документов",
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
            quick_row.addWidget(button)
        quick_row.addStretch(1)

        quick_container = QWidget()
        quick_container.setLayout(quick_row)
        quick.add_widget(quick_container)

        activity = self._section(
            "Лента событий",
            subtitle="Последние действия и изменения системы",
            badge="Сегодня",
        )
        self.activity_empty = QLabel(
            "События появятся после работы с тендерами и документами."
        )
        self.activity_empty.setObjectName("DashboardEmptyText")
        self.activity_empty.setWordWrap(True)
        activity.add_widget(self.activity_empty)

        grid.addWidget(quick, 0, 0)
        grid.addWidget(activity, 0, 1)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)

        self.main_layout.addLayout(grid)
        self.main_layout.addStretch(1)

    def _section(
        self,
        title: str,
        *,
        subtitle: str = "",
        badge: str = "",
    ) -> DashboardSection:
        section = DashboardSection(
            title,
            subtitle=subtitle,
            badge=badge,
            theme=self._theme,
        )
        self._themed_sections.append(section)
        return section

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
        for key, kpi in self.viewmodel.state.kpis.items():
            self._on_kpi_changed(key, kpi)
        self.set_recent_tenders(self.viewmodel.state.recent_tenders)
        self.set_ai_recommendations(
            self.viewmodel.state.ai_recommendations
        )
        self._refresh_updated_label()

    def set_recent_tenders(self, tenders: list[RecentTender]) -> None:
        self.recent_list.clear()
        self.tender_section.set_badge(
            str(len(tenders)) if tenders else "Тендеры"
        )

        if not tenders:
            item = QListWidgetItem(
                "Тендеры пока не добавлены. Нажмите «Найти тендеры»."
            )
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.recent_list.addItem(item)
            return

        for tender in tenders:
            score = f" · {tender.score}/100" if tender.score is not None else ""
            deadline = f" · до {tender.deadline}" if tender.deadline else ""
            item = QListWidgetItem(
                f"{tender.number} — {tender.title}\n"
                f"{tender.customer}{deadline}{score}"
            )
            item.setData(Qt.ItemDataRole.UserRole, tender.number)
            self.recent_list.addItem(item)

    def set_ai_recommendations(
        self,
        recommendations: list[AiRecommendation],
    ) -> None:
        self.ai_list.clear()
        self.ai_section.set_badge(
            str(len(recommendations)) if recommendations else "AI"
        )

        if not recommendations:
            item = QListWidgetItem(
                "Рекомендаций пока нет. Выполните анализ тендера."
            )
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.ai_list.addItem(item)
            return

        symbols = {
            "success": "✓",
            "warning": "!",
            "danger": "×",
            "info": "i",
        }
        for index, recommendation in enumerate(recommendations):
            symbol = symbols.get(recommendation.severity, "•")
            item = QListWidgetItem(
                f"{symbol} {recommendation.title}\n"
                f"{recommendation.description}"
            )
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.ai_list.addItem(item)

    def set_kpi(
        self,
        key: str,
        value: str,
        *,
        trend: str | None = None,
        tone: str | None = None,
    ) -> None:
        self.viewmodel.set_kpi(
            key,
            value=value,
            trend=trend,
            tone=tone,
        )

    def set_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        self.kpi_center.set_theme(self._theme)
        for section in self._themed_sections:
            section.apply_theme(self._theme)
        self._apply_page_theme()

    def _on_kpi_changed(self, key: str, kpi: DashboardKpi) -> None:
        self.kpi_center.update_kpi(kpi)

    def _refresh_updated_label(self) -> None:
        updated = self.viewmodel.state.last_updated
        self.updated_label.setText(
            f"Обновлено: {updated:%d.%m.%Y %H:%M:%S}"
            if updated is not None
            else "Данные ещё не обновлялись"
        )

    def _apply_page_theme(self) -> None:
        palette = get_palette(self._theme)
        self.setStyleSheet(
            f"""
            QWidget#DashboardPage, QWidget#DashboardCanvas {{
                background-color: {palette.app_background};
            }}
            QScrollArea#DashboardScroll {{
                background-color: {palette.app_background};
                border: none;
            }}
            QLabel#DashboardTitle {{
                color: {palette.text_primary};
                {Typography.H1.css()}
            }}
            QLabel#DashboardSubtitle, QLabel#DashboardUpdated {{
                color: {palette.text_muted};
                {Typography.BODY_S.css()}
            }}
            QLabel#DashboardEmptyText {{
                color: {palette.text_muted};
                background: transparent;
                border: none;
                padding: 12px 0;
                {Typography.BODY_M.css()}
            }}
            QListWidget#RecentTenderList,
            QListWidget#AiRecommendationList {{
                background-color: {palette.input_background};
                color: {palette.text_primary};
                border: 1px solid {palette.border_subtle};
                border-radius: 10px;
                padding: 6px;
                outline: none;
                {Typography.BODY_S.css()}
            }}
            QListWidget#RecentTenderList::item,
            QListWidget#AiRecommendationList::item {{
                border-bottom: 1px solid {palette.divider};
                padding: 10px;
            }}
            QListWidget#RecentTenderList::item:selected,
            QListWidget#AiRecommendationList::item:selected {{
                background-color: {palette.selected_background};
                color: {palette.text_primary};
                border-radius: 7px;
            }}
            """
        )


__all__ = ["DashboardPage"]
