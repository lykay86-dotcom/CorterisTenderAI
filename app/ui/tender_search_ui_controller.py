"""Qt integration controller for tender-search profiles and results."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import (
    QObject,
    QRunnable,
    QThreadPool,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow,
    QMenu,
    QToolBar,
    QWidget,
)

from app.tenders.collector.cancellation import CollectorCancellationToken
from app.tenders.collector.company_capability import (
    CompanyCapabilityProfileRepository,
)
from app.tenders.collector.models import CollectorRunResult
from app.tenders.collector.participation_score import (
    CorterisParticipationScore,
)
from app.tenders.collector.participation_score_service import (
    CorterisParticipationScoreService,
)
from app.tenders.collector.progress import CollectorProgressEvent
from app.tenders.collector.provider_control import (
    CollectorProviderManager,
    ProviderDisplayState,
)
from app.tenders.providers.mos_supplier_config import (
    MOS_SUPPLIER_KEYRING_SECRET,
    MosSupplierApiConfig,
)
from app.security.secrets import load_secret, save_secret
from app.tenders.collector.run_session import CollectorRunSession
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.collector.verification_review import (
    TenderVerificationReviewService,
)
from app.tenders.full_analysis import (
    FullAnalysisProgress,
    TenderFullAnalysisResult,
    TenderFullAnalysisService,
)
from app.tenders.document_storage import (
    TenderDocumentDownloadResult,
    TenderDocumentDownloadService,
)
from app.tenders.models import UnifiedTender
from app.tenders.corteris_filter import (
    CorterisTenderClassifier,
    CorterisTenderFilter,
)
from app.tenders.matching_catalog import (
    MatchingCatalog,
    MatchingCatalogRepository,
)
from app.tenders.requirement_analysis import (
    TenderRequirementAnalysis,
    TenderRequirementAnalysisService,
)
from app.tenders.search_profile_runner import (
    TenderSearchProfileRun,
    TenderSearchProfileRunner,
)
from app.tenders.tender_registry import tender_registry_key
from app.tenders.search_runtime import (
    TenderSearchRuntime,
    create_tender_search_runtime,
)
from app.ui.tender_collector_dialog import TenderCollectorDialog
from app.ui.company_capability_dialog import CompanyCapabilityDialog
from app.ui.matching_catalog_dialog import MatchingCatalogDialog
from app.ui.commercial_estimator_dialog import CommercialEstimatorDialog
from app.tenders.commercial_estimator import CommercialEstimateRepository
from app.tenders.collector.aggregator_discovery import (
    AggregatorDiscoveryRepository,
)
from app.ui.aggregator_discovery_dialog import AggregatorDiscoveryDialog
from app.ui.tender_collector_scheduler_controller import (
    TenderCollectorSchedulerUiController,
)
from app.ui.tender_documents_dialog import TenderDocumentsDialog
from app.ui.tender_full_analysis_dialog import TenderFullAnalysisDialog
from app.ui.tender_participation_score_dialog import (
    TenderParticipationScoreDialog,
)
from app.ui.tender_provider_manager_dialog import (
    TenderProviderManagerDialog,
)
from app.ui.provider_credentials_dialog import ProviderCredentialsDialog
from app.ui.tender_registry_dialog import TenderRegistryDialog
from app.ui.tender_verification_dialog import TenderVerificationDialog
from app.ui.tender_requirement_analysis_dialog import (
    TenderRequirementAnalysisDialog,
)
from app.ui.tender_search_profiles_dialog import (
    TenderSearchProfilesDialog,
)
from app.ui.tender_search_results_dialog import (
    TenderSearchResultsDialog,
)
from app.ui.theme.colors import ThemeName


class _ThreadPoolLike(Protocol):
    def start(self, runnable: QRunnable) -> None: ...


class _SearchWorkerSignals(QObject):
    succeeded = Signal(str, object)
    failed = Signal(str, str, str)


class _TenderSearchWorker(QRunnable):
    def __init__(
        self,
        runner: TenderSearchProfileRunner,
        profile_id: str,
    ) -> None:
        super().__init__()
        self.runner = runner
        self.profile_id = profile_id
        self.signals = _SearchWorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        try:
            result = self.runner.run(self.profile_id)
        except Exception as exc:
            self.signals.failed.emit(
                self.profile_id,
                type(exc).__name__,
                str(exc),
            )
            return
        self.signals.succeeded.emit(self.profile_id, result)


class _FullAnalysisWorkerSignals(QObject):
    progress = Signal(str, object)
    succeeded = Signal(str, object)
    failed = Signal(str, str, str)


class _TenderFullAnalysisWorker(QRunnable):
    def __init__(
        self,
        service: TenderFullAnalysisService,
        registry_key: str,
    ) -> None:
        super().__init__()
        self.service = service
        self.registry_key = registry_key.strip()
        self.cancellation_token = CollectorCancellationToken()
        self.signals = _FullAnalysisWorkerSignals()
        self.setAutoDelete(True)

    def cancel(self) -> bool:
        return self.cancellation_token.cancel("Полный анализ остановлен пользователем.")

    @Slot()
    def run(self) -> None:
        try:
            result = self.service.run(
                self.registry_key,
                cancellation_token=self.cancellation_token,
                progress_callback=lambda event: self.signals.progress.emit(
                    self.registry_key,
                    event,
                ),
            )
        except Exception as exc:
            self.signals.failed.emit(
                self.registry_key,
                type(exc).__name__,
                str(exc),
            )
            return
        self.signals.succeeded.emit(self.registry_key, result)


class _DocumentWorkerSignals(QObject):
    succeeded = Signal(str, object, object)
    failed = Signal(str, object, str, str)


class _TenderDocumentWorker(QRunnable):
    def __init__(
        self,
        service: TenderDocumentDownloadService,
        tender: UnifiedTender,
        *,
        force: bool,
    ) -> None:
        super().__init__()
        self.service = service
        self.tender = tender
        self.force = bool(force)
        self.registry_key = tender_registry_key(tender)
        self.signals = _DocumentWorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        try:
            result = self.service.download_for_tender(
                self.tender,
                force=self.force,
            )
        except Exception as exc:
            self.signals.failed.emit(
                self.registry_key,
                self.tender,
                type(exc).__name__,
                str(exc),
            )
            return
        self.signals.succeeded.emit(
            self.registry_key,
            self.tender,
            result,
        )


class _AnalysisWorkerSignals(QObject):
    succeeded = Signal(str, object)
    failed = Signal(str, str, str)


class _TenderRequirementAnalysisWorker(QRunnable):
    def __init__(
        self,
        service: TenderRequirementAnalysisService,
        registry_key: str,
        *,
        force_extraction: bool,
    ) -> None:
        super().__init__()
        self.service = service
        self.registry_key = registry_key.strip()
        self.force_extraction = bool(force_extraction)
        self.signals = _AnalysisWorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        try:
            result = self.service.analyze(
                self.registry_key,
                force_extraction=self.force_extraction,
            )
        except Exception as exc:
            self.signals.failed.emit(
                self.registry_key,
                type(exc).__name__,
                str(exc),
            )
            return
        self.signals.succeeded.emit(self.registry_key, result)


class _ParticipationScoreWorkerSignals(QObject):
    succeeded = Signal(str, object)
    failed = Signal(str, str, str)


class _ParticipationScoreWorker(QRunnable):
    def __init__(
        self,
        service: CorterisParticipationScoreService,
        registry_key: str,
    ) -> None:
        super().__init__()
        self.service = service
        self.registry_key = registry_key.strip()
        self.signals = _ParticipationScoreWorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        try:
            result = self.service.evaluate(
                self.registry_key,
                persist=True,
            )
        except Exception as exc:
            self.signals.failed.emit(
                self.registry_key,
                type(exc).__name__,
                str(exc),
            )
            return
        self.signals.succeeded.emit(
            self.registry_key,
            result,
        )


class _CollectorRunWorkerSignals(QObject):
    progress = Signal(object)
    succeeded = Signal(object)
    failed = Signal(str, str)


class _CollectorRunWorker(QRunnable):
    def __init__(
        self,
        session: CollectorRunSession,
        query: object,
        provider_ids: tuple[str, ...],
    ) -> None:
        super().__init__()
        self.session = session
        self.query = query
        self.provider_ids = provider_ids
        self.cancellation_token = CollectorCancellationToken()
        self.signals = _CollectorRunWorkerSignals()
        self.setAutoDelete(True)

    def cancel(self) -> bool:
        return self.cancellation_token.cancel("Остановлено пользователем из интерфейса.")

    @Slot()
    def run(self) -> None:
        async def execute() -> object:
            return await self.session.run(
                self.query,
                provider_ids=self.provider_ids,
                cancellation_token=self.cancellation_token,
                progress_callback=self.signals.progress.emit,
            )

        try:
            result = asyncio.run(execute())
        except Exception as exc:
            self.signals.failed.emit(
                type(exc).__name__,
                str(exc),
            )
            return
        self.signals.succeeded.emit(result)


class _ProviderCheckWorkerSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(str, str)


class _ProviderCheckWorker(QRunnable):
    def __init__(
        self,
        manager: CollectorProviderManager,
        provider_ids: tuple[str, ...],
    ) -> None:
        super().__init__()
        self.manager = manager
        self.provider_ids = provider_ids
        self.signals = _ProviderCheckWorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        try:
            states = asyncio.run(self.manager.check_providers(self.provider_ids))
        except Exception as exc:
            self.signals.failed.emit(
                type(exc).__name__,
                str(exc),
            )
            return
        self.signals.succeeded.emit(states)


class TenderSearchUiController(QObject):
    """Install tender search in the main window and run it off-thread."""

    search_started = Signal(str)
    search_finished = Signal(str, object)
    search_failed = Signal(str, str)
    document_download_started = Signal(str)
    document_download_finished = Signal(str, object)
    document_download_failed = Signal(str, str)
    analysis_started = Signal(str)
    analysis_finished = Signal(str, object)
    analysis_failed = Signal(str, str)
    collector_started = Signal(str)
    collector_finished = Signal(object)
    collector_failed = Signal(str)
    score_started = Signal(str)
    score_finished = Signal(str, object)
    score_failed = Signal(str, str)
    full_analysis_started = Signal(str)
    full_analysis_finished = Signal(str, object)
    full_analysis_failed = Signal(str, str)

    def __init__(
        self,
        data_directory: str | Path,
        *,
        runtime: TenderSearchRuntime | None = None,
        provider_manager: CollectorProviderManager | None = None,
        collector_session: CollectorRunSession | None = None,
        verification_review_service: (TenderVerificationReviewService | None) = None,
        theme: ThemeName | str = ThemeName.DARK,
        thread_pool: _ThreadPoolLike | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self.data_directory = Path(data_directory).expanduser()
        self.runtime = runtime or create_tender_search_runtime(self.data_directory)
        self.provider_manager = provider_manager or CollectorProviderManager(self.data_directory)
        self.collector_session = collector_session or CollectorRunSession(self.data_directory)
        registry_path = (
            self.runtime.tender_registry.path
            if self.runtime.tender_registry is not None
            else self.data_directory / "tender_registry.sqlite3"
        )
        self.verification_repository = CollectorStateRepository(registry_path)
        self.verification_review_service = (
            verification_review_service
            or TenderVerificationReviewService(self.verification_repository)
        )
        try:
            self._theme = ThemeName(theme)
        except (TypeError, ValueError, AttributeError):
            self._theme = ThemeName.DARK
        self._thread_pool = thread_pool or QThreadPool.globalInstance()
        self._profiles_dialog: TenderSearchProfilesDialog | None = None
        self._registry_dialog: TenderRegistryDialog | None = None
        self._provider_dialog: TenderProviderManagerDialog | None = None
        self._company_capability_dialog: CompanyCapabilityDialog | None = None
        self._matching_catalog_dialog: MatchingCatalogDialog | None = None
        self._commercial_estimate_dialogs: dict[str, CommercialEstimatorDialog] = {}
        self._aggregator_discovery_dialog: AggregatorDiscoveryDialog | None = None
        self._provider_check_worker: _ProviderCheckWorker | None = None
        self._provider_check_ids: tuple[str, ...] = ()
        self._collector_dialog: TenderCollectorDialog | None = None
        self._collector_worker: _CollectorRunWorker | None = None
        self._collector_profile_id = ""
        self._result_dialogs: list[TenderSearchResultsDialog] = []
        self._document_dialogs: dict[str, TenderDocumentsDialog] = {}
        self._active_workers: dict[str, _TenderSearchWorker] = {}
        self._document_workers: dict[
            str,
            _TenderDocumentWorker,
        ] = {}
        self._analysis_dialogs: dict[
            str,
            TenderRequirementAnalysisDialog,
        ] = {}
        self._analysis_workers: dict[
            str,
            _TenderRequirementAnalysisWorker,
        ] = {}
        self._score_dialogs: dict[
            str,
            TenderParticipationScoreDialog,
        ] = {}
        self._score_workers: dict[
            str,
            _ParticipationScoreWorker,
        ] = {}
        self._full_analysis_dialogs: dict[
            str,
            TenderFullAnalysisDialog,
        ] = {}
        self._full_analysis_workers: dict[
            str,
            _TenderFullAnalysisWorker,
        ] = {}
        self._verification_dialogs: dict[str, TenderVerificationDialog] = {}
        # PySide6 can release a QMenu wrapper created by QMenuBar.addMenu()
        # when no Python-side strong reference is retained, especially with
        # the offscreen test platform. Keep the menu alive with the controller.
        self._tender_menu: QMenu | None = None
        self._tender_toolbar: QToolBar | None = None

        self.action = QAction(
            "Профили и поиск тендеров…",
            self,
        )
        self.action.setObjectName("actionTenderSearchProfiles")
        self.action.setShortcut(QKeySequence("Ctrl+Shift+F"))
        self.action.setStatusTip("Открыть профили и запустить поиск тендеров")
        self.action.triggered.connect(self.open_profiles_dialog)

        self.registry_action = QAction(
            "Реестр найденных тендеров…",
            self,
        )
        self.registry_action.setObjectName("actionTenderRegistry")
        self.registry_action.setShortcut(QKeySequence("Ctrl+Shift+R"))
        self.registry_action.setStatusTip("Открыть локальный реестр найденных тендеров")
        self.registry_action.setEnabled(self.runtime.tender_registry is not None)
        self.registry_action.triggered.connect(self.open_registry_dialog)

        self.providers_action = QAction(
            "Источники тендеров…",
            self,
        )
        self.providers_action.setObjectName("actionTenderProviders")
        self.providers_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.providers_action.setStatusTip("Настроить источники и проверить подключения")
        self.providers_action.triggered.connect(self.open_provider_manager_dialog)

        self.collector_action = QAction(
            "Запустить сборщик тендеров…",
            self,
        )
        self.collector_action.setObjectName("actionTenderCollector")
        self.collector_action.setShortcut(QKeySequence("Ctrl+Shift+C"))
        self.collector_action.setStatusTip("Запустить автоматический сбор по включённым источникам")
        self.collector_action.triggered.connect(self.open_collector_dialog)

        self.company_capability_action = QAction(
            "Возможности компании…",
            self,
        )
        self.company_capability_action.setObjectName("actionCompanyCapabilityProfile")
        self.company_capability_action.setStatusTip(
            "Настроить подтверждённые возможности компании для рейтинга"
        )
        self.company_capability_action.triggered.connect(self.open_company_capability_dialog)

        self.matching_catalog_action = QAction(
            "Каталог сопоставления…",
            self,
        )
        self.matching_catalog_action.setObjectName("actionMatchingCatalog")
        self.matching_catalog_action.setStatusTip(
            "Настроить ключевые слова, синонимы, ОКПД2, исключения и веса"
        )
        self.matching_catalog_action.triggered.connect(self.open_matching_catalog_dialog)

        self.aggregator_discovery_action = QAction(
            "Очередь официальной проверки…",
            self,
        )
        self.aggregator_discovery_action.setObjectName("actionAggregatorDiscoveryQueue")
        self.aggregator_discovery_action.setStatusTip(
            "Показать обнаружения агрегаторов, ожидающие официальной проверки"
        )
        self.aggregator_discovery_action.triggered.connect(self.open_aggregator_discovery_dialog)

        self.scheduler_ui_controller = TenderCollectorSchedulerUiController(
            self.data_directory,
            profile_repository=self.runtime.repository,
            provider_manager=self.provider_manager,
            start_collector=self.try_start_collector,
            is_collector_busy=(lambda: self._collector_worker is not None),
            collector_finished_signal=self.collector_finished,
            collector_failed_signal=self.collector_failed,
            theme=self._theme,
            parent=self,
        )

    @property
    def profiles_dialog(self) -> TenderSearchProfilesDialog | None:
        return self._profiles_dialog

    @property
    def registry_dialog(self) -> TenderRegistryDialog | None:
        return self._registry_dialog

    @property
    def provider_dialog(
        self,
    ) -> TenderProviderManagerDialog | None:
        return self._provider_dialog

    @property
    def collector_dialog(self) -> TenderCollectorDialog | None:
        return self._collector_dialog

    @property
    def result_dialogs(self) -> tuple[TenderSearchResultsDialog, ...]:
        return tuple(self._result_dialogs)

    @property
    def document_dialogs(self) -> tuple[TenderDocumentsDialog, ...]:
        return tuple(self._document_dialogs.values())

    @property
    def analysis_dialogs(
        self,
    ) -> tuple[TenderRequirementAnalysisDialog, ...]:
        return tuple(self._analysis_dialogs.values())

    @property
    def score_dialogs(
        self,
    ) -> tuple[TenderParticipationScoreDialog, ...]:
        return tuple(self._score_dialogs.values())

    def install_on_main_window(
        self,
        main_window: QWidget,
    ) -> QAction:
        """Install a visible menu action or at least a window shortcut."""

        if isinstance(main_window, QMainWindow):
            menu = self._find_or_create_tender_menu(main_window)
            self._tender_menu = menu
            # Retain the wrapper on the window too. This protects the menu
            # lifetime even when the controller is reconstructed or inspected
            # through temporary action.menu() wrappers in PySide6 tests.
            setattr(main_window, "_tender_search_menu", menu)
            if self.action not in menu.actions():
                menu.addAction(self.action)
            if self.registry_action not in menu.actions():
                menu.addAction(self.registry_action)
            if self.providers_action not in menu.actions():
                menu.addAction(self.providers_action)
            if self.collector_action not in menu.actions():
                menu.addAction(self.collector_action)
            if self.company_capability_action not in menu.actions():
                menu.addAction(self.company_capability_action)
            if self.matching_catalog_action not in menu.actions():
                menu.addAction(self.matching_catalog_action)
            if self.aggregator_discovery_action not in menu.actions():
                menu.addAction(self.aggregator_discovery_action)

            toolbar = self._find_or_create_tender_toolbar(main_window)
            self._tender_toolbar = toolbar
            setattr(
                main_window,
                "_tender_search_toolbar",
                toolbar,
            )
            if self.action not in toolbar.actions():
                toolbar.addAction(self.action)
            if self.registry_action not in toolbar.actions():
                toolbar.addAction(self.registry_action)
            if self.providers_action not in toolbar.actions():
                toolbar.addAction(self.providers_action)
            if self.collector_action not in toolbar.actions():
                toolbar.addAction(self.collector_action)
            if self.company_capability_action not in toolbar.actions():
                toolbar.addAction(self.company_capability_action)
            if self.matching_catalog_action not in toolbar.actions():
                toolbar.addAction(self.matching_catalog_action)
            if self.aggregator_discovery_action not in toolbar.actions():
                toolbar.addAction(self.aggregator_discovery_action)
            toolbar.setVisible(True)
        else:
            # Fallback for a QWidget-based shell: shortcuts still work.
            if self.action not in main_window.actions():
                main_window.addAction(self.action)
            if self.registry_action not in main_window.actions():
                main_window.addAction(self.registry_action)
            if self.providers_action not in main_window.actions():
                main_window.addAction(self.providers_action)
            if self.collector_action not in main_window.actions():
                main_window.addAction(self.collector_action)
            if self.company_capability_action not in main_window.actions():
                main_window.addAction(self.company_capability_action)
            if self.matching_catalog_action not in main_window.actions():
                main_window.addAction(self.matching_catalog_action)
            if self.aggregator_discovery_action not in main_window.actions():
                main_window.addAction(self.aggregator_discovery_action)

        self.scheduler_ui_controller.install_on_main_window(
            main_window,
            menu=self._tender_menu,
            toolbar=self._tender_toolbar,
        )

        # Keep the controller alive for the whole window lifetime.
        setattr(
            main_window,
            "_tender_search_ui_controller",
            self,
        )
        return self.action

    @Slot()
    def open_profiles_dialog(self) -> None:
        parent = self.parent()
        parent_widget = parent if isinstance(parent, QWidget) else None

        if self._profiles_dialog is None:
            self._profiles_dialog = TenderSearchProfilesDialog(
                self.runtime.repository,
                theme=self._theme,
                parent=parent_widget,
            )
            self._profiles_dialog.profile_run_requested.connect(self.run_profile)

        self._profiles_dialog.refresh_profiles()
        self._profiles_dialog.open()
        self._profiles_dialog.raise_()
        self._profiles_dialog.activateWindow()

    @Slot()
    def open_company_capability_dialog(self) -> None:
        parent = self.parent()
        parent_widget = parent if isinstance(parent, QWidget) else None
        if self._company_capability_dialog is None:
            self._company_capability_dialog = CompanyCapabilityDialog(
                CompanyCapabilityProfileRepository(
                    self.data_directory / "company_capability_profile.json"
                ),
                parent=parent_widget,
            )
        self._company_capability_dialog.load_profile()
        self._company_capability_dialog.open()
        self._company_capability_dialog.raise_()
        self._company_capability_dialog.activateWindow()

    @Slot()
    def open_matching_catalog_dialog(self) -> None:
        parent = self.parent()
        parent_widget = parent if isinstance(parent, QWidget) else None
        repository = self.runtime.matching_catalog_repository or MatchingCatalogRepository(
            self.data_directory / "tender_registry.sqlite3"
        )
        if self._matching_catalog_dialog is None:
            self._matching_catalog_dialog = MatchingCatalogDialog(
                repository,
                parent=parent_widget,
            )
            self._matching_catalog_dialog.catalog_saved.connect(self._apply_matching_catalog)
        self._matching_catalog_dialog.load_catalog()
        self._matching_catalog_dialog.open()
        self._matching_catalog_dialog.raise_()
        self._matching_catalog_dialog.activateWindow()

    @Slot()
    def open_aggregator_discovery_dialog(self) -> None:
        parent = self.parent()
        parent_widget = parent if isinstance(parent, QWidget) else None
        repository = self.runtime.aggregator_discovery_repository or AggregatorDiscoveryRepository(
            self.data_directory / "tender_registry.sqlite3"
        )
        if self._aggregator_discovery_dialog is None:
            self._aggregator_discovery_dialog = AggregatorDiscoveryDialog(
                repository,
                parent=parent_widget,
            )
        self._aggregator_discovery_dialog.refresh()
        self._aggregator_discovery_dialog.open()
        self._aggregator_discovery_dialog.raise_()
        self._aggregator_discovery_dialog.activateWindow()

    @Slot(object)
    def _apply_matching_catalog(self, catalog: MatchingCatalog) -> None:
        self.runtime.search_service.tender_filter = CorterisTenderFilter(
            CorterisTenderClassifier(catalog.to_search_profile())
        )

    @Slot()
    def open_registry_dialog(self) -> None:
        repository = self.runtime.tender_registry
        if repository is None:
            self._set_profiles_status("Локальный реестр тендеров недоступен.")
            return

        parent = self.parent()
        parent_widget = parent if isinstance(parent, QWidget) else None
        if self._registry_dialog is None:
            self._registry_dialog = TenderRegistryDialog(
                repository,
                theme=self._theme,
                parent=parent_widget,
            )
            self._registry_dialog.profiles_requested.connect(self.open_profiles_dialog)
            self._registry_dialog.documents_requested.connect(self.open_registry_documents)
            self._registry_dialog.analysis_requested.connect(self.open_requirement_analysis)
            self._registry_dialog.score_requested.connect(self.open_participation_score)
            self._registry_dialog.full_analysis_requested.connect(self.open_full_analysis)
            self._registry_dialog.commercial_estimate_requested.connect(
                self.open_commercial_estimator
            )
            self._registry_dialog.verification_requested.connect(self.open_verification_details)

        self._registry_dialog.refresh_records()
        self._registry_dialog.open()
        self._registry_dialog.raise_()
        self._registry_dialog.activateWindow()

    @Slot()
    def open_collector_dialog(self) -> None:
        parent = self.parent()
        parent_widget = parent if isinstance(parent, QWidget) else None
        if self._collector_dialog is None:
            self._collector_dialog = TenderCollectorDialog(
                theme=self._theme,
                parent=parent_widget,
            )
            self._collector_dialog.start_requested.connect(self.start_collector)
            self._collector_dialog.stop_requested.connect(self.stop_collector)
            self._collector_dialog.sources_requested.connect(self.open_provider_manager_dialog)
            self._collector_dialog.registry_requested.connect(self.open_registry_dialog)

        self.refresh_collector_configuration()
        self._collector_dialog.open()
        self._collector_dialog.raise_()
        self._collector_dialog.activateWindow()

    @Slot()
    def refresh_collector_configuration(self) -> None:
        if self._collector_dialog is None or self._collector_dialog.running:
            return
        profiles = self.runtime.repository.list_profiles(include_disabled=False)
        self._collector_dialog.set_profiles(
            profiles,
            select_id=self._collector_profile_id,
        )
        self._collector_dialog.set_provider_states(
            self.provider_manager.states(),
            preserve_selection=True,
        )

    @Slot(str, object)
    def start_collector(
        self,
        profile_id: str,
        provider_ids: object,
    ) -> None:
        self.try_start_collector(
            profile_id,
            provider_ids,
        )

    def try_start_collector(
        self,
        profile_id: str,
        provider_ids: object,
    ) -> bool:
        """Start one collector run and report whether it was accepted."""

        normalized = profile_id.strip().casefold()
        if not normalized:
            return False
        if self._collector_worker is not None:
            if self._collector_dialog is not None:
                self._collector_dialog.set_status("Сборщик уже выполняется.")
            return False

        try:
            profile = self.runtime.repository.get(normalized)
        except Exception as exc:
            if self._collector_dialog is not None:
                self._collector_dialog.set_error(f"Не удалось загрузить профиль: {exc}")
            return False
        if not profile.enabled:
            if self._collector_dialog is not None:
                self._collector_dialog.set_error("Выбранный профиль отключён.")
            return False

        selected = tuple(
            dict.fromkeys(
                str(item).strip().casefold() for item in (provider_ids or ()) if str(item).strip()
            )
        )
        enabled = set(self.provider_manager.enabled_provider_ids())
        selected = tuple(provider_id for provider_id in selected if provider_id in enabled)
        if not selected:
            if self._collector_dialog is not None:
                self._collector_dialog.set_error("Нет включённых источников для запуска.")
            return False

        worker = _CollectorRunWorker(
            self.collector_session,
            profile.to_search_query(),
            selected,
        )
        worker.signals.progress.connect(self._on_collector_progress)
        worker.signals.succeeded.connect(self._on_collector_succeeded)
        worker.signals.failed.connect(self._on_collector_failed)
        self._collector_worker = worker
        self._collector_profile_id = normalized

        if self._collector_dialog is not None:
            self._collector_dialog.begin_run(
                profile.name,
                selected,
            )
        self.collector_started.emit(normalized)
        self._thread_pool.start(worker)
        return True

    @Slot()
    def stop_collector(self) -> None:
        worker = self._collector_worker
        if worker is None:
            return
        worker.cancel()
        if self._collector_dialog is not None:
            self._collector_dialog.mark_cancel_requested()

    @Slot(object)
    def _on_collector_progress(self, event: object) -> None:
        if self._collector_dialog is not None and isinstance(event, CollectorProgressEvent):
            self._collector_dialog.apply_progress(event)

    @Slot(object)
    def _on_collector_succeeded(self, result: object) -> None:
        self._collector_worker = None
        if not isinstance(result, CollectorRunResult):
            self._on_collector_failed(
                "TypeError",
                "Коллектор вернул неподдерживаемый результат.",
            )
            return
        if self._collector_dialog is not None:
            self._collector_dialog.set_result(result)
        if self._registry_dialog is not None:
            self._registry_dialog.refresh_records()
        self.collector_finished.emit(result)

    @Slot(str, str)
    def _on_collector_failed(
        self,
        error_type: str,
        message: str,
    ) -> None:
        self._collector_worker = None
        rendered = f"{error_type}: {message}"
        if self._collector_dialog is not None:
            self._collector_dialog.set_error(f"Сбор завершился ошибкой: {rendered}")
        self.collector_failed.emit(rendered)

    @Slot()
    def open_provider_manager_dialog(self) -> None:
        parent = self.parent()
        parent_widget = parent if isinstance(parent, QWidget) else None
        if self._provider_dialog is None:
            self._provider_dialog = TenderProviderManagerDialog(
                self.provider_manager.states(),
                theme=self._theme,
                parent=parent_widget,
            )
            self._provider_dialog.provider_enabled_changed.connect(self.set_provider_enabled)
            self._provider_dialog.provider_check_requested.connect(self.check_provider_connection)
            self._provider_dialog.provider_configuration_requested.connect(
                self.configure_provider_credentials
            )
            self._provider_dialog.check_all_requested.connect(self.check_all_provider_connections)
            self._provider_dialog.refresh_button.clicked.connect(self.refresh_provider_states)

        self.refresh_provider_states()
        self._provider_dialog.open()
        self._provider_dialog.raise_()
        self._provider_dialog.activateWindow()

    @Slot()
    def refresh_provider_states(self) -> None:
        states = self.provider_manager.states()
        if self._provider_dialog is not None:
            self._provider_dialog.set_states(states)
        if self._collector_dialog is not None and not self._collector_dialog.running:
            self._collector_dialog.set_provider_states(
                states,
                preserve_selection=True,
            )

    @Slot(str, bool)
    def set_provider_enabled(
        self,
        provider_id: str,
        enabled: bool,
    ) -> None:
        try:
            self.provider_manager.set_enabled(
                provider_id,
                enabled,
            )
        except Exception as exc:
            if self._provider_dialog is not None:
                self._provider_dialog.set_status(
                    f"Не удалось сохранить настройку: {exc}",
                    error=True,
                )
            return
        self.refresh_provider_states()
        if self._provider_dialog is not None:
            self._provider_dialog.set_status(
                "Источник включён." if enabled else "Источник отключён."
            )

    @Slot(str)
    def configure_provider_credentials(self, provider_id: str) -> None:
        if provider_id.strip().casefold() != "mos_supplier":
            if self._provider_dialog is not None:
                self._provider_dialog.set_status(
                    "Настройка API пока доступна для Портала поставщиков."
                )
            return

        state = next(
            (item for item in self.provider_manager.states() if item.provider_id == "mos_supplier"),
            None,
        )
        parent = self._provider_dialog
        dialog = ProviderCredentialsDialog(
            "mos_supplier",
            state.display_name if state is not None else "Портал поставщиков",
            configured=MosSupplierApiConfig.from_environment().configured,
            parent=parent,
        )
        if dialog.exec() != ProviderCredentialsDialog.DialogCode.Accepted:
            return
        try:
            save_secret(MOS_SUPPLIER_KEYRING_SECRET, dialog.token)
            saved_token = load_secret(MOS_SUPPLIER_KEYRING_SECRET)
        except Exception as exc:
            if self._provider_dialog is not None:
                self._provider_dialog.set_status(
                    f"Не удалось сохранить API-ключ: {type(exc).__name__}",
                    error=True,
                )
            return
        if saved_token != dialog.token:
            if self._provider_dialog is not None:
                self._provider_dialog.set_status(
                    "Хранилище Windows не подтвердило сохранение API-ключа.",
                    error=True,
                )
            return

        self.refresh_provider_states()
        if self._provider_dialog is not None:
            self._provider_dialog.set_status("API-ключ сохранён в защищённом хранилище Windows.")

    @Slot(str)
    def check_provider_connection(
        self,
        provider_id: str,
    ) -> None:
        self._start_provider_checks((provider_id,))

    @Slot()
    def check_all_provider_connections(self) -> None:
        self._start_provider_checks(self.provider_manager.enabled_provider_ids())

    def _start_provider_checks(
        self,
        provider_ids: tuple[str, ...],
    ) -> None:
        normalized = tuple(
            dict.fromkeys(item.strip().casefold() for item in provider_ids if item.strip())
        )
        if not normalized:
            if self._provider_dialog is not None:
                self._provider_dialog.set_status("Нет включённых источников для проверки.")
            return
        if self._provider_check_worker is not None:
            if self._provider_dialog is not None:
                self._provider_dialog.set_status("Проверка источников уже выполняется.")
            return

        worker = _ProviderCheckWorker(
            self.provider_manager,
            normalized,
        )
        worker.signals.succeeded.connect(self._on_provider_checks_succeeded)
        worker.signals.failed.connect(self._on_provider_checks_failed)
        self._provider_check_worker = worker
        self._provider_check_ids = normalized

        if self._provider_dialog is not None:
            self._provider_dialog.set_checking(
                normalized,
                True,
            )
            self._provider_dialog.set_status("Проверка подключений выполняется в фоне…")
        self._thread_pool.start(worker)

    @Slot(object)
    def _on_provider_checks_succeeded(
        self,
        states: object,
    ) -> None:
        checked = self._provider_check_ids
        self._provider_check_worker = None
        self._provider_check_ids = ()
        if self._provider_dialog is not None:
            self._provider_dialog.set_checking(
                checked,
                False,
            )
            if isinstance(states, tuple) and all(
                isinstance(item, ProviderDisplayState) for item in states
            ):
                self._provider_dialog.set_states(states)
            else:
                self.refresh_provider_states()
            self._provider_dialog.set_status("Проверка источников завершена.")

    @Slot(str, str)
    def _on_provider_checks_failed(
        self,
        error_type: str,
        message: str,
    ) -> None:
        checked = self._provider_check_ids
        self._provider_check_worker = None
        self._provider_check_ids = ()
        if self._provider_dialog is not None:
            self._provider_dialog.set_checking(
                checked,
                False,
            )
            self._provider_dialog.set_status(
                (f"Проверка источников завершилась ошибкой: {error_type}: {message}"),
                error=True,
            )
            self.refresh_provider_states()

    @Slot(str)
    def run_profile(self, profile_id: str) -> None:
        normalized = profile_id.strip().casefold()
        if not normalized:
            return

        if normalized in self._active_workers:
            self._set_profiles_status("Этот профиль уже выполняется. Дождитесь завершения.")
            return

        worker = _TenderSearchWorker(
            self.runtime.runner,
            normalized,
        )
        worker.signals.succeeded.connect(self._on_search_succeeded)
        worker.signals.failed.connect(self._on_search_failed)
        self._active_workers[normalized] = worker

        if self._profiles_dialog is not None:
            self._profiles_dialog.set_search_busy(
                True,
                profile_id=normalized,
            )

        self.search_started.emit(normalized)
        self._thread_pool.start(worker)

    @Slot(str, object)
    def _on_search_succeeded(
        self,
        profile_id: str,
        run: object,
    ) -> None:
        self._active_workers.pop(profile_id, None)
        if self._profiles_dialog is not None:
            self._profiles_dialog.set_search_busy(False)
            self._profiles_dialog.set_status("Поиск завершён. Открыта таблица результатов.")
            self._profiles_dialog.hide()

        if not isinstance(run, TenderSearchProfileRun):
            self._on_search_failed(
                profile_id,
                "TypeError",
                "Поисковый сервис вернул неподдерживаемый результат.",
            )
            return

        parent = self.parent()
        parent_widget = parent if isinstance(parent, QWidget) else None
        dialog = TenderSearchResultsDialog(
            run,
            theme=self._theme,
            parent=parent_widget,
        )
        dialog.rerun_requested.connect(self.run_profile)
        dialog.profiles_requested.connect(self.open_profiles_dialog)
        dialog.documents_requested.connect(self.open_tender_documents)
        dialog.full_analysis_requested.connect(
            lambda tender: self.open_full_analysis(tender_registry_key(tender))
        )
        dialog.finished.connect(lambda _result, current=dialog: self._forget_result_dialog(current))
        self._result_dialogs.append(dialog)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

        if self._registry_dialog is not None:
            self._registry_dialog.refresh_records()

        self.search_finished.emit(profile_id, run)

    @Slot(str)
    def open_registry_documents(self, registry_key: str) -> None:
        repository = self.runtime.tender_registry
        if repository is None:
            self._set_document_status("Локальный реестр тендеров недоступен.")
            return

        tender = repository.get_tender(registry_key)
        if tender is None:
            self._set_document_status("Не удалось восстановить карточку закупки из реестра.")
            return
        self.open_tender_documents(tender)

    @Slot(object)
    def open_tender_documents(self, tender: object) -> None:
        if not isinstance(tender, UnifiedTender):
            self._set_document_status("Выбрана неподдерживаемая карточка закупки.")
            return

        self._show_tender_documents(tender, start_download=True)

    @Slot(str, str)
    def open_analysis_citation(self, registry_key: str, document_key: str) -> None:
        normalized = registry_key.strip()
        if not normalized or not document_key:
            return
        repository = self.runtime.tender_registry
        tender = repository.get_tender(normalized) if repository is not None else None
        if tender is None:
            self._set_document_status("Не удалось восстановить карточку закупки из реестра.")
            return
        self._show_tender_documents(
            tender,
            document_key=document_key,
            start_download=False,
        )

    def _show_tender_documents(
        self,
        tender: UnifiedTender,
        *,
        document_key: str | None = None,
        start_download: bool,
    ) -> None:

        store = self.runtime.document_store
        service = self.runtime.document_service
        if store is None or service is None:
            self._set_document_status("Локальное хранилище документации недоступно.")
            return

        registry_key = tender_registry_key(tender)
        dialog = self._document_dialogs.get(registry_key)
        if dialog is None:
            parent = self.parent()
            parent_widget = parent if isinstance(parent, QWidget) else None
            dialog = TenderDocumentsDialog(
                tender,
                store,
                theme=self._theme,
                parent=parent_widget,
            )
            dialog.download_requested.connect(self.download_tender_documents)
            dialog.analysis_requested.connect(self.open_requirement_analysis)
            dialog.finished.connect(
                lambda _result, key=registry_key, current=dialog: self._forget_document_dialog(
                    key, current
                )
            )
            self._document_dialogs[registry_key] = dialog

        if document_key is None:
            dialog.refresh_documents()
        else:
            dialog.select_document(document_key)
        dialog.open()
        dialog.raise_()
        dialog.activateWindow()

        # The button in results/registry explicitly means download, so start
        # the background operation immediately after opening the local view.
        if start_download:
            self.download_tender_documents(tender, False)

    @Slot(object, bool)
    def download_tender_documents(
        self,
        tender: object,
        force: bool = False,
    ) -> None:
        if not isinstance(tender, UnifiedTender):
            return
        service = self.runtime.document_service
        if service is None:
            self._set_document_status("Сервис загрузки документации недоступен.")
            return

        registry_key = tender_registry_key(tender)
        dialog = self._document_dialogs.get(registry_key)
        if registry_key in self._document_workers:
            if dialog is not None:
                dialog.set_status("Документация этой закупки уже загружается.")
            return

        worker = _TenderDocumentWorker(
            service,
            tender,
            force=force,
        )
        worker.signals.succeeded.connect(self._on_document_download_succeeded)
        worker.signals.failed.connect(self._on_document_download_failed)
        self._document_workers[registry_key] = worker

        if dialog is not None:
            dialog.set_download_busy(
                True,
                message=(
                    "Повторная загрузка документации выполняется…"
                    if force
                    else "Загрузка документации выполняется в фоне…"
                ),
            )

        self.document_download_started.emit(registry_key)
        self._thread_pool.start(worker)

    @Slot(str, object, object)
    def _on_document_download_succeeded(
        self,
        registry_key: str,
        tender: object,
        result: object,
    ) -> None:
        self._document_workers.pop(registry_key, None)

        dialog = self._document_dialogs.get(registry_key)
        if dialog is not None and isinstance(result, TenderDocumentDownloadResult):
            dialog.set_download_result(result)
        elif dialog is not None:
            dialog.set_download_error("Сервис вернул неподдерживаемый результат.")

        if self._registry_dialog is not None:
            self._registry_dialog.refresh_records()

        analysis_dialog = self._analysis_dialogs.get(registry_key)
        if analysis_dialog is not None:
            analysis_dialog.set_status("Документация обновлена. Запустите анализ повторно.")

        self.document_download_finished.emit(
            registry_key,
            result,
        )

    @Slot(str, object, str, str)
    def _on_document_download_failed(
        self,
        registry_key: str,
        tender: object,
        error_type: str,
        message: str,
    ) -> None:
        del tender
        self._document_workers.pop(registry_key, None)
        rendered = message or error_type
        dialog = self._document_dialogs.get(registry_key)
        if dialog is not None:
            dialog.set_download_error(rendered)
        self.document_download_failed.emit(
            registry_key,
            rendered,
        )

    @Slot(str)
    def open_verification_details(
        self,
        registry_key: str,
    ) -> None:
        normalized = registry_key.strip()
        if not normalized:
            return
        try:
            review = self.verification_review_service.load(normalized)
        except Exception as exc:
            if self._registry_dialog is not None:
                self._registry_dialog.set_status(
                    f"Не удалось загрузить достоверность: {exc}",
                    error=True,
                )
            return
        dialog = self._verification_dialogs.get(normalized)
        if dialog is None:
            parent = self.parent()
            parent_widget = parent if isinstance(parent, QWidget) else None
            dialog = TenderVerificationDialog(
                review,
                theme=self._theme,
                parent=parent_widget,
            )
            dialog.resolve_requested.connect(self.resolve_verification_field)
            dialog.clear_requested.connect(self.clear_verification_field)
            dialog.refresh_requested.connect(self.refresh_verification_details)
            dialog.finished.connect(
                lambda _result, key=normalized, current=dialog: self._forget_verification_dialog(
                    key, current
                )
            )
            self._verification_dialogs[normalized] = dialog
        else:
            dialog.set_review(review)
        dialog.open()
        dialog.raise_()
        dialog.activateWindow()

    @Slot(str)
    def refresh_verification_details(
        self,
        registry_key: str,
    ) -> None:
        normalized = registry_key.strip()
        dialog = self._verification_dialogs.get(normalized)
        if dialog is None:
            return
        try:
            dialog.set_review(self.verification_review_service.load(normalized))
            dialog.set_status("Данные обновлены.")
        except Exception as exc:
            dialog.set_status(str(exc), error=True)

    @Slot(str, str, str, str)
    def resolve_verification_field(
        self,
        registry_key: str,
        field_name: str,
        candidate_id: str,
        note: str,
    ) -> None:
        dialog = self._verification_dialogs.get(registry_key)
        try:
            review = self.verification_review_service.resolve(
                registry_key,
                field_name,
                candidate_id,
                note=note,
            )
        except Exception as exc:
            if dialog is not None:
                dialog.set_status(
                    f"Не удалось сохранить выбор: {exc}",
                    error=True,
                )
            return
        if dialog is not None:
            dialog.set_review(review)
            dialog.set_status("Ручной выбор сохранён. Рейтинг пересчитывается.")
        if self._registry_dialog is not None:
            self._registry_dialog.refresh_records()
        if self.runtime.participation_score_service is not None:
            self.run_participation_score(registry_key)

    @Slot(str, str, str)
    def clear_verification_field(
        self,
        registry_key: str,
        field_name: str,
        note: str,
    ) -> None:
        dialog = self._verification_dialogs.get(registry_key)
        try:
            review = self.verification_review_service.clear(
                registry_key,
                field_name,
                note=note,
            )
        except Exception as exc:
            if dialog is not None:
                dialog.set_status(
                    f"Не удалось снять ручной выбор: {exc}",
                    error=True,
                )
            return
        if dialog is not None:
            dialog.set_review(review)
            dialog.set_status("Ручной выбор снят; восстановлен приоритет источников.")
        if self._registry_dialog is not None:
            self._registry_dialog.refresh_records()
        if self.runtime.participation_score_service is not None:
            self.run_participation_score(registry_key)

    def _forget_verification_dialog(
        self,
        registry_key: str,
        dialog: TenderVerificationDialog,
    ) -> None:
        if self._verification_dialogs.get(registry_key) is dialog:
            self._verification_dialogs.pop(registry_key, None)

    @Slot(str)
    def open_commercial_estimator(self, registry_key: str) -> None:
        normalized = registry_key.strip()
        if not normalized:
            return
        dialog = self._commercial_estimate_dialogs.get(normalized)
        if dialog is None:
            repository = (
                self.runtime.commercial_estimate_repository
                or CommercialEstimateRepository(self.data_directory / "tender_registry.sqlite3")
            )
            tender = (
                self.runtime.tender_registry.get_tender(normalized)
                if self.runtime.tender_registry is not None
                else None
            )
            parent = self.parent()
            parent_widget = parent if isinstance(parent, QWidget) else None
            dialog = CommercialEstimatorDialog(
                normalized,
                repository,
                tender=tender,
                parent=parent_widget,
            )
            dialog.finished.connect(
                lambda _result, key=normalized: self._commercial_estimate_dialogs.pop(key, None)
            )
            self._commercial_estimate_dialogs[normalized] = dialog
        dialog.open()
        dialog.raise_()
        dialog.activateWindow()

    @Slot(str)
    def open_full_analysis(self, registry_key: str) -> None:
        normalized = registry_key.strip()
        if not normalized:
            return
        service = self.runtime.full_analysis_service
        if service is None:
            if self._registry_dialog is not None:
                self._registry_dialog.set_status(
                    "Сервис полного анализа недоступен.",
                    error=True,
                )
            return
        dialog = self._full_analysis_dialogs.get(normalized)
        if dialog is None:
            parent = self.parent()
            parent_widget = parent if isinstance(parent, QWidget) else None
            dialog = TenderFullAnalysisDialog(
                normalized,
                theme=self._theme,
                parent=parent_widget,
            )
            dialog.cancel_requested.connect(self.cancel_full_analysis)
            dialog.documents_requested.connect(self.open_registry_documents)
            dialog.citation_requested.connect(self.open_analysis_citation)
            dialog.requirements_requested.connect(self.open_requirement_analysis)
            dialog.score_requested.connect(self.open_participation_score)
            dialog.finished.connect(
                lambda _result, key=normalized, current=dialog: self._forget_full_analysis_dialog(
                    key, current
                )
            )
            self._full_analysis_dialogs[normalized] = dialog
        dialog.open()
        dialog.raise_()
        dialog.activateWindow()
        self.run_full_analysis(normalized)

    @Slot(str)
    def run_full_analysis(self, registry_key: str) -> None:
        normalized = registry_key.strip()
        service = self.runtime.full_analysis_service
        if not normalized or service is None:
            return
        dialog = self._full_analysis_dialogs.get(normalized)
        if normalized in self._full_analysis_workers:
            if dialog is not None:
                dialog.message_label.setText("Полный анализ этой закупки уже выполняется.")
            return
        worker = _TenderFullAnalysisWorker(service, normalized)
        worker.signals.progress.connect(self._on_full_analysis_progress)
        worker.signals.succeeded.connect(self._on_full_analysis_succeeded)
        worker.signals.failed.connect(self._on_full_analysis_failed)
        self._full_analysis_workers[normalized] = worker
        if dialog is not None:
            dialog.begin()
        self.full_analysis_started.emit(normalized)
        self._thread_pool.start(worker)

    @Slot(str)
    def cancel_full_analysis(self, registry_key: str) -> None:
        worker = self._full_analysis_workers.get(registry_key.strip())
        if worker is not None:
            worker.cancel()

    @Slot(str, object)
    def _on_full_analysis_progress(self, registry_key: str, event: object) -> None:
        dialog = self._full_analysis_dialogs.get(registry_key)
        if dialog is not None and isinstance(event, FullAnalysisProgress):
            dialog.update_progress(event)

    @Slot(str, object)
    def _on_full_analysis_succeeded(self, registry_key: str, result: object) -> None:
        self._full_analysis_workers.pop(registry_key, None)
        dialog = self._full_analysis_dialogs.get(registry_key)
        if isinstance(result, TenderFullAnalysisResult):
            if dialog is not None:
                dialog.set_result(result)
            if self._registry_dialog is not None:
                self._registry_dialog.refresh_records()
            self.full_analysis_finished.emit(registry_key, result)
            return
        message = "Сервис вернул неподдерживаемый результат полного анализа."
        if dialog is not None:
            dialog.set_error(message)
        self.full_analysis_failed.emit(registry_key, message)

    @Slot(str, str, str)
    def _on_full_analysis_failed(
        self,
        registry_key: str,
        error_type: str,
        message: str,
    ) -> None:
        self._full_analysis_workers.pop(registry_key, None)
        rendered = message or error_type
        dialog = self._full_analysis_dialogs.get(registry_key)
        if dialog is not None:
            dialog.set_error(rendered)
        self.full_analysis_failed.emit(registry_key, rendered)

    def _forget_full_analysis_dialog(
        self,
        registry_key: str,
        dialog: TenderFullAnalysisDialog,
    ) -> None:
        if self._full_analysis_dialogs.get(registry_key) is dialog:
            self._full_analysis_dialogs.pop(registry_key, None)

    @Slot(str)
    def open_participation_score(
        self,
        registry_key: str,
    ) -> None:
        normalized = registry_key.strip()
        if not normalized:
            return
        service = self.runtime.participation_score_service
        if service is None:
            self._set_score_status("Сервис оценки участия недоступен.")
            return

        dialog = self._score_dialogs.get(normalized)
        if dialog is None:
            parent = self.parent()
            parent_widget = parent if isinstance(parent, QWidget) else None
            dialog = TenderParticipationScoreDialog(
                normalized,
                score=service.latest(normalized),
                theme=self._theme,
                parent=parent_widget,
            )
            dialog.recalculate_requested.connect(self.run_participation_score)
            dialog.finished.connect(
                lambda _result, key=normalized, current=dialog: self._forget_score_dialog(
                    key, current
                )
            )
            self._score_dialogs[normalized] = dialog
        else:
            latest = service.latest(normalized)
            if latest is not None:
                dialog.set_score(latest)

        dialog.open()
        dialog.raise_()
        dialog.activateWindow()
        self.run_participation_score(normalized)

    @Slot(str)
    def run_participation_score(
        self,
        registry_key: str,
    ) -> None:
        normalized = registry_key.strip()
        if not normalized:
            return
        service = self.runtime.participation_score_service
        if service is None:
            self._set_score_status("Сервис оценки участия недоступен.")
            return
        dialog = self._score_dialogs.get(normalized)
        if normalized in self._score_workers:
            if dialog is not None:
                dialog.set_status("Оценка этой закупки уже выполняется.")
            return

        worker = _ParticipationScoreWorker(
            service,
            normalized,
        )
        worker.signals.succeeded.connect(self._on_participation_score_succeeded)
        worker.signals.failed.connect(self._on_participation_score_failed)
        self._score_workers[normalized] = worker
        if dialog is not None:
            dialog.set_busy(
                True,
                message=("Расчёт рейтинга по карточке, документам и анализу требований…"),
            )
        self.score_started.emit(normalized)
        self._thread_pool.start(worker)

    @Slot(str, object)
    def _on_participation_score_succeeded(
        self,
        registry_key: str,
        result: object,
    ) -> None:
        self._score_workers.pop(registry_key, None)
        dialog = self._score_dialogs.get(registry_key)
        if isinstance(result, CorterisParticipationScore):
            if dialog is not None:
                dialog.set_score(result)
                decision_service = self.runtime.participation_decision_service
                if decision_service is not None:
                    dialog.set_decision(decision_service.evaluate(registry_key))
            if self._registry_dialog is not None:
                self._registry_dialog.refresh_records()
            self.score_finished.emit(registry_key, result)
            return

        message = "Сервис вернул неподдерживаемую оценку."
        if dialog is not None:
            dialog.set_error(message)
        self.score_failed.emit(registry_key, message)

    @Slot(str, str, str)
    def _on_participation_score_failed(
        self,
        registry_key: str,
        error_type: str,
        message: str,
    ) -> None:
        self._score_workers.pop(registry_key, None)
        rendered = message or error_type
        dialog = self._score_dialogs.get(registry_key)
        if dialog is not None:
            dialog.set_error(rendered)
        self.score_failed.emit(registry_key, rendered)

    @Slot(str)
    def open_requirement_analysis(self, registry_key: str) -> None:
        normalized = registry_key.strip()
        if not normalized:
            return

        service = self.runtime.requirement_analysis_service
        if service is None:
            self._set_analysis_status("Сервис анализа требований недоступен.")
            return

        dialog = self._analysis_dialogs.get(normalized)
        if dialog is None:
            parent = self.parent()
            parent_widget = parent if isinstance(parent, QWidget) else None
            latest = service.latest(normalized)
            dialog = TenderRequirementAnalysisDialog(
                normalized,
                analysis=latest,
                theme=self._theme,
                parent=parent_widget,
            )
            dialog.analysis_requested.connect(self.run_requirement_analysis)
            dialog.finished.connect(
                lambda _result, key=normalized, current=dialog: self._forget_analysis_dialog(
                    key, current
                )
            )
            self._analysis_dialogs[normalized] = dialog
        else:
            latest = service.latest(normalized)
            if latest is not None:
                dialog.set_analysis(latest)

        dialog.open()
        dialog.raise_()
        dialog.activateWindow()
        self.run_requirement_analysis(normalized, False)

    @Slot(str, bool)
    def run_requirement_analysis(
        self,
        registry_key: str,
        force_extraction: bool = False,
    ) -> None:
        normalized = registry_key.strip()
        if not normalized:
            return
        service = self.runtime.requirement_analysis_service
        if service is None:
            self._set_analysis_status("Сервис анализа требований недоступен.")
            return

        dialog = self._analysis_dialogs.get(normalized)
        if normalized in self._analysis_workers:
            if dialog is not None:
                dialog.set_status("Анализ этой закупки уже выполняется.")
            return

        worker = _TenderRequirementAnalysisWorker(
            service,
            normalized,
            force_extraction=force_extraction,
        )
        worker.signals.succeeded.connect(self._on_requirement_analysis_succeeded)
        worker.signals.failed.connect(self._on_requirement_analysis_failed)
        self._analysis_workers[normalized] = worker

        if dialog is not None:
            dialog.set_analysis_busy(
                True,
                message=(
                    "Повторное извлечение текста и анализ выполняются…"
                    if force_extraction
                    else "Анализ требований выполняется в фоне…"
                ),
            )

        self.analysis_started.emit(normalized)
        self._thread_pool.start(worker)

    @Slot(str, object)
    def _on_requirement_analysis_succeeded(
        self,
        registry_key: str,
        result: object,
    ) -> None:
        self._analysis_workers.pop(registry_key, None)
        dialog = self._analysis_dialogs.get(registry_key)
        if isinstance(result, TenderRequirementAnalysis):
            if dialog is not None:
                dialog.set_analysis(result)
            self.analysis_finished.emit(registry_key, result)
            return

        message = "Сервис вернул неподдерживаемый результат анализа."
        if dialog is not None:
            dialog.set_analysis_error(message)
        self.analysis_failed.emit(registry_key, message)

    @Slot(str, str, str)
    def _on_requirement_analysis_failed(
        self,
        registry_key: str,
        error_type: str,
        message: str,
    ) -> None:
        self._analysis_workers.pop(registry_key, None)
        rendered = message or error_type
        dialog = self._analysis_dialogs.get(registry_key)
        if dialog is not None:
            dialog.set_analysis_error(rendered)
        self.analysis_failed.emit(registry_key, rendered)

    @Slot(str, str, str)
    def _on_search_failed(
        self,
        profile_id: str,
        error_type: str,
        message: str,
    ) -> None:
        self._active_workers.pop(profile_id, None)
        if self._profiles_dialog is not None:
            self._profiles_dialog.set_search_busy(False)
            self._profiles_dialog.set_status(
                (
                    f"Поиск не выполнен: {message or error_type}. "
                    "Проверьте интернет, доступность ЕИС и параметры "
                    "профиля."
                ),
                error=True,
            )
        self.search_failed.emit(
            profile_id,
            message or error_type,
        )

    def _set_profiles_status(self, message: str) -> None:
        if self._profiles_dialog is not None:
            self._profiles_dialog.set_status(
                message,
                error=True,
            )

    def _set_document_status(self, message: str) -> None:
        if self._registry_dialog is not None:
            self._registry_dialog.set_status(
                message,
                error=True,
            )
        elif self._profiles_dialog is not None:
            self._profiles_dialog.set_status(
                message,
                error=True,
            )

    def _set_score_status(self, message: str) -> None:
        if self._registry_dialog is not None:
            self._registry_dialog.set_status(
                message,
                error=True,
            )
        elif self._profiles_dialog is not None:
            self._profiles_dialog.set_status(
                message,
                error=True,
            )

    def _set_analysis_status(self, message: str) -> None:
        if self._registry_dialog is not None:
            self._registry_dialog.set_status(
                message,
                error=True,
            )
        elif self._profiles_dialog is not None:
            self._profiles_dialog.set_status(
                message,
                error=True,
            )

    def _forget_score_dialog(
        self,
        registry_key: str,
        dialog: TenderParticipationScoreDialog,
    ) -> None:
        current = self._score_dialogs.get(registry_key)
        if current is dialog:
            self._score_dialogs.pop(registry_key, None)

    def _forget_analysis_dialog(
        self,
        registry_key: str,
        dialog: TenderRequirementAnalysisDialog,
    ) -> None:
        current = self._analysis_dialogs.get(registry_key)
        if current is dialog:
            self._analysis_dialogs.pop(registry_key, None)

    def _forget_document_dialog(
        self,
        registry_key: str,
        dialog: TenderDocumentsDialog,
    ) -> None:
        current = self._document_dialogs.get(registry_key)
        if current is dialog:
            self._document_dialogs.pop(registry_key, None)

    def _forget_result_dialog(
        self,
        dialog: TenderSearchResultsDialog,
    ) -> None:
        try:
            self._result_dialogs.remove(dialog)
        except ValueError:
            pass

    @staticmethod
    def _find_or_create_tender_menu(
        main_window: QMainWindow,
    ) -> QMenu:
        menu_bar = main_window.menuBar()
        for action in menu_bar.actions():
            menu = action.menu()
            if menu is None:
                continue
            title = menu.title().replace("&", "").strip().casefold()
            if menu.objectName() == "tendersMenu" or title == "тендеры":
                return menu

        menu = menu_bar.addMenu("Тендеры")
        menu.setObjectName("tendersMenu")
        return menu

    @staticmethod
    def _find_or_create_tender_toolbar(
        main_window: QMainWindow,
    ) -> QToolBar:
        existing = main_window.findChild(
            QToolBar,
            "tenderSearchToolBar",
        )
        if existing is not None:
            existing.setVisible(True)
            return existing

        toolbar = QToolBar("Тендеры", main_window)
        toolbar.setObjectName("tenderSearchToolBar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        main_window.addToolBar(
            Qt.ToolBarArea.TopToolBarArea,
            toolbar,
        )
        return toolbar


__all__ = ["TenderSearchUiController"]
