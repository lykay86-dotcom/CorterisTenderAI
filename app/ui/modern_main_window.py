"""Modern application shell for Corteris Tender AI v1.3 Alpha."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from app.repositories.business_metrics import (
    BusinessMetricsRepository,
    BusinessRecordKind,
)
from app.ui.controllers.dashboard_controller import DashboardController
from app.ui.pages.business_workflow_page import BusinessWorkflowPage
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

        self.workspace.add_page(
            "ai",
            "AI-анализ",
            self._placeholder("AI-анализ будет перенесён в новый интерфейс в следующих коммитах."),
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
        self.workspace.add_page(
            "documents",
            "Документы",
            self._placeholder("Единый центр документов находится в разработке."),
        )
        self.workspace.add_page(
            "clients",
            "Клиенты",
            self._placeholder("Карточки заказчиков и клиентов появятся позже."),
        )
        self.workspace.add_page(
            "analytics",
            "Аналитика",
            self._placeholder("Графики и аналитика будут добавлены в следующем спринте."),
        )
        self.workspace.add_page(
            "settings",
            "Настройки",
            self._placeholder("Настройки прежней версии доступны в разделе «Тендеры»."),
        )

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
        self.workspace.sidebar.select("dashboard")
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
        self.workspace.topbar.ai_clicked.connect(lambda: self.workspace.sidebar.select("ai"))
        self.workspace.topbar.notifications_clicked.connect(self._show_notifications)
        self.workspace.topbar.profile_clicked.connect(self._show_profile)

        self.dashboard_page.find_tenders_requested.connect(
            lambda: self.workspace.sidebar.select("tenders")
        )
        self.dashboard_page.create_proposal_requested.connect(
            lambda: self.workspace.sidebar.select("quotes")
        )
        self.dashboard_page.create_estimate_requested.connect(
            lambda: self.workspace.sidebar.select("estimates")
        )
        self.dashboard_page.analyze_documents_requested.connect(
            lambda: self.workspace.sidebar.select("ai")
        )

    def _business_workflow_changed(self) -> None:
        """Synchronize both workflow views and Dashboard KPI."""
        sender = self.sender()
        for page in (self.quotes_page, self.estimates_page):
            if page is not sender:
                page.refresh()

        self.dashboard_controller.refresh()
        self.statusBar().showMessage(
            "Бизнес-процессы и Dashboard обновлены",
            4000,
        )

    def _open_tender_from_dashboard(self, tender_id: str) -> None:
        """Open a Dashboard tender in the existing working module."""
        self.workspace.sidebar.select("tenders")
        if self.tender_workspace_page.open_tender(tender_id):
            self.statusBar().showMessage(
                f"Открыт тендер ID {tender_id}",
                5000,
            )

    def apply_theme(self, theme: ThemeName | str) -> None:
        """Apply and persist the selected UI theme."""
        self._theme = ThemeName(theme)
        self.setStyleSheet(build_stylesheet(self._theme.value))
        self.dashboard_page.set_theme(self._theme)
        self.quotes_page.apply_theme(self._theme)
        self.estimates_page.apply_theme(self._theme)
        self._settings.setValue("ui/theme", self._theme.value)

        self.workspace.topbar.theme_button.setText("☀" if self._theme == ThemeName.DARK else "🌙")
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

        self.workspace.sidebar.select("tenders")
        if self.tender_workspace_page.submit_unified_search_text(normalized):
            self.statusBar().showMessage(f"Поиск тендеров: {normalized}", 5000)
        else:
            self.tender_workspace_page.focus_unified_search()
            self.statusBar().showMessage("Проверьте профиль и источники поиска", 5000)

    def _show_notifications(self) -> None:
        QMessageBox.information(
            self,
            "Уведомления",
            "Новых уведомлений пока нет.",
        )

    def _show_profile(self) -> None:
        QMessageBox.information(
            self,
            "Профиль",
            "ООО «КОРТЕРИС»\nCorteris Tender AI 1.3 Alpha",
        )

    def _placeholder(self, text: str) -> QWidget:
        page = QWidget(self.workspace.pages)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 32, 32, 32)

        title = QLabel(text, page)
        title.setWordWrap(True)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setObjectName("PlaceholderText")

        layout.addStretch()
        layout.addWidget(title)
        layout.addStretch()
        return page

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
