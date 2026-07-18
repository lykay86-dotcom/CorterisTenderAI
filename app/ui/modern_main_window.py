"""Modern application shell for Corteris Tender AI v1.3 Alpha."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMainWindow, QMessageBox

from app.repositories.business_metrics import (
    BusinessMetricsRepository,
    BusinessRecordKind,
)
from app.ui.controllers.dashboard_controller import DashboardController
from app.ui.navigation import (
    NavigationCause,
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
from app.ui.pages.tender_workspace_page import TenderWorkspacePage
from app.ui.theme.colors import ThemeName
from app.ui.theme.stylesheet import build_stylesheet
from app.ui.widgets.dashboard_layout import DashboardLayout

if TYPE_CHECKING:
    from app.core.ai.provider_selection import AiProviderSelectionService


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

        self.setObjectName("ModernMainWindow")
        self.setWindowTitle("Corteris Tender AI 1.3 Alpha")
        self.resize(1540, 940)
        self.setMinimumSize(1180, 720)

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

        self.quotes_page = BusinessWorkflowPage(
            repository=self.business_repository,
            initial_kind=BusinessRecordKind.PROPOSAL,
            theme=self._theme,
            parent=self.workspace.pages,
        )
        self.workspace.add_page(
            "quotes",
            "КП, сметы и проекты",
            self.quotes_page,
        )

        self.estimates_page = BusinessWorkflowPage(
            repository=self.business_repository,
            initial_kind=BusinessRecordKind.ESTIMATE,
            theme=self._theme,
            parent=self.workspace.pages,
        )
        self.workspace.add_page(
            "estimates",
            "Сметы и проекты",
            self.estimates_page,
        )

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

        for page in (self.quotes_page, self.estimates_page):
            page.tender_open_requested.connect(self._open_tender_from_dashboard)
            page.workflow_changed.connect(self._business_workflow_changed)

        self.apply_theme(self._theme)
        self.workspace.navigate(
            RouteRequest(
                RouteId.DASHBOARD,
                cause=NavigationCause.PROGRAMMATIC,
                record_history=False,
            )
        )
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

    def _register_navigation_destinations(self) -> None:
        """Bind canonical routes to the existing page and controller owners."""
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
            "quotes",
            lambda: self._workflow_route_context(self.quotes_page),
        )
        self.workspace.register_context_provider(
            "estimates",
            lambda: self._workflow_route_context(self.estimates_page),
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

    @staticmethod
    def _workflow_route_context(page: BusinessWorkflowPage) -> RouteContext:
        state = page.capture_navigation_state()
        return RouteContext(
            workflow_kind=state.kind or None,
            workflow_status=state.status or None,
            workflow_archive_mode=state.archive_mode or None,
            workflow_search=state.search_text or None,
            workflow_record_id=state.record_id,
        )

    def _activate_workflow(self, route_id: RouteId, context: RouteContext) -> bool:
        page = self.estimates_page if route_id is RouteId.WORKFLOW_ESTIMATES else self.quotes_page
        page.apply_navigation_state(
            WorkflowNavigationState(
                search_text=context.workflow_search or "",
                kind=context.workflow_kind or "",
                status=context.workflow_status or "",
                archive_mode=context.workflow_archive_mode
                or WorkflowNavigationState().archive_mode,
                record_id=context.workflow_record_id,
            )
        )
        return True

    def _activate_tender_route(self, context: RouteContext) -> bool:
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
        if context.tender_id is not None and not self.tender_workspace_page.open_tender(
            context.tender_id
        ):
            return False
        if context.settings_section is not None:
            return self.tender_workspace_page.select_settings_section(context.settings_section)
        if context.tender_section is not None:
            return self.tender_workspace_page.select_section(context.tender_section)
        return True

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
        """Synchronize both workflow views and Dashboard KPI."""
        sender = self.sender()
        for page in (self.quotes_page, self.estimates_page):
            if page is not sender:
                state = page.capture_navigation_state()
                page.refresh()
                page.apply_navigation_state(state)

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
            context=RouteContext(tender_id=tender_id),
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
        self.quotes_page.apply_theme(self._theme)
        self.estimates_page.apply_theme(self._theme)
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

    def closeEvent(self, event) -> None:
        """Stop the background work owned by the modern shell."""
        tender_search = getattr(self, "_tender_search_ui_controller", None)
        shutdown_tender_search = getattr(tender_search, "shutdown", None)
        if callable(shutdown_tender_search) and not shutdown_tender_search():
            event.ignore()
            return
        try:
            self.dashboard_controller.shutdown()
        finally:
            super().closeEvent(event)


__all__ = ["ModernMainWindow"]
