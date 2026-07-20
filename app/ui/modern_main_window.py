"""Modern application shell for Corteris Tender AI v1.3 Alpha."""

from __future__ import annotations

from itertools import pairwise
from typing import TYPE_CHECKING

from PySide6.QtCore import QSettings
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow, QMessageBox, QWidget

from app.repositories.business_metrics import (
    BusinessMetricsRepository,
    BusinessRecordKind,
)
from app.ui.controllers.dashboard_controller import DashboardController
from app.ui.navigation import (
    NavigationCause,
    NavigationStatus,
    RouteContext,
    RouteId,
    RouteRequest,
    RouteResult,
)
from app.ui.pages.business_workflow_page import (
    BusinessWorkflowPage,
    WorkflowNavigationState,
)
from app.ui.pages.dashboard_page import DashboardPage
from app.ui.pages.tender_analytics_page import TenderAnalyticsPage
from app.ui.pages.tender_workspace_page import TenderWorkspacePage
from app.ui.theme.colors import ThemeName
from app.ui.theme.stylesheet import build_stylesheet
from app.ui.viewmodels.dashboard_viewmodel import DashboardKpiAction
from app.ui.widgets.dashboard_layout import DashboardLayout

if TYPE_CHECKING:
    from app.core.ai.provider_selection import AiProviderSelectionService
    from app.ui.controllers.tender_analytics_controller import TenderAnalyticsController
    from app.ui.tender_search_ui_controller import TenderSearchUiController


class ModernMainWindow(QMainWindow):
    """New Corteris workspace while preserving the existing working modules."""

    ORGANIZATION = "Corteris"
    APPLICATION = "CorterisTenderAI"

    def __init__(
        self,
        *,
        ai_provider_selection_service: "AiProviderSelectionService | None" = None,
    ) -> None:
        super().__init__()

        self._close_started = False
        self._close_complete = False
        self._dashboard_shutdown = False
        self._analytics_shutdown = False

        self.setObjectName("ModernMainWindow")
        self.setWindowTitle("Corteris Tender AI 1.3 Alpha")
        self.resize(1540, 940)
        self.setMinimumSize(960, 540)

        self._settings = QSettings(self.ORGANIZATION, self.APPLICATION)
        self._theme = self._load_theme()

        self.workspace = DashboardLayout(self)
        self.setCentralWidget(self.workspace)

        self.dashboard_page = DashboardPage(
            theme=self._theme,
            parent=self.workspace.pages,
        )
        self.workspace.add_page(
            "dashboard",
            "Рабочий стол",
            self.dashboard_page,
        )
        self.dashboard_controller = DashboardController(
            self.dashboard_page,
            parent=self,
        )

        self.tender_workspace_page = TenderWorkspacePage(
            ai_provider_selection_service=ai_provider_selection_service,
            status_bar=self.statusBar(),
            parent=self.workspace.pages,
        )
        self.workspace.add_page(
            "tenders",
            "Тендеры и рабочие модули",
            self.tender_workspace_page,
        )

        self.business_repository = BusinessMetricsRepository()

        self.workflow_page = BusinessWorkflowPage(
            repository=self.business_repository,
            theme=self._theme,
            parent=self.workspace.pages,
        )
        self.workspace.add_page(
            "workflow",
            "КП, сметы и проекты",
            self.workflow_page,
        )

        self.analytics_page = TenderAnalyticsPage(
            theme=self._theme,
            parent=self.workspace.pages,
        )
        self.workspace.add_page(
            "analytics",
            "Аналитика",
            self.analytics_page,
        )
        self.analytics_controller: TenderAnalyticsController | None = None

        self._configure_dashboard_tab_order()

        # RM-127/RM-142 compatibility names intentionally reference the same
        # canonical object. RM-155 owns their eventual retirement.
        self.quotes_page = self.workflow_page
        self.estimates_page = self.workflow_page

        self._register_navigation_destinations()

        self._connect_actions()
        self.dashboard_controller.tender_selected.connect(self._open_tender_from_dashboard)
        self.dashboard_controller.refresh_succeeded.connect(
            lambda snapshot: self.statusBar().showMessage(
                f"Dashboard обновлён · тендеров: {len(snapshot.tenders)}",
                4000,
            )
        )
        self.dashboard_controller.refresh_failed.connect(
            lambda message: self.statusBar().showMessage(
                message,
                8000,
            )
        )

        self.workflow_page.tender_open_requested.connect(self._open_tender_from_dashboard)
        self.workflow_page.workflow_changed.connect(self._business_workflow_changed)

        self.apply_theme(self._theme)
        self.workspace.navigate(
            RouteRequest(
                RouteId.DASHBOARD,
                cause=NavigationCause.PROGRAMMATIC,
                record_history=False,
            )
        )

    def _configure_dashboard_tab_order(self) -> None:
        controls: tuple[QWidget, ...] = (
            *self.workspace.sidebar.keyboard_focus_chain(),
            *self.workspace.topbar.keyboard_focus_chain(),
            *self.dashboard_page.keyboard_focus_chain(),
        )
        for current, following in pairwise(controls):
            QWidget.setTabOrder(current, following)
        self.dashboard_page.set_tab_exit_target(controls[0])
        self.dashboard_controller.start()

        self.statusBar().showMessage(
            "Corteris Tender AI 1.3 Alpha · система готова",
            5000,
        )

    def _load_theme(self) -> ThemeName:
        saved = self._settings.value("ui/theme", ThemeName.DARK.value)
        try:
            return ThemeName(str(saved))
        except ValueError:
            return ThemeName.DARK

    def _connect_actions(self) -> None:
        self.workspace.topbar.theme_toggled.connect(self.toggle_theme)
        self.workspace.topbar.search_requested.connect(self._global_search)
        self.workspace.topbar.ai_clicked.connect(
            lambda: self._navigate(
                RouteId.TENDER_AI,
                cause=NavigationCause.TOPBAR,
                focus_token="TopBarAiButton",
            )
        )
        self.workspace.topbar.notifications_clicked.connect(
            lambda: self._navigate(
                RouteId.TENDER_NOTIFICATIONS,
                cause=NavigationCause.TOPBAR,
                focus_token="TopBarNotificationsButton",
            )
        )
        self.workspace.topbar.profile_clicked.connect(
            lambda: self._navigate(
                RouteId.PROFILE,
                cause=NavigationCause.TOPBAR,
                focus_token="TopBarProfileButton",
            )
        )

        self.dashboard_page.find_tenders_requested.connect(
            lambda: self._navigate(
                RouteId.TENDERS,
                cause=NavigationCause.QUICK_ACTION,
                focus_token="QuickActionTile",
            )
        )
        self.dashboard_page.create_proposal_requested.connect(
            lambda: self._navigate(
                RouteId.WORKFLOW_PROPOSALS,
                cause=NavigationCause.QUICK_ACTION,
                focus_token="QuickActionTile",
            )
        )
        self.dashboard_page.create_estimate_requested.connect(
            lambda: self._navigate(
                RouteId.WORKFLOW_ESTIMATES,
                cause=NavigationCause.QUICK_ACTION,
                focus_token="QuickActionTile",
            )
        )
        self.dashboard_page.analyze_documents_requested.connect(
            lambda: self._navigate(
                RouteId.TENDER_AI,
                cause=NavigationCause.QUICK_ACTION,
                focus_token="QuickActionTile",
            )
        )
        self.dashboard_page.kpi_action_requested.connect(self._open_dashboard_kpi)

    def _register_navigation_destinations(self) -> None:
        """Bind canonical routes to the existing page and controller owners."""
        self.workspace.register_route_handler(
            RouteId.FUTURE_ANALYTICS,
            self._show_analytics_page,
        )
        self.workspace.register_route_handler(RouteId.TENDERS, self._activate_tender_route)
        self.workspace.register_route_handler(RouteId.TENDER_AI, self._activate_tender_route)
        self.workspace.register_route_handler(RouteId.TENDER_SETTINGS, self._activate_tender_route)

        self.workspace.register_route_handler(
            RouteId.WORKFLOW,
            lambda context: self._activate_workflow(RouteId.WORKFLOW, context),
        )
        self.workspace.register_route_handler(
            RouteId.WORKFLOW_PROPOSALS,
            lambda context: self._activate_workflow(RouteId.WORKFLOW_PROPOSALS, context),
        )
        self.workspace.register_route_handler(
            RouteId.WORKFLOW_ESTIMATES,
            lambda context: self._activate_workflow(RouteId.WORKFLOW_ESTIMATES, context),
        )
        self.workspace.register_route_handler(
            RouteId.WORKFLOW_PROJECTS,
            lambda context: self._activate_workflow(RouteId.WORKFLOW_PROJECTS, context),
        )

        self.workspace.register_context_provider(
            "workflow",
            lambda: self._workflow_route_context(self.workflow_page),
        )
        self.workspace.register_route_handler(
            RouteId.TENDER_DOCUMENTS,
            self._open_tender_documents,
        )
        self.workspace.register_route_handler(
            RouteId.TENDER_SCHEDULER,
            lambda _context: self._trigger_tender_action("schedule_action"),
        )
        self.workspace.register_route_handler(
            RouteId.TENDER_NOTIFICATIONS,
            lambda _context: self._trigger_tender_action("notifications_action"),
        )
        self.workspace.register_route_handler(
            RouteId.PROFILE,
            self._open_profile,
        )

    def _show_analytics_page(self, _context: RouteContext) -> bool:
        controller = self.analytics_controller
        if controller is not None:
            controller.refresh()
        return True

    def bind_tender_analytics_runtime(
        self,
        tender_search_controller: TenderSearchUiController,
    ) -> None:
        """Bind analytics to the already installed tender runtime exactly once."""

        if self.analytics_controller is not None:
            return
        registry = tender_search_controller.runtime.tender_registry
        if registry is None:
            return
        from app.tenders.collector.store import CollectorStateRepository
        from app.ui.controllers.tender_analytics_controller import (
            TenderAnalyticsController,
        )

        self.analytics_controller = TenderAnalyticsController(
            self.analytics_page,
            registry,
            CollectorStateRepository(registry.path),
            business_repository=self.business_repository,
            parent=self,
        )
        self.analytics_page.contributor_activated.connect(
            tender_search_controller.open_registry_record
        )
        self.analytics_controller.start()

    @staticmethod
    def _workflow_route_context(page: BusinessWorkflowPage) -> RouteContext:
        state = page.capture_navigation_state()
        return RouteContext(
            workflow_kind=state.kind or None,
            workflow_status=state.status or None,
            workflow_archive_mode=state.archive_mode or None,
            workflow_search=state.search_text or None,
            workflow_record_id=state.record_id,
            dashboard_filter=state.dashboard_filter or None,
        )

    def _activate_workflow(self, route_id: RouteId, context: RouteContext) -> bool:
        route_kind = {
            RouteId.WORKFLOW_PROPOSALS: BusinessRecordKind.PROPOSAL.value,
            RouteId.WORKFLOW_ESTIMATES: BusinessRecordKind.ESTIMATE.value,
            RouteId.WORKFLOW_PROJECTS: BusinessRecordKind.PROJECT.value,
        }.get(route_id)
        self.workflow_page.apply_navigation_state(
            WorkflowNavigationState(
                search_text=context.workflow_search or "",
                kind=route_kind if route_kind is not None else context.workflow_kind or "",
                status=context.workflow_status or "",
                archive_mode=context.workflow_archive_mode
                or WorkflowNavigationState().archive_mode,
                record_id=context.workflow_record_id,
                dashboard_filter=context.dashboard_filter or "",
            )
        )
        return True

    def _activate_tender_route(self, context: RouteContext) -> bool:
        self.tender_workspace_page.apply_dashboard_filter(context.dashboard_filter)
        if (
            context.tender_section is not None
            and context.tender_section not in self.tender_workspace_page.section_keys
        ):
            return False
        if (
            context.settings_section is not None
            and context.settings_section not in self.tender_workspace_page.settings_section_keys
        ):
            return False
        if context.settings_section is not None and context.tender_section not in {
            None,
            "settings",
        }:
            return False
        if context.tender_id is not None:
            if context.tender_identity_kind == "registry":
                controller = getattr(self, "_tender_search_ui_controller", None)
                opener = getattr(controller, "open_registry_record", None)
                if not callable(opener) or not bool(opener(context.tender_id)):
                    return False
            elif context.tender_identity_kind in {None, "legacy_orm"}:
                if not self.tender_workspace_page.open_tender(context.tender_id):
                    return False
            else:
                return False
        if context.settings_section is not None:
            return self.tender_workspace_page.select_settings_section(context.settings_section)
        if context.tender_section is not None:
            return self.tender_workspace_page.select_section(context.tender_section)
        return True

    def _open_dashboard_kpi(self, action: DashboardKpiAction) -> None:
        """Navigate a KPI through the accepted typed route/context contract."""
        if not isinstance(action, DashboardKpiAction):
            raise TypeError("Dashboard KPI activation requires DashboardKpiAction")
        self._navigate(
            action.route_id,
            cause=NavigationCause.DEEP_LINK,
            context=RouteContext(dashboard_filter=action.filter_id.value),
            focus_token=action.focus_token,
        )

    def _open_tender_documents(self, context: RouteContext) -> bool:
        controller = getattr(self, "_tender_search_ui_controller", None)
        opener = getattr(controller, "open_registry_documents", None)
        if context.tender_id is None or not callable(opener):
            return False
        opener(context.tender_id)
        return True

    def _trigger_tender_action(self, action_name: str) -> bool:
        controller = getattr(self, "_tender_search_ui_controller", None)
        scheduler = getattr(controller, "scheduler_ui_controller", None)
        action = getattr(scheduler, action_name, None)
        trigger = getattr(action, "trigger", None)
        if not callable(trigger):
            return False
        trigger()
        return True

    def _open_profile(self, _context: RouteContext) -> bool:
        self._show_profile()
        return True

    def _navigate(
        self,
        target: RouteId | str,
        *,
        cause: NavigationCause,
        context: RouteContext = RouteContext(),
        focus_token: str | None = None,
    ) -> RouteResult:
        if self._close_started:
            return RouteResult(
                status=NavigationStatus.UNAVAILABLE,
                reason_code="shell_closing",
                message="Приложение завершает работу.",
                snapshot=self.workspace.current_snapshot,
            )
        result = self.workspace.navigate(
            RouteRequest(
                target,
                cause=cause,
                context=context,
                focus_token=focus_token,
            )
        )
        if not result.succeeded and result.message:
            self.statusBar().showMessage(result.message, 5000)
        return result

    def _business_workflow_changed(self) -> None:
        """Refresh the canonical workflow view and Dashboard KPI."""
        if self._close_started:
            return
        state = self.workflow_page.capture_navigation_state()
        self.workflow_page.refresh()
        self.workflow_page.apply_navigation_state(state)

        self.dashboard_controller.refresh()
        self.statusBar().showMessage(
            "Бизнес-процессы и Dashboard обновлены",
            4000,
        )

    def _open_tender_from_dashboard(self, tender_id: str) -> None:
        """Open a Dashboard tender in the existing working module."""
        result = self._navigate(
            RouteId.TENDERS,
            cause=NavigationCause.DEEP_LINK,
            context=RouteContext(tender_id=tender_id, tender_identity_kind="legacy_orm"),
        )
        if result.succeeded:
            self.statusBar().showMessage(
                f"Открыт тендер ID {tender_id}",
                5000,
            )
        else:
            self.statusBar().showMessage("Тендер с указанным ID не найден", 5000)

    def apply_theme(self, theme: ThemeName | str) -> None:
        """Apply and persist the selected UI theme."""
        self._theme = ThemeName(theme)
        self.setStyleSheet(build_stylesheet(self._theme.value))
        self.dashboard_page.set_theme(self._theme)
        self.workflow_page.apply_theme(self._theme)
        self.analytics_page.apply_theme(self._theme)
        tender_search = getattr(self, "_tender_search_ui_controller", None)
        apply_tender_search_theme = getattr(tender_search, "apply_theme", None)
        if callable(apply_tender_search_theme):
            apply_tender_search_theme(self._theme)
        self._settings.setValue("ui/theme", self._theme.value)

        self.workspace.topbar.apply_theme(self._theme)
        self.workspace.topbar.theme_button.setToolTip(
            "Включить светлую тему" if self._theme == ThemeName.DARK else "Включить тёмную тему"
        )

    def toggle_theme(self) -> None:
        """Switch between the dark and light themes."""
        new_theme = ThemeName.LIGHT if self._theme == ThemeName.DARK else ThemeName.DARK
        self.apply_theme(new_theme)

    def _global_search(self, query: str) -> None:
        normalized = query.strip()
        if not normalized:
            self.statusBar().showMessage("Введите поисковый запрос", 3000)
            return

        result = self._navigate(
            RouteId.TENDERS,
            cause=NavigationCause.TOPBAR,
            focus_token="TopBarTenderSearch",
        )
        if not result.succeeded:
            return
        if self.tender_workspace_page.submit_unified_search_text(normalized):
            self.statusBar().showMessage(f"Поиск тендеров: {normalized}", 5000)
        else:
            self.tender_workspace_page.focus_unified_search()
            self.statusBar().showMessage("Проверьте профиль и источники поиска", 5000)

    def _show_profile(self) -> None:
        QMessageBox.information(
            self,
            "Профиль",
            "ООО «КОРТЕРИС»\nCorteris Tender AI 1.3 Alpha",
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        """Stop the background work owned by the modern shell."""
        if self._close_complete:
            super().closeEvent(event)
            return

        tender_search = getattr(self, "_tender_search_ui_controller", None)
        shutdown_tender_search = getattr(tender_search, "shutdown", None)
        if callable(shutdown_tender_search) and not shutdown_tender_search():
            event.ignore()
            return

        self._close_started = True
        self.workspace.setEnabled(False)
        if not self.workflow_page.shutdown():
            event.ignore()
            return

        if not self._dashboard_shutdown:
            self.dashboard_controller.shutdown()
            self._dashboard_shutdown = True

        if not self._analytics_shutdown and self.analytics_controller is not None:
            if not self.analytics_controller.shutdown():
                event.ignore()
                return
            self._analytics_shutdown = True

        self._close_complete = True
        super().closeEvent(event)


__all__ = ["ModernMainWindow"]
