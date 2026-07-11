"""Dashboard 1.0 with integrated AI Advisor."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QResizeEvent
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

from app.ui.dashboard.activity_feed import (
    ActivityEntry,
    ActivityFeed,
    ActivityTone,
)
from app.ui.dashboard.ai_advisor import AiAdvisor
from app.ui.dashboard.data_state import DataState, DataStateKind
from app.ui.dashboard.demo_data import (
    DashboardDemoSnapshot,
    build_demo_snapshot,
    build_empty_dashboard_kpis,
    demo_mode_from_environment,
)
from app.ui.dashboard.keyboard_navigation import (
    DashboardShortcutManager,
)
from app.ui.dashboard.kpi_center import KpiCenter
from app.ui.dashboard.quick_actions import QuickActions
from app.ui.dashboard.responsive import (
    DashboardLayoutSpec,
    dashboard_layout_for_width,
)
from app.ui.dashboard.section import DashboardSection
from app.ui.dashboard.status_banner import (
    DashboardStatusBanner,
    StatusTone,
)
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
from app.ui.widgets.button import OutlineButton


class DashboardPage(QWidget):
    """Responsive Dashboard 1.0 with KPI, tender feed and AI Advisor."""

    find_tenders_requested = Signal()
    create_proposal_requested = Signal()
    create_estimate_requested = Signal()
    analyze_documents_requested = Signal()
    tender_open_requested = Signal(str)
    recommendation_action_requested = Signal(int)
    kpi_action_requested = Signal(str)
    demo_mode_changed = Signal(bool)

    def __init__(
        self,
        viewmodel: DashboardViewModel | None = None,
        advisor_viewmodel: AiAdvisorViewModel | None = None,
        *,
        theme: ThemeName | str = ThemeName.DARK,
        demo_mode: bool | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._theme = ThemeName(theme)
        self.viewmodel = viewmodel or DashboardViewModel(self)
        self.advisor_viewmodel = advisor_viewmodel or AiAdvisorViewModel(self)
        self._themed_sections: list[DashboardSection] = []
        self._layout_spec: DashboardLayoutSpec | None = None
        self._data_state = DataState.ready()
        self._demo_mode = (
            demo_mode_from_environment()
            if demo_mode is None
            else bool(demo_mode)
        )

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
        self.canvas.setMinimumWidth(0)

        self.main_layout = QVBoxLayout(self.canvas)
        self.main_layout.setContentsMargins(24, 22, 24, 28)
        self.main_layout.setSpacing(16)

        self._build_header()
        self._build_status_zone()
        self._build_kpi_zone()
        self._build_primary_zone()
        self._build_secondary_zone()
        self._apply_responsive_layout(force=True)
        self._build_keyboard_navigation()

        self.scroll.setWidget(self.canvas)
        root.addWidget(self.scroll)

        self._connect_dashboard_viewmodel()
        self._connect_advisor_viewmodel()
        self._apply_page_theme()
        self.refresh_from_state()
        self._render_advisor_state()
        if self._demo_mode:
            self.load_demo_data()

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

        self.refresh_button = OutlineButton(
            "Обновить",
            icon_text="↻",
            theme=self._theme,
        )
        self.refresh_button.clicked.connect(
            self.viewmodel.request_refresh
        )

        header.addLayout(title_column, 1)
        header.addWidget(self.updated_label)
        header.addWidget(self.refresh_button)
        self.main_layout.addLayout(header)

    def _build_status_zone(self) -> None:
        self.status_banner = DashboardStatusBanner(
            theme=self._theme,
            parent=self.canvas,
        )
        self.status_banner.action_requested.connect(
            self._handle_status_action
        )
        self.main_layout.addWidget(self.status_banner)

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
        self.primary_grid = QGridLayout()
        self.primary_grid.setContentsMargins(0, 0, 0, 0)
        self.primary_grid.setHorizontalSpacing(16)
        self.primary_grid.setVerticalSpacing(16)

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
        self.tender_feed.state_action_requested.connect(
            self._handle_data_state_action
        )
        self.tender_section.add_widget(self.tender_feed)

        self.ai_advisor = AiAdvisor(
            theme=self._theme,
            parent=self.canvas,
        )
        self.ai_advisor.setMinimumHeight(360)

        self.primary_grid.addWidget(self.tender_section, 0, 0)
        self.primary_grid.addWidget(self.ai_advisor, 0, 1)
        self.primary_grid.setColumnStretch(0, 3)
        self.primary_grid.setColumnStretch(1, 2)

        self.main_layout.addLayout(self.primary_grid)

    def _build_secondary_zone(self) -> None:
        self.secondary_grid = QGridLayout()
        self.secondary_grid.setContentsMargins(0, 0, 0, 0)
        self.secondary_grid.setHorizontalSpacing(16)
        self.secondary_grid.setVerticalSpacing(16)

        self.quick_section = self._section(
            "Быстрые действия",
            subtitle="Частые операции без перехода по меню",
        )
        self.quick_actions = QuickActions(
            theme=self._theme,
            columns=2,
            parent=self.quick_section,
        )
        self.quick_actions.action_requested.connect(
            self._handle_quick_action
        )
        self.quick_section.add_widget(self.quick_actions)

        self.activity_section = self._section(
            "Лента событий",
            subtitle="Последние действия и изменения системы",
            badge="Сегодня",
        )
        self.activity_feed = ActivityFeed(
            theme=self._theme,
            max_entries=30,
            parent=self.activity_section,
        )
        self.activity_feed.setMinimumHeight(250)
        self.activity_feed.action_requested.connect(
            self._handle_activity_action
        )
        self.activity_section.add_widget(self.activity_feed)

        self.secondary_grid.addWidget(self.quick_section, 0, 0)
        self.secondary_grid.addWidget(self.activity_section, 0, 1)
        self.secondary_grid.setColumnStretch(0, 3)
        self.secondary_grid.setColumnStretch(1, 2)

        self.main_layout.addLayout(self.secondary_grid)
        self.main_layout.addStretch(1)

    def _build_keyboard_navigation(self) -> None:
        self.shortcut_manager = DashboardShortcutManager(self)
        self.shortcut_manager.action_requested.connect(
            self._handle_keyboard_action
        )
        self.setFocusProxy(self.refresh_button)
        self._configure_tab_order()

    def _configure_tab_order(self) -> None:
        """Create a predictable top-to-bottom keyboard route."""
        widgets: list[QWidget] = [self.refresh_button]
        widgets.extend(self.kpi_center.cards.values())
        widgets.append(self.tender_feed.table)
        widgets.append(self.ai_advisor.action_button)
        widgets.extend(self.quick_actions.tiles)
        widgets.extend(self.activity_feed.items)

        if not self.activity_feed.items:
            widgets.append(self.activity_feed.scroll)

        previous: QWidget | None = None
        for widget in widgets:
            if previous is not None:
                QWidget.setTabOrder(previous, widget)
            previous = widget

    def _handle_keyboard_action(self, action_key: str) -> None:
        if action_key in self.quick_actions.action_keys:
            self.quick_actions.trigger(action_key)
            return

        if action_key == "refresh_dashboard":
            self.viewmodel.request_refresh()
        elif action_key == "focus_kpis":
            self.kpi_center.focus_first()
        elif action_key == "focus_tenders":
            self.tender_feed.focus_table()
        elif action_key == "focus_advisor":
            self.ai_advisor.action_button.setFocus(
                Qt.FocusReason.ShortcutFocusReason
            )
        elif action_key == "focus_quick_actions":
            self.quick_actions.focus_first()
        elif action_key == "focus_activity":
            self.activity_feed.focus_first()
        elif action_key == "dismiss_status":
            self.status_banner.clear()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._apply_responsive_layout()

    @property
    def demo_mode(self) -> bool:
        return self._demo_mode

    def load_demo_data(
        self,
        snapshot: DashboardDemoSnapshot | None = None,
    ) -> None:
        """Load synthetic Corteris data for visual and UX review."""
        demo = snapshot or build_demo_snapshot()
        self._demo_mode = True

        self.set_data_state(
            DataState.loading(
                "Подготавливаем демонстрационные KPI, тендеры "
                "и AI-рекомендации."
            )
        )

        for kpi in demo.kpis:
            self.viewmodel.set_kpi(
                kpi.key,
                value=kpi.value,
                trend=kpi.trend,
                tone=kpi.tone,
                title=kpi.title,
                icon_text=kpi.icon_text,
            )

        self.viewmodel.set_recent_tenders(demo.tenders)
        self.viewmodel.set_ai_recommendations(demo.recommendations)
        self.activity_feed.set_entries(demo.activities)
        self.activity_section.set_badge(
            str(len(demo.activities))
        )

        self.set_data_state(DataState.ready())
        self._sync_advisor_from_dashboard()
        self._configure_tab_order()

        self.subtitle_label.setText(
            "Демонстрационный режим — используются синтетические данные."
        )
        self.quick_actions.set_badge("find_tenders", "DEMO")
        self.status_banner.show_status(
            title="Демонстрационный режим",
            message=(
                "Все показанные закупки и организации вымышлены "
                "и используются только для проверки интерфейса."
            ),
            tone=StatusTone.INFO,
            action_text="Выключить демо",
            action_key="disable_demo_mode",
        )
        self.demo_mode_changed.emit(True)

    def disable_demo_mode(self) -> None:
        """Clear synthetic data and restore the normal empty state."""
        if not self._demo_mode:
            return

        self._demo_mode = False

        for kpi in build_empty_dashboard_kpis():
            self.viewmodel.set_kpi(
                kpi.key,
                value=kpi.value,
                trend=kpi.trend,
                tone=kpi.tone,
                title=kpi.title,
                icon_text=kpi.icon_text,
            )

        self.viewmodel.set_recent_tenders([])
        self.viewmodel.set_ai_recommendations([])
        self.activity_feed.clear()
        self.activity_section.set_badge("Сегодня")
        self.quick_actions.set_badge("find_tenders", "")
        self.subtitle_label.setText(
            "Ключевые показатели, тендеры и действия на сегодня."
        )
        self.set_data_state(
            DataState.empty(
                "Новые тендеры появятся после запуска поиска."
            )
        )
        self.status_banner.clear()
        self._configure_tab_order()
        self.demo_mode_changed.emit(False)

    @property
    def data_state(self) -> DataState:
        return self._data_state

    def set_data_state(self, state: DataState) -> None:
        """Apply one semantic state to all Dashboard data components."""
        self._data_state = state
        self.kpi_center.set_data_state(state)
        self.tender_feed.set_data_state(state)
        self.ai_advisor.set_data_state(state)

        actions_enabled = state.kind != DataStateKind.LOADING
        for key in self.quick_actions.action_keys:
            self.quick_actions.set_enabled(key, actions_enabled)

        badge = {
            DataStateKind.READY: (
                str(len(self.tender_feed.model.tenders))
                if self.tender_feed.model.tenders
                else "Тендеры"
            ),
            DataStateKind.LOADING: "…",
            DataStateKind.EMPTY: "0",
            DataStateKind.ERROR: "!",
            DataStateKind.PARTIAL: "Частично",
        }[state.kind]
        self.tender_section.set_badge(badge)

    def set_refreshing(self, refreshing: bool) -> None:
        """Toggle refresh loading and provide visible status feedback."""
        self.refresh_button.set_loading(bool(refreshing))
        self.refresh_button.setEnabled(not refreshing)

        if refreshing:
            self.set_data_state(
                DataState.loading(
                    "Получаем актуальные тендеры, KPI и AI-рекомендации."
                )
            )
            self.status_banner.show_status(
                title="Обновление данных",
                message="Получаем актуальные тендеры и показатели.",
                tone=StatusTone.LOADING,
                dismissible=False,
            )
        else:
            if self._data_state.kind == DataStateKind.LOADING:
                next_state = (
                    DataState.ready()
                    if self.tender_feed.model.rowCount() > 0
                    else DataState.empty(
                        "По текущим условиям тендеры не найдены."
                    )
                )
                self.set_data_state(next_state)

            if self.status_banner.tone == StatusTone.LOADING:
                self.status_banner.show_status(
                    title="Данные обновлены",
                    message="Рабочий стол содержит актуальную информацию.",
                    tone=StatusTone.SUCCESS,
                    auto_hide_ms=2500,
                )

    def set_partial_data(self, message: str) -> None:
        self.set_data_state(DataState.partial(message))
        self.status_banner.show_status(
            title="Данные загружены частично",
            message=message,
            tone=StatusTone.WARNING,
        )

    def show_error(
        self,
        message: str,
        *,
        action_text: str = "Повторить",
        action_key: str = "refresh_dashboard",
    ) -> None:
        """Show a recoverable Dashboard error."""
        self.set_data_state(
            DataState.error(
                message,
                action_text=action_text,
                action_key=action_key,
            )
        )
        self.status_banner.show_status(
            title="Не удалось выполнить операцию",
            message=message,
            tone=StatusTone.ERROR,
            action_text=action_text,
            action_key=action_key,
        )

    def show_warning(self, message: str) -> None:
        """Show a non-blocking Dashboard warning."""
        self.status_banner.show_status(
            title="Требуется внимание",
            message=message,
            tone=StatusTone.WARNING,
        )

    def _apply_responsive_layout(self, *, force: bool = False) -> None:
        viewport_width = self.scroll.viewport().width()
        available_width = viewport_width if viewport_width > 0 else self.width()
        spec = dashboard_layout_for_width(available_width)

        if not force and spec == self._layout_spec:
            return

        self._layout_spec = spec
        margin = spec.outer_margin
        self.main_layout.setContentsMargins(
            margin,
            margin,
            margin,
            margin + 4,
        )
        self.main_layout.setSpacing(spec.section_spacing)

        self.kpi_center.set_columns(spec.kpi_columns)
        self.quick_actions.set_columns(spec.quick_action_columns)
        self.quick_actions.set_compact(spec.compact)
        self.ai_advisor.set_compact(spec.compact)
        self.tender_feed.set_state_compact(spec.compact)

        self.tender_feed.setMinimumHeight(spec.tender_min_height)
        self.ai_advisor.setMinimumHeight(spec.advisor_min_height)
        self.activity_feed.setMinimumHeight(spec.activity_min_height)

        self.updated_label.setVisible(not spec.compact)
        self.subtitle_label.setVisible(
            spec.density.value not in {"narrow"}
        )

        self._reflow_grid(
            self.primary_grid,
            self.tender_section,
            self.ai_advisor,
            columns=spec.primary_columns,
            spacing=spec.grid_spacing,
            first_stretch=3,
            second_stretch=2,
        )
        self._reflow_grid(
            self.secondary_grid,
            self.quick_section,
            self.activity_section,
            columns=spec.secondary_columns,
            spacing=spec.grid_spacing,
            first_stretch=3,
            second_stretch=2,
        )

    @staticmethod
    def _reflow_grid(
        grid: QGridLayout,
        first: QWidget,
        second: QWidget,
        *,
        columns: int,
        spacing: int,
        first_stretch: int,
        second_stretch: int,
    ) -> None:
        grid.removeWidget(first)
        grid.removeWidget(second)
        grid.setHorizontalSpacing(spacing)
        grid.setVerticalSpacing(spacing)

        for column in range(2):
            grid.setColumnStretch(column, 0)

        if columns <= 1:
            grid.addWidget(first, 0, 0)
            grid.addWidget(second, 1, 0)
            grid.setColumnStretch(0, 1)
            return

        grid.addWidget(first, 0, 0)
        grid.addWidget(second, 0, 1)
        grid.setColumnStretch(0, first_stretch)
        grid.setColumnStretch(1, second_stretch)

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

        if self._data_state.kind not in {
            DataStateKind.LOADING,
            DataStateKind.ERROR,
            DataStateKind.PARTIAL,
        }:
            self.set_data_state(
                DataState.ready()
                if tenders
                else DataState.empty(
                    "Новые тендеры появятся после запуска поиска."
                )
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
        self.quick_actions.apply_theme(self._theme)
        self.activity_feed.apply_theme(self._theme)
        self.status_banner.apply_theme(self._theme)
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
        if self._data_state.kind in {
            DataStateKind.LOADING,
            DataStateKind.ERROR,
        }:
            return

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

    def _handle_quick_action(self, action_key: str) -> None:
        activity_map = {
            "find_tenders": (
                "Запущен поиск тендеров",
                "Система начала поиск новых закупок.",
                "T",
                ActivityTone.INFO,
            ),
            "analyze_documents": (
                "Запущен AI-анализ",
                "Документы переданы на проверку требований и рисков.",
                "AI",
                ActivityTone.INFO,
            ),
            "create_proposal": (
                "Создание коммерческого предложения",
                "Открыт модуль подготовки КП.",
                "КП",
                ActivityTone.SUCCESS,
            ),
            "create_estimate": (
                "Создание сметы",
                "Открыт расчёт оборудования, работ и прибыли.",
                "₽",
                ActivityTone.NEUTRAL,
            ),
        }
        activity = activity_map.get(action_key)
        if activity is not None:
            title, description, icon_text, tone = activity
            self.add_activity(
                title=title,
                description=description,
                icon_text=icon_text,
                tone=tone,
            )
            self.status_banner.show_status(
                title=title,
                message=description,
                tone=StatusTone.INFO,
                auto_hide_ms=3200,
            )

        if action_key == "find_tenders":
            self.find_tenders_requested.emit()
        elif action_key == "analyze_documents":
            self.analyze_documents_requested.emit()
        elif action_key == "create_proposal":
            self.create_proposal_requested.emit()
        elif action_key == "create_estimate":
            self.create_estimate_requested.emit()

    def _handle_data_state_action(self, action_key: str) -> None:
        if action_key == "disable_demo_mode":
            self.disable_demo_mode()
            return
        if action_key == "refresh_dashboard":
            self.viewmodel.request_refresh()
            return
        if action_key in self.quick_actions.action_keys:
            self.quick_actions.trigger(action_key)

    def _handle_status_action(self, action_key: str) -> None:
        self.status_banner.clear()
        self._handle_data_state_action(action_key)

    def _handle_activity_action(self, action_key: str) -> None:
        if action_key.startswith("open_tender:"):
            tender_number = action_key.partition(":")[2]
            if tender_number:
                self.tender_open_requested.emit(tender_number)
            return
        self._handle_quick_action(action_key)

    def add_activity(
        self,
        *,
        title: str,
        description: str = "",
        icon_text: str = "•",
        tone: ActivityTone = ActivityTone.NEUTRAL,
        action_text: str = "",
        action_key: str = "",
        key: str = "",
    ) -> None:
        entry = ActivityEntry(
            key=key or f"activity-{datetime.now().timestamp()}",
            title=title,
            description=description,
            timestamp=datetime.now(),
            tone=tone,
            icon_text=icon_text,
            action_text=action_text,
            action_key=action_key,
        )
        self.activity_feed.add_entry(entry)
        self.activity_section.set_badge(
            str(len(self.activity_feed.entries))
        )
        self._configure_tab_order()

    def _handle_advisor_action(self, action_key: str) -> None:
        if action_key.startswith("open_tender:"):
            tender_number = action_key.partition(":")[2]
            if tender_number:
                self.tender_open_requested.emit(tender_number)
            return

        self._handle_quick_action(action_key)

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
