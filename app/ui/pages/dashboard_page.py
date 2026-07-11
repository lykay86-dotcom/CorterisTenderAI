"""Dashboard 1.0 with integrated AI Advisor."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.ui.dashboard.ai_advisor import AiAdvisor
from app.ui.dashboard.kpi_center import KpiCenter
from app.ui.dashboard.section import DashboardSection
from app.ui.dashboard.tender_feed import TenderFeed
from app.ui.theme.colors import ThemeName, get_palette
from app.ui.theme.typography import Typography
from app.ui.viewmodels.ai_advisor_viewmodel import (
    AiAdvisorAction,
    AiAdvisorFocus,
    AiAdvisorMetrics,
    AiAdvisorViewModel,
)
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


class DashboardPage(QWidget):
    """Responsive Dashboard 1.0 with KPI, tender feed and AI Advisor."""

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
        advisor_viewmodel: AiAdvisorViewModel | None = None,
        *,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._theme = ThemeName(theme)
        self.viewmodel = viewmodel or DashboardViewModel(self)
        self.advisor_viewmodel = advisor_viewmodel or AiAdvisorViewModel(self)
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

        self._connect_dashboard_viewmodel()
        self._connect_advisor_viewmodel()
        self._apply_page_theme()
        self.refresh_from_state()
        self._render_advisor_state()

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
        self.tender_feed = TenderFeed(
            theme=self._theme,
            parent=self.tender_section,
        )
        self.tender_feed.setMinimumHeight(360)
        self.tender_feed.tender_open_requested.connect(
            self.tender_open_requested
        )
        self.tender_section.add_widget(self.tender_feed)

        self.ai_advisor = AiAdvisor(
            theme=self._theme,
            parent=self.canvas,
        )
        self.ai_advisor.setMinimumHeight(360)

        grid.addWidget(self.tender_section, 0, 0)
        grid.addWidget(self.ai_advisor, 0, 1)
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

        find_button = PrimaryButton("Найти тендеры", theme=self._theme)
        proposal_button = SecondaryButton("Создать КП", theme=self._theme)
        estimate_button = SecondaryButton("Создать смету", theme=self._theme)
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

    def _connect_dashboard_viewmodel(self) -> None:
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

    def _connect_advisor_viewmodel(self) -> None:
        self.advisor_viewmodel.status_changed.connect(
            self.ai_advisor.set_status
        )
        self.advisor_viewmodel.metrics_changed.connect(
            self._render_advisor_metrics
        )
        self.advisor_viewmodel.focus_changed.connect(
            self._render_advisor_focus
        )
        self.advisor_viewmodel.reasons_changed.connect(
            lambda reasons: self.ai_advisor.set_reasons(list(reasons))
        )
        self.advisor_viewmodel.warning_changed.connect(
            self.ai_advisor.set_warning
        )
        self.advisor_viewmodel.action_changed.connect(
            self._render_advisor_action
        )
        self.ai_advisor.action_requested.connect(
            self._handle_advisor_action
        )

    def refresh_from_state(self) -> None:
        for key, kpi in self.viewmodel.state.kpis.items():
            self._on_kpi_changed(key, kpi)
        self.set_recent_tenders(self.viewmodel.state.recent_tenders)
        self.set_ai_recommendations(
            self.viewmodel.state.ai_recommendations
        )
        self._refresh_updated_label()
        self._sync_advisor_from_dashboard()

    def set_recent_tenders(self, tenders: list[RecentTender]) -> None:
        self.tender_feed.set_tenders(tenders)
        self.tender_section.set_badge(
            str(len(tenders)) if tenders else "Тендеры"
        )
        self._sync_advisor_from_dashboard()

    def set_ai_recommendations(
        self,
        recommendations: list[AiRecommendation],
    ) -> None:
        self._sync_advisor_from_dashboard(recommendations)

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
        self.tender_feed.apply_theme(self._theme)
        self.ai_advisor.apply_theme(self._theme)
        for section in self._themed_sections:
            section.apply_theme(self._theme)
        self._apply_page_theme()

    def _on_kpi_changed(self, key: str, kpi: DashboardKpi) -> None:
        self.kpi_center.update_kpi(kpi)
        self._sync_advisor_from_dashboard()

    def _sync_advisor_from_dashboard(
        self,
        recommendations: list[AiRecommendation] | None = None,
    ) -> None:
        state = self.viewmodel.state
        recommendations = (
            state.ai_recommendations
            if recommendations is None
            else recommendations
        )

        self.advisor_viewmodel.set_metrics(
            new_tenders=self._kpi_int("new_tenders"),
            recommended=self._kpi_int("recommended"),
            attention=self._kpi_int("attention"),
        )

        priority = self._priority_tender(state.recent_tenders)
        if priority is None:
            self.advisor_viewmodel.set_focus(
                title="Запустите поиск тендеров, чтобы получить рекомендацию"
            )
            self.advisor_viewmodel.set_reasons([])
            self.advisor_viewmodel.set_warning("")
            self.advisor_viewmodel.set_action(
                text="Найти тендеры",
                key="find_tenders",
            )
            return

        self.advisor_viewmodel.set_focus(
            title=priority.title,
            number=priority.number,
            amount=priority.nmck,
            score=priority.score,
        )
        reasons = [
            item.description or item.title
            for item in recommendations
            if item.severity in {"success", "info"}
        ]
        self.advisor_viewmodel.set_reasons(reasons)

        warnings = [
            item.description or item.title
            for item in recommendations
            if item.severity in {"warning", "danger"}
        ]
        self.advisor_viewmodel.set_warning(
            warnings[0] if warnings else ""
        )
        self.advisor_viewmodel.set_action(
            text="Открыть приоритетный тендер",
            key=f"open_tender:{priority.number}",
        )

    def _render_advisor_state(self) -> None:
        state = self.advisor_viewmodel.state
        self.ai_advisor.set_status(state.status, state.status_text or None)
        self._render_advisor_metrics(state.metrics)
        self._render_advisor_focus(state.focus)
        self.ai_advisor.set_reasons(list(state.reasons))
        self.ai_advisor.set_warning(state.warning)
        self._render_advisor_action(state.action)

    def _render_advisor_metrics(self, metrics: AiAdvisorMetrics) -> None:
        self.ai_advisor.set_metrics(
            new_tenders=metrics.new_tenders,
            recommended=metrics.recommended,
            attention=metrics.attention,
        )

    def _render_advisor_focus(self, focus: AiAdvisorFocus) -> None:
        self.ai_advisor.set_focus(
            title=focus.title,
            number=focus.number,
            amount=focus.amount,
            score=focus.score,
        )

    def _render_advisor_action(self, action: AiAdvisorAction) -> None:
        self.ai_advisor.set_action(
            text=action.text,
            action_key=action.key,
            enabled=action.enabled,
        )

    def _handle_advisor_action(self, action_key: str) -> None:
        if action_key == "find_tenders":
            self.find_tenders_requested.emit()
            return
        if action_key == "create_proposal":
            self.create_proposal_requested.emit()
            return
        if action_key == "create_estimate":
            self.create_estimate_requested.emit()
            return
        if action_key == "analyze_documents":
            self.analyze_documents_requested.emit()
            return
        if action_key.startswith("open_tender:"):
            tender_number = action_key.partition(":")[2]
            if tender_number:
                self.tender_open_requested.emit(tender_number)

    def _kpi_int(self, key: str) -> int:
        kpi = self.viewmodel.state.kpis.get(key)
        if kpi is None:
            return 0
        digits = "".join(character for character in kpi.value if character.isdigit())
        return int(digits) if digits else 0

    @staticmethod
    def _priority_tender(
        tenders: list[RecentTender],
    ) -> RecentTender | None:
        if not tenders:
            return None
        return max(
            tenders,
            key=lambda tender: tender.score if tender.score is not None else -1,
        )

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
            """
        )


__all__ = ["DashboardPage"]
