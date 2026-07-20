"""Qt integration controller for tender-search profiles and results."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
from pathlib import Path
from threading import Event
from time import monotonic
from typing import Protocol
from urllib.parse import urlsplit
from uuid import uuid4

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
    QMessageBox,
    QToolBar,
    QWidget,
)

from app.operations.contracts import (
    OperationCapabilities,
    OperationEpisode,
    OperationEpisodeId,
    OperationEvent,
    OperationKind,
    OperationProgress,
    OperationReasonCode,
    OperationState,
    OperationSubject,
)
from app.operations.diagnostics import DiagnosticRegistry
from app.operations.safe_feedback import SafeFeedbackProjector
from app.operations.transitions import transition_episode
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
)
from app.tenders.collector.manual_provider_registration import (
    ManualProviderCommandStatus,
    ManualProviderExecutionError,
)
from app.tenders.collector.manual_provider_protocol import (
    ManualProviderProtocolCommandStatus,
)
from app.tenders.collector.manual_adapter import ManualAdapterCommandStatus
from app.tenders.provider_credentials import CredentialErrorCategory
from app.tenders.collector.run_session import CollectorRunSession
from app.tenders.collector.search_errors import (
    classify_search_error,
    safe_search_error_fields,
)
from app.tenders.collector.source_monitoring import (
    SourceMonitoringService,
    SourceMonitoringSnapshot,
)
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.collector.verification_review import (
    TenderVerificationReviewService,
)
from app.tenders.collector.vertical_source_verification import (
    VerticalSourceVerificationRepository,
)
from app.tenders.full_analysis import (
    FullAnalysisProgress,
    TenderFullAnalysisResult,
    TenderFullAnalysisService,
)
from app.core.ai.orchestrator import TenderAiOrchestrator
from app.core.ai.recheck import TenderAiRecheckResult
from app.tenders.document_storage import (
    TenderDocumentDownloadResult,
    TenderDocumentDownloadService,
)
from app.tenders.models import UnifiedTender
from app.tenders.matching_catalog import (
    MatchingCatalog,
    MatchingCatalogRepository,
)
from app.tenders.requirement_analysis import (
    TenderRequirementAnalysis,
    TenderRequirementAnalysisService,
)
from app.tenders.provider_base import TenderSearchQuery
from app.tenders.unified_search import (
    UnifiedTenderSearchRequest,
    UnifiedTenderSearchValidationError,
    resolve_unified_tender_search,
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
    ManualAdapterWizardDialog,
    ManualProviderProtocolDialog,
    ManualProviderProtocolDialogOperation,
    ManualProviderRegistrationDialog,
    TenderProviderConfigurationDialog,
    TenderProviderManagerDialog,
)
from app.ui.provider_credentials_dialog import (
    CredentialDialogOperation,
    ProviderCredentialsDialog,
)
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
from app.ui.tender_unified_search_panel import TenderUnifiedSearchPanel
from app.ui.theme.colors import ThemeName


class _ThreadPoolLike(Protocol):
    def start(self, runnable: QRunnable) -> None: ...


class TenderSearchLifecycleState(StrEnum):
    IDLE = "idle"
    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CLOSED = "closed"

    @property
    def terminal(self) -> bool:
        return self in {
            self.CANCELLED,
            self.COMPLETED,
            self.FAILED,
            self.TIMED_OUT,
            self.CLOSED,
        }


@dataclass(frozen=True, slots=True)
class TenderSearchLifecycleSnapshot:
    generation: int
    revision: int
    state: TenderSearchLifecycleState
    profile_id: str = ""
    updated_at: str = ""
    error_code: str = ""
    message: str = ""

    @property
    def active(self) -> bool:
        return self.state in {
            TenderSearchLifecycleState.QUEUED,
            TenderSearchLifecycleState.RUNNING,
            TenderSearchLifecycleState.CANCELLING,
        }


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


class _AiRecheckWorkerSignals(QObject):
    succeeded = Signal(str, object)
    failed = Signal(str, str, str)


class _TenderAiRecheckWorker(QRunnable):
    def __init__(self, orchestrator: TenderAiOrchestrator, registry_key: str) -> None:
        super().__init__()
        self.orchestrator = orchestrator
        self.registry_key = registry_key.strip()
        self.signals = _AiRecheckWorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        try:
            result = self.orchestrator.recheck(self.registry_key)
        except Exception as exc:
            self.signals.failed.emit(
                self.registry_key,
                type(exc).__name__,
                "",
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
    started = Signal(int)
    progress = Signal(int, object)
    succeeded = Signal(int, object)
    failed = Signal(int, str, str)


class _CollectorRunWorker(QRunnable):
    def __init__(
        self,
        session: CollectorRunSession,
        query: object,
        provider_ids: tuple[str, ...],
        generation: int = 0,
    ) -> None:
        super().__init__()
        self.session = session
        self.query = query
        self.provider_ids = provider_ids
        self.generation = generation
        self.cancellation_token = CollectorCancellationToken()
        self.completion_event = Event()
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
                progress_callback=lambda event: self.signals.progress.emit(
                    self.generation,
                    event,
                ),
            )

        self.signals.started.emit(self.generation)
        try:
            result = asyncio.run(execute())
        except Exception as exc:
            failure = classify_search_error(exc)
            self.signals.failed.emit(
                self.generation,
                failure.code,
                failure.message,
            )
        else:
            self.signals.succeeded.emit(self.generation, result)
        finally:
            self.completion_event.set()

    def abandon(self) -> None:
        """Mark a queued runnable removed from the owned pool as complete."""

        self.cancel()
        self.completion_event.set()


def safe_manual_health_error_message(_error: BaseException) -> str:
    """Return a fixed UI message without exception type, target or payload text."""

    return "Проверка подключения завершилась безопасной ошибкой."


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
        self.cancellation_token = CollectorCancellationToken()
        self.completion_event = Event()
        self.signals = _ProviderCheckWorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        try:
            visible = {item.provider_id: item for item in self.manager.states()}
            has_manual = any(
                visible.get(provider_id) is not None and visible[provider_id].registration_only
                for provider_id in self.provider_ids
            )
            operation = (
                self.manager.check_providers(
                    self.provider_ids,
                    cancellation_token=self.cancellation_token,
                )
                if has_manual
                else self.manager.check_providers(self.provider_ids)
            )
            states = asyncio.run(operation)
        except Exception as exc:
            self.signals.failed.emit(
                "ProviderHealthCheckError",
                safe_manual_health_error_message(exc),
            )
        else:
            self.signals.succeeded.emit(states)
        finally:
            self.completion_event.set()

    def cancel(self) -> bool:
        return self.cancellation_token.cancel()

    def abandon(self) -> None:
        self.cancel()
        self.completion_event.set()


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
    operation_episode_changed = Signal(object)
    score_started = Signal(str)
    score_finished = Signal(str, object)
    score_failed = Signal(str, str)
    full_analysis_started = Signal(str)
    full_analysis_finished = Signal(str, object)
    full_analysis_failed = Signal(str, str)
    ai_recheck_started = Signal(str)
    ai_recheck_finished = Signal(str, object)
    ai_recheck_failed = Signal(str, str)

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
        snapshot_factory = getattr(self.provider_manager, "settings_snapshot", None)
        self.collector_session = collector_session or CollectorRunSession(
            self.data_directory,
            provider_settings_snapshot_factory=(
                snapshot_factory if callable(snapshot_factory) else None
            ),
        )
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
        self._owns_thread_pool = thread_pool is None
        self._thread_pool = thread_pool or QThreadPool(self)
        self._accepting_runs = True
        self._shutdown_complete = False
        self._run_generation = 0
        self._lifecycle_snapshot = TenderSearchLifecycleSnapshot(
            generation=0,
            revision=0,
            state=TenderSearchLifecycleState.IDLE,
            updated_at=_utc_now(),
        )
        self._operation_episode: OperationEpisode | None = None
        self.operation_diagnostic_registry = DiagnosticRegistry(max_records=256)
        self.operation_feedback_projector = SafeFeedbackProjector(
            registry=self.operation_diagnostic_registry
        )
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
        self._unified_search_panel: TenderUnifiedSearchPanel | None = None
        self._collector_worker: _CollectorRunWorker | None = None
        self._source_monitoring_snapshot: SourceMonitoringSnapshot | None = None
        self._collector_profile_id = ""
        self._profile_dialog_run_id = ""
        self._result_dialogs: list[TenderSearchResultsDialog] = []
        self._document_dialogs: dict[str, TenderDocumentsDialog] = {}
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
        self._ai_recheck_workers: dict[str, _TenderAiRecheckWorker] = {}
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
        self.source_monitoring_service = SourceMonitoringService(
            state_repository=self.scheduler_ui_controller.freshness_repository,
            schedule_repository=self.scheduler_ui_controller.scheduler.repository,
            verification_repository=getattr(
                self.provider_manager,
                "vertical_verification_repository",
                VerticalSourceVerificationRepository(registry_path),
            ),
            check_repository=getattr(self.provider_manager, "check_repository", None),
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
    def unified_search_panel(self) -> TenderUnifiedSearchPanel | None:
        return self._unified_search_panel

    @property
    def lifecycle_snapshot(self) -> TenderSearchLifecycleSnapshot:
        return self._lifecycle_snapshot

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
        bind_analytics = getattr(main_window, "bind_tender_analytics_runtime", None)
        if callable(bind_analytics):
            bind_analytics(self)
        return self.action

    def tender_workspace_actions(self) -> tuple[QAction, ...]:
        """Return the canonical actions without creating a second action set."""
        return (
            self.action,
            self.registry_action,
            self.providers_action,
            self.collector_action,
            self.company_capability_action,
            self.matching_catalog_action,
            self.aggregator_discovery_action,
            self.scheduler_ui_controller.schedule_action,
            self.scheduler_ui_controller.notifications_action,
        )

    def apply_theme(self, theme: ThemeName | str) -> None:
        """Retheme controller-owned surfaces without creating a second theme owner."""

        self._theme = ThemeName(theme)
        if self._unified_search_panel is not None:
            self._unified_search_panel.apply_theme(self._theme)

    def install_on_tender_workspace(self, workspace: QWidget) -> None:
        """Bind canonical actions and the single unified-search panel."""
        binder = getattr(workspace, "bind_tender_actions", None)
        if not callable(binder):
            raise TypeError("Tender workspace does not support action binding")
        binder(self.tender_workspace_actions())

        legacy_handoff = getattr(workspace, "canonical_provider_settings_requested", None)
        if legacy_handoff is not None and not bool(
            getattr(workspace, "_provider_settings_handoff_bound", False)
        ):
            legacy_handoff.connect(self.open_provider_manager_dialog)
            setattr(workspace, "_provider_settings_handoff_bound", True)

        installer = getattr(workspace, "install_unified_search_panel", None)
        if not callable(installer):
            raise TypeError("Tender workspace does not support unified search")
        if self._unified_search_panel is None:
            panel = TenderUnifiedSearchPanel(
                theme=self._theme,
                parent=workspace,
            )
            panel.start_requested.connect(self.start_unified_search)
            panel.stop_requested.connect(self.stop_collector)
            panel.profiles_requested.connect(self.open_profiles_dialog)
            panel.sources_requested.connect(self.open_provider_manager_dialog)
            panel.registry_requested.connect(self.open_registry_dialog)
            self._unified_search_panel = panel
        installer(self._unified_search_panel)
        self.refresh_unified_search_configuration()

    @Slot()
    def refresh_unified_search_configuration(self) -> None:
        panel = self._unified_search_panel
        if panel is None or panel.running:
            return
        panel.set_provider_states(
            self.provider_manager.states(),
            preserve_selection=True,
        )
        panel.set_profiles(
            self.runtime.repository.list_profiles(include_disabled=False),
            select_id=self._collector_profile_id,
        )

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
            self._profiles_dialog.panel.profile_saved.connect(
                lambda _profile_id: self.refresh_unified_search_configuration()
            )
            self._profiles_dialog.panel.profile_deleted.connect(
                lambda _profile_id: self.refresh_unified_search_configuration()
            )

        self._profiles_dialog.refresh_profiles()
        self._profiles_dialog.open()
        self._profiles_dialog.raise_()
        self._profiles_dialog.activateWindow()

    @Slot()
    def open_company_capability_dialog(self) -> None:
        parent = self.parent()
        parent_widget = parent if isinstance(parent, QWidget) else None
        if self._company_capability_dialog is None:
            repository = self.runtime.capability_repository
            if repository is None:
                repository = CompanyCapabilityProfileRepository(
                    self.data_directory / "company_capability_profile.json"
                )
            self._company_capability_dialog = CompanyCapabilityDialog(
                repository,
                parent=parent_widget,
            )
        else:
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
        # The canonical Collector service loads the persisted catalog for each
        # fresh run. Keeping a second mutable legacy filter here would create a
        # competing production search owner.
        del catalog
        self.refresh_unified_search_configuration()

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

    @Slot(str)
    def open_registry_record(self, registry_key: str) -> bool:
        """Open the existing registry dialog at one exact canonical record."""

        normalized = registry_key.strip()
        repository = self.runtime.tender_registry
        if not normalized or repository is None or repository.get_record(normalized) is None:
            return False
        self.open_registry_dialog()
        if self._registry_dialog is None:
            return False
        return self._registry_dialog.select_registry_key(normalized)

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

        if not self._accepting_runs:
            return False
        normalized = profile_id.strip().casefold()
        if not normalized:
            return False
        try:
            profile = self.runtime.repository.get(normalized)
        except Exception:
            if self._collector_dialog is not None:
                self._collector_dialog.set_error(
                    "Не удалось безопасно загрузить выбранный профиль."
                )
            return False
        if not profile.enabled:
            if self._collector_dialog is not None:
                self._collector_dialog.set_error("Выбранный профиль отключён.")
            return False

        try:
            requested_provider_ids = tuple(
                str(item) for item in (provider_ids or ()) if str(item).strip()
            )
            if not requested_provider_ids:
                requested_provider_ids = self.provider_manager.enabled_provider_ids()
            resolver = getattr(self.provider_manager, "resolve_provider_ids", None)
            selected = (
                resolver(requested_provider_ids)
                if callable(resolver)
                else tuple(
                    dict.fromkeys(item.strip().casefold() for item in requested_provider_ids)
                )
            )
            runnable_resolver = getattr(
                self.provider_manager,
                "assert_runnable_provider_ids",
                None,
            )
            if callable(runnable_resolver):
                selected = runnable_resolver(selected)
        except ManualProviderExecutionError:
            if self._collector_dialog is not None:
                self._collector_dialog.set_error(
                    "Источник требует выбора протокола и пока недоступен для запуска."
                )
            return False
        except (KeyError, TypeError, ValueError):
            if self._collector_dialog is not None:
                self._collector_dialog.set_error("Выбран неизвестный источник.")
            return False
        enabled = set(self.provider_manager.enabled_provider_ids())
        selected = tuple(provider_id for provider_id in selected if provider_id in enabled)
        if not selected:
            if self._collector_dialog is not None:
                self._collector_dialog.set_error("Нет включённых источников для запуска.")
            return False

        query = profile.to_search_query()
        query = replace(
            query,
            extra={
                **dict(query.extra),
                "corteris_run_context": {
                    "schema_version": 1,
                    "origin": "saved_profile",
                    "profile_id": normalized[:120],
                    "profile_name": profile.name[:200],
                },
            },
        )
        return self._try_start_collector_query(
            profile_id=normalized,
            profile_name=profile.name,
            query=query,
            provider_ids=selected,
        )

    @Slot(object)
    def start_unified_search(self, request: object) -> None:
        """Resolve one typed panel request against current canonical snapshots."""
        panel = self._unified_search_panel
        if not isinstance(request, UnifiedTenderSearchRequest):
            if panel is not None:
                panel.set_error("Получен неподдерживаемый запрос поиска.")
            return
        try:
            resolved = resolve_unified_tender_search(
                request,
                profiles=self.runtime.repository.list_profiles(),
                provider_states=self.provider_manager.states(),
            )
        except UnifiedTenderSearchValidationError as exc:
            if panel is not None:
                panel.set_error(exc.public_message)
                panel.focus_search()
            return

        self._try_start_collector_query(
            profile_id=resolved.profile.id,
            profile_name=resolved.profile.name,
            query=resolved.query,
            provider_ids=resolved.provider_ids,
        )

    def _try_start_collector_query(
        self,
        *,
        profile_id: str,
        profile_name: str,
        query: TenderSearchQuery,
        provider_ids: tuple[str, ...],
    ) -> bool:
        """Create and wire the sole Collector worker for every UI entry point."""
        if not self._accepting_runs:
            return False
        if self._collector_worker is not None or self._lifecycle_snapshot.active:
            if self._collector_dialog is not None:
                self._collector_dialog.set_status("Сборщик уже выполняется.")
            if self._unified_search_panel is not None:
                self._unified_search_panel.set_status("Поиск уже выполняется.", error=True)
            return False

        if "corteris_run_context" not in query.extra:
            query = replace(
                query,
                extra={
                    **dict(query.extra),
                    "corteris_run_context": {
                        "schema_version": 1,
                        "origin": "unified_search",
                        "profile_id": profile_id[:120],
                        "profile_name": profile_name[:200],
                    },
                },
            )
        self._run_generation += 1
        generation = self._run_generation
        self._transition_lifecycle(
            TenderSearchLifecycleState.QUEUED,
            generation=generation,
            profile_id=profile_id,
        )
        worker = _CollectorRunWorker(
            self.collector_session,
            query,
            provider_ids,
            generation,
        )
        worker.signals.started.connect(self._on_collector_started)
        worker.signals.progress.connect(self._on_collector_progress)
        worker.signals.succeeded.connect(self._on_collector_succeeded)
        worker.signals.failed.connect(self._on_collector_failed)
        self._collector_worker = worker
        self._collector_profile_id = profile_id

        if self._collector_dialog is not None:
            self._collector_dialog.begin_run(
                profile_name,
                provider_ids,
            )
        if self._unified_search_panel is not None:
            self._unified_search_panel.begin_run(
                profile_name,
                provider_ids,
            )
        self.collector_started.emit(profile_id)
        self._thread_pool.start(worker)
        return True

    @Slot()
    def stop_collector(self) -> None:
        worker = self._collector_worker
        if worker is None:
            return
        self._transition_lifecycle(
            TenderSearchLifecycleState.CANCELLING,
            generation=worker.generation,
        )
        worker.cancel()
        if self._collector_dialog is not None:
            self._collector_dialog.mark_cancel_requested()
        if self._unified_search_panel is not None:
            self._unified_search_panel.mark_cancel_requested()

    @Slot(int)
    def _on_collector_started(self, generation: int) -> None:
        self._transition_lifecycle(
            TenderSearchLifecycleState.RUNNING,
            generation=generation,
        )

    @Slot(int, object)
    def _on_collector_progress(self, generation: int, event: object) -> None:
        if not self._accepts_generation(generation):
            return
        if self._collector_dialog is not None and isinstance(event, CollectorProgressEvent):
            self._collector_dialog.apply_progress(event)
        if self._unified_search_panel is not None and isinstance(event, CollectorProgressEvent):
            self._unified_search_panel.apply_progress(event)

    @Slot(int, object)
    def _on_collector_succeeded(
        self,
        generation: int | object,
        result: object | None = None,
    ) -> None:
        if result is None:
            result = generation
            generation = self._lifecycle_snapshot.generation
        generation = int(generation)
        if not self._accepts_generation(generation):
            return
        if not isinstance(result, CollectorRunResult):
            self._on_collector_failed(
                generation,
                "TypeError",
                "Коллектор вернул неподдерживаемый результат.",
            )
            return
        state = (
            TenderSearchLifecycleState.CANCELLED
            if (
                result.status.value == "cancelled"
                or self._lifecycle_snapshot.state is TenderSearchLifecycleState.CANCELLING
            )
            else (
                TenderSearchLifecycleState.TIMED_OUT
                if bool(getattr(result.batch_result, "timed_out", False))
                else TenderSearchLifecycleState.COMPLETED
            )
        )
        self._transition_lifecycle(state, generation=generation)
        self._collector_worker = None
        if self._collector_dialog is not None:
            self._collector_dialog.set_result(result)
        if self._unified_search_panel is not None:
            self._unified_search_panel.set_result(result)
        if self._registry_dialog is not None:
            self._registry_dialog.refresh_records()
        self.refresh_provider_states()
        self.collector_finished.emit(result)
        self._finish_profile_dialog_run(result=result)

    @Slot(int, str, str)
    def _on_collector_failed(
        self,
        generation: int | str,
        error_type: str,
        message: str | None = None,
    ) -> None:
        if message is None:
            message = error_type
            error_type = str(generation)
            generation = self._lifecycle_snapshot.generation
        generation = int(generation)
        if not self._accepts_generation(generation):
            return
        safe_code, safe_message = safe_search_error_fields(error_type)
        terminal = (
            TenderSearchLifecycleState.CANCELLED
            if safe_code == "search_cancelled"
            else (
                TenderSearchLifecycleState.TIMED_OUT
                if safe_code == "provider_timeout"
                else TenderSearchLifecycleState.FAILED
            )
        )
        self._transition_lifecycle(
            terminal,
            generation=generation,
            error_code=safe_code,
            message=safe_message,
        )
        self._collector_worker = None
        rendered = f"{safe_code}: {safe_message}"
        if self._collector_dialog is not None:
            self._collector_dialog.set_error(f"Сбор завершился ошибкой: {rendered}")
        if self._unified_search_panel is not None:
            self._unified_search_panel.set_error(f"Поиск завершился ошибкой: {rendered}")
        self.refresh_provider_states()
        self.collector_failed.emit(rendered)
        self._finish_profile_dialog_run(error=safe_message)

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
            self._provider_dialog.provider_configuration_requested.connect(self.configure_provider)
            self._provider_dialog.provider_credentials_requested.connect(
                self.configure_provider_credentials
            )
            self._provider_dialog.manual_provider_add_requested.connect(self.add_manual_provider)
            self._provider_dialog.manual_provider_edit_requested.connect(self.edit_manual_provider)
            self._provider_dialog.manual_provider_protocol_requested.connect(
                self.configure_manual_provider_protocol
            )
            self._provider_dialog.manual_adapter_requested.connect(
                self.configure_manual_provider_adapter
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
        monitoring = self.source_monitoring_service.snapshot(states)
        previous = self._source_monitoring_snapshot
        self._source_monitoring_snapshot = monitoring
        if previous is not None:
            self.scheduler_ui_controller.publish_monitoring_transitions(previous, monitoring)
        if self._provider_dialog is not None:
            self._provider_dialog.set_states(states)
            self._provider_dialog.set_monitoring_snapshot(monitoring)
        if self._collector_dialog is not None and not self._collector_dialog.running:
            self._collector_dialog.set_provider_states(
                states,
                preserve_selection=True,
            )
        if self._unified_search_panel is not None and not self._unified_search_panel.running:
            self._unified_search_panel.set_provider_states(
                states,
                preserve_selection=True,
            )
        self.scheduler_ui_controller.refresh_schedule_dialog()

    @Slot()
    def add_manual_provider(self) -> None:
        editor = ManualProviderRegistrationDialog(parent=self._provider_dialog)
        if editor.exec() != ManualProviderRegistrationDialog.DialogCode.Accepted:
            return
        try:
            draft = editor.draft()
        except (TypeError, ValueError):
            if self._provider_dialog is not None:
                self._provider_dialog.set_status(
                    "Данные площадки отклонены безопасной валидацией.",
                    error=True,
                )
            return
        result = self.provider_manager.register_manual_provider(draft)
        if result.status is not ManualProviderCommandStatus.CREATED:
            if self._provider_dialog is not None:
                self._provider_dialog.set_status(result.message, error=True)
            return
        self.refresh_provider_states()
        if self._provider_dialog is not None:
            self._provider_dialog.set_status(result.message)

    @Slot(str)
    def edit_manual_provider(self, provider_id: str) -> None:
        normalized = provider_id.strip().casefold()
        state = next(
            (
                item
                for item in self.provider_manager.states()
                if item.provider_id == normalized and item.registration_only
            ),
            None,
        )
        if state is None or state.manual_registration is None:
            if self._provider_dialog is not None:
                self._provider_dialog.set_status("Регистрация площадки не найдена.", error=True)
            return
        editor = ManualProviderRegistrationDialog(
            state.manual_registration,
            parent=self._provider_dialog,
        )
        if editor.exec() != ManualProviderRegistrationDialog.DialogCode.Accepted:
            return
        try:
            draft = editor.draft()
        except (TypeError, ValueError):
            if self._provider_dialog is not None:
                self._provider_dialog.set_status(
                    "Данные площадки отклонены безопасной валидацией.",
                    error=True,
                )
            return
        result = self.provider_manager.update_manual_provider(normalized, draft)
        if result.status is not ManualProviderCommandStatus.UPDATED:
            if self._provider_dialog is not None:
                self._provider_dialog.set_status(result.message, error=True)
            return
        self.refresh_provider_states()
        if self._provider_dialog is not None:
            self._provider_dialog.set_status(result.message)

    @Slot(str)
    def configure_provider(self, provider_id: str) -> None:
        normalized = provider_id.strip().casefold()
        if normalized == "mos_supplier":
            self.configure_provider_credentials(normalized)
            return
        state = next(
            (item for item in self.provider_manager.states() if item.provider_id == normalized),
            None,
        )
        if state is None or state.implementation_status != "commercial_access_pending":
            if self._provider_dialog is not None:
                self._provider_dialog.set_status("Для источника нет non-secret настроек.")
            return
        editor = TenderProviderConfigurationDialog(
            state,
            parent=self._provider_dialog,
        )
        if editor.exec() != TenderProviderConfigurationDialog.DialogCode.Accepted:
            return
        setter = getattr(self.provider_manager, "set_configuration", None)
        if not callable(setter):
            if self._provider_dialog is not None:
                self._provider_dialog.set_status("Менеджер не поддерживает настройку источника.")
            return
        try:
            setter(normalized, editor.configuration())
        except Exception as exc:
            if self._provider_dialog is not None:
                self._provider_dialog.set_status(
                    f"Не удалось сохранить non-secret настройки: {type(exc).__name__}",
                    error=True,
                )
            return
        self.refresh_provider_states()
        if self._provider_dialog is not None:
            self._provider_dialog.set_status("Настройки источника сохранены.")

    @Slot(str)
    def configure_manual_provider_protocol(self, provider_id: str) -> None:
        normalized = provider_id.strip().casefold()
        state = next(
            (
                item
                for item in self.provider_manager.states()
                if item.provider_id == normalized and item.registration_only
            ),
            None,
        )
        if state is None or state.manual_registration is None:
            if self._provider_dialog is not None:
                self._provider_dialog.set_status("Ручная регистрация не найдена.", error=True)
            return
        editor = ManualProviderProtocolDialog(
            state.manual_registration,
            policies=self.provider_manager.manual_protocol_policies(),
            parent=self._provider_dialog,
        )
        if editor.exec() != ManualProviderProtocolDialog.DialogCode.Accepted:
            return

        if editor.operation is ManualProviderProtocolDialogOperation.CLEAR:
            answer = QMessageBox.question(
                self._provider_dialog,
                "Сброс выбора протокола",
                "Сбросить выбранный протокол? Площадка снова будет ожидать выбора.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            result = self.provider_manager.clear_manual_provider_protocol(
                normalized,
                expected_updated_at=editor.expected_updated_at,
            )
            success = result.status is ManualProviderProtocolCommandStatus.CLEARED
        else:
            try:
                draft = editor.draft()
            except (TypeError, ValueError):
                if self._provider_dialog is not None:
                    self._provider_dialog.set_status(
                        "Настройка протокола отклонена безопасной валидацией.",
                        error=True,
                    )
                return
            result = self.provider_manager.save_manual_provider_protocol(
                normalized,
                draft,
                expected_updated_at=editor.expected_updated_at,
            )
            success = result.status in {
                ManualProviderProtocolCommandStatus.SAVED,
                ManualProviderProtocolCommandStatus.CHANGED,
            }

        if not success:
            if self._provider_dialog is not None:
                self._provider_dialog.set_status(result.message, error=True)
            return
        self.refresh_provider_states()
        if self._provider_dialog is not None:
            self._provider_dialog.set_status(result.message)

    @Slot(str)
    def configure_manual_provider_adapter(self, provider_id: str) -> None:
        normalized = provider_id.strip().casefold()
        state = next(
            (
                item
                for item in self.provider_manager.states()
                if item.provider_id == normalized and item.registration_only
            ),
            None,
        )
        if (
            state is None
            or state.manual_registration is None
            or state.manual_registration.protocol_selection is None
        ):
            if self._provider_dialog is not None:
                self._provider_dialog.set_status(
                    "Сначала выберите протокол ручной площадки.", error=True
                )
            return
        editor = ManualAdapterWizardDialog(
            state.manual_registration,
            preview_command=lambda spec, sample: (
                self.provider_manager.preview_manual_provider_adapter(
                    normalized,
                    spec,
                    sample,
                )
            ),
            parent=self._provider_dialog,
        )
        if editor.exec() != ManualAdapterWizardDialog.DialogCode.Accepted:
            return
        try:
            spec = editor.specification()
        except (TypeError, ValueError):
            if self._provider_dialog is not None:
                self._provider_dialog.set_status(
                    "Спецификация адаптера отклонена безопасной проверкой.", error=True
                )
            return
        result = self.provider_manager.save_manual_adapter_spec(
            normalized,
            spec,
            expected_updated_at=editor.expected_updated_at,
        )
        success = result.status in {
            ManualAdapterCommandStatus.SAVED,
            ManualAdapterCommandStatus.UNCHANGED,
        }
        if not success:
            if self._provider_dialog is not None:
                self._provider_dialog.set_status(result.message, error=True)
            return
        self.refresh_provider_states()
        if self._provider_dialog is not None:
            self._provider_dialog.set_status(result.message)

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
                    self._safe_worker_failure(
                        OperationKind.PROVIDER_CHECK,
                        type(exc).__name__,
                        str(exc),
                    ),
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
        normalized = provider_id.strip().casefold()
        state = next(
            (item for item in self.provider_manager.states() if item.provider_id == normalized),
            None,
        )
        if state is None or not (
            normalized == "mos_supplier"
            or state.implementation_status == "commercial_access_pending"
        ):
            if self._provider_dialog is not None:
                self._provider_dialog.set_status("Для источника нет управляемого credential.")
            return

        safe_state = self.provider_manager.credential_state(normalized, "api_key")
        parent = self._provider_dialog
        dialog = ProviderCredentialsDialog(
            normalized,
            state.display_name,
            state=safe_state,
            parent=parent,
        )
        if dialog.exec() != ProviderCredentialsDialog.DialogCode.Accepted:
            return
        try:
            if dialog.operation is CredentialDialogOperation.DELETE:
                result = self.provider_manager.delete_credential(normalized, "api_key")
            elif dialog.operation in {
                CredentialDialogOperation.SAVE,
                CredentialDialogOperation.REPLACE,
            }:
                result = self.provider_manager.save_credential(
                    normalized,
                    "api_key",
                    dialog.take_value(),
                    replace=(dialog.operation is CredentialDialogOperation.REPLACE),
                )
            else:
                return
        except Exception:
            if self._provider_dialog is not None:
                self._provider_dialog.set_status(
                    "Операция credential не выполнена.",
                    error=True,
                )
            return

        self.refresh_provider_states()
        if self._provider_dialog is not None:
            self._provider_dialog.set_status(
                result.message,
                error=result.error_category is not CredentialErrorCategory.NONE,
            )

    @Slot(str)
    def check_provider_connection(
        self,
        provider_id: str,
    ) -> None:
        state = next(
            (
                item
                for item in self.provider_manager.states()
                if item.provider_id == provider_id.strip().casefold()
            ),
            None,
        )
        if state is not None and state.registration_only:
            registration = state.manual_registration
            selection = registration.protocol_selection if registration is not None else None
            if selection is None or not state.adapter_compiled:
                if self._provider_dialog is not None:
                    self._provider_dialog.set_status(
                        "Сначала настройте протокол и адаптер.", error=True
                    )
                return
            hostname = urlsplit(selection.endpoint_url).hostname or "неизвестный host"
            answer = QMessageBox.question(
                self._provider_dialog,
                "Проверка подключения",
                (
                    f"Выполнить сетевую проверку «{state.display_name}»?\n"
                    f"Протокол: {selection.family.value.upper()}\n"
                    f"Host: {hostname}"
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer is not QMessageBox.StandardButton.Yes:
                return
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
        if self._collector_worker is not None:
            if self._provider_dialog is not None:
                self._provider_dialog.set_status(
                    "Проверка подключения недоступна во время активного сбора.",
                    error=True,
                )
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
        if self._lifecycle_snapshot.active:
            self._set_profiles_status("Этот профиль уже выполняется. Дождитесь завершения.")
            return

        self._profile_dialog_run_id = normalized
        if self._profiles_dialog is not None:
            self._profiles_dialog.set_search_busy(True, profile_id=normalized)
        self.search_started.emit(normalized)
        if not self.try_start_collector(normalized, ()):
            self._profile_dialog_run_id = ""
            if self._profiles_dialog is not None:
                self._profiles_dialog.set_search_busy(False)
            self._set_profiles_status("Поиск не запущен. Проверьте профиль и источники.")
            return

    def _accepts_generation(self, generation: int) -> bool:
        snapshot = self._lifecycle_snapshot
        return snapshot.generation == generation and not snapshot.state.terminal

    @property
    def operation_episode(self) -> OperationEpisode | None:
        return self._operation_episode

    def _transition_lifecycle(
        self,
        state: TenderSearchLifecycleState,
        *,
        generation: int,
        profile_id: str = "",
        error_code: str = "",
        message: str = "",
    ) -> bool:
        current = self._lifecycle_snapshot
        if state is TenderSearchLifecycleState.CLOSED and generation == current.generation:
            pass
        elif state is TenderSearchLifecycleState.QUEUED and generation > current.generation:
            pass
        elif generation != current.generation or current.state.terminal:
            return False
        elif (
            current.state is TenderSearchLifecycleState.CANCELLING
            and state is TenderSearchLifecycleState.RUNNING
        ):
            return False
        if current.generation == generation and current.state is state:
            return False
        self._lifecycle_snapshot = TenderSearchLifecycleSnapshot(
            generation=generation,
            revision=current.revision + 1,
            state=state,
            profile_id=profile_id or current.profile_id,
            updated_at=_utc_now(),
            error_code=error_code[:120],
            message=message[:300],
        )
        self._sync_operation_episode(self._lifecycle_snapshot)
        return True

    def _sync_operation_episode(self, snapshot: TenderSearchLifecycleSnapshot) -> None:
        occurred_at = datetime.fromisoformat(snapshot.updated_at.replace("Z", "+00:00"))
        mapped_state = {
            TenderSearchLifecycleState.IDLE: OperationState.IDLE,
            TenderSearchLifecycleState.QUEUED: OperationState.QUEUED,
            TenderSearchLifecycleState.RUNNING: OperationState.RUNNING,
            TenderSearchLifecycleState.CANCELLING: OperationState.CANCELLING,
            TenderSearchLifecycleState.CANCELLED: OperationState.CANCELLED,
            TenderSearchLifecycleState.COMPLETED: OperationState.SUCCEEDED,
            TenderSearchLifecycleState.FAILED: OperationState.FAILED,
            TenderSearchLifecycleState.TIMED_OUT: OperationState.TIMED_OUT,
            TenderSearchLifecycleState.CLOSED: OperationState.CLOSED,
        }[snapshot.state]
        reason = {
            OperationState.CANCELLED: OperationReasonCode.CANCELLED_BY_USER,
            OperationState.TIMED_OUT: OperationReasonCode.TIMEOUT,
            OperationState.FAILED: OperationReasonCode.SOURCE_UNAVAILABLE,
        }.get(mapped_state)
        capabilities = OperationCapabilities(
            can_cancel=mapped_state in {OperationState.QUEUED, OperationState.RUNNING},
            can_retry=mapped_state
            in {
                OperationState.CANCELLED,
                OperationState.FAILED,
                OperationState.TIMED_OUT,
            },
            can_close=True,
            can_open_result=mapped_state is OperationState.SUCCEEDED,
            can_open_diagnostics=mapped_state in {OperationState.FAILED, OperationState.TIMED_OUT},
        )
        if mapped_state is OperationState.QUEUED:
            subject_value = snapshot.profile_id
            try:
                subject = OperationSubject("search_profile", subject_value)
            except ValueError:
                subject = OperationSubject(
                    "search_profile",
                    "profile-" + hashlib.sha256(subject_value.encode("utf-8")).hexdigest()[:16],
                )
            episode = OperationEpisode(
                episode_id=OperationEpisodeId(f"episode-{uuid4().hex}"),
                kind=OperationKind.TENDER_SEARCH,
                subject=subject,
                state=mapped_state,
                attempt=1,
                generation=snapshot.generation,
                revision=snapshot.revision,
                progress=OperationProgress.indeterminate(phase="queued"),
                started_at=occurred_at,
                updated_at=occurred_at,
                finished_at=None,
                reason=None,
                summary=None,
                diagnostic_id=None,
                capabilities=capabilities,
                parent_episode_id=None,
            )
            self._operation_episode = episode
            self.operation_episode_changed.emit(episode)
            return
        current = self._operation_episode
        if current is None or current.generation != snapshot.generation:
            return
        progress = current.progress
        if mapped_state is OperationState.RUNNING and progress.phase == "queued":
            progress = OperationProgress.indeterminate(phase="collect")
        outcome = transition_episode(
            current,
            OperationEvent(
                state=mapped_state,
                generation=snapshot.generation,
                revision=snapshot.revision,
                occurred_at=occurred_at,
                finished_at=occurred_at if mapped_state.terminal else None,
                progress=progress,
                reason=reason,
                capabilities=capabilities,
            ),
        )
        if outcome.accepted:
            self._operation_episode = outcome.episode
            self.operation_episode_changed.emit(outcome.episode)

    def _safe_worker_failure(
        self,
        kind: OperationKind,
        error_type: str,
        unsafe_message: str,
    ) -> str:
        normalized = error_type.casefold()
        reason = (
            OperationReasonCode.TIMEOUT
            if "timeout" in normalized
            else (
                OperationReasonCode.AUTH_REQUIRED
                if "credential" in normalized or "auth" in normalized
                else (
                    OperationReasonCode.PERMISSION_DENIED
                    if "permission" in normalized
                    else OperationReasonCode.INTERNAL_ERROR
                )
            )
        )
        feedback = self.operation_feedback_projector.project_reason(
            reason,
            episode_id=OperationEpisodeId(f"episode-{uuid4().hex}"),
            kind=kind,
            occurred_at=datetime.now(timezone.utc),
            unsafe_detail=unsafe_message,
            register_diagnostic=True,
        )
        return feedback.to_plain_text()

    def _finish_profile_dialog_run(
        self,
        *,
        result: object | None = None,
        error: str = "",
    ) -> None:
        profile_id = self._profile_dialog_run_id
        if not profile_id:
            return
        self._profile_dialog_run_id = ""
        if self._profiles_dialog is not None:
            self._profiles_dialog.set_search_busy(False)
            if error:
                self._profiles_dialog.set_status(
                    f"Поиск не выполнен: {error[:300]}",
                    error=True,
                )
            else:
                self._profiles_dialog.set_status("Поиск завершён. Результаты сохранены в реестр.")
                self._profiles_dialog.hide()
        if error:
            self.search_failed.emit(profile_id, error[:300])
        else:
            self.search_finished.emit(profile_id, result)

    def shutdown(self, timeout_ms: int = 3000) -> bool:
        """Cancel and join tender-owned background work within a fixed budget."""

        if timeout_ms < 0:
            raise ValueError("timeout_ms must be non-negative")
        if self._shutdown_complete:
            return True
        self._accepting_runs = False
        self.scheduler_ui_controller.shutdown()
        deadline = monotonic() + (timeout_ms / 1000)

        collector = self._collector_worker
        if collector is not None:
            self._transition_lifecycle(
                TenderSearchLifecycleState.CANCELLING,
                generation=collector.generation,
            )
            collector.cancel()
            self._abandon_if_queued(collector)

        provider_check = self._provider_check_worker
        if provider_check is not None:
            provider_check.cancel()
            self._abandon_if_queued(provider_check)

        completed = self._wait_for_worker(collector, deadline)
        completed = self._wait_for_worker(provider_check, deadline) and completed
        wait_for_done = getattr(self._thread_pool, "waitForDone", None)
        if completed and self._owns_thread_pool and callable(wait_for_done):
            remaining_ms = max(0, round((deadline - monotonic()) * 1000))
            completed = bool(wait_for_done(remaining_ms))

        if not completed:
            return False
        self._collector_worker = None
        self._provider_check_worker = None
        self._provider_check_ids = ()
        self._finish_profile_dialog_run(error="Операция поиска отменена.")
        self._transition_lifecycle(
            TenderSearchLifecycleState.CLOSED,
            generation=self._lifecycle_snapshot.generation,
            error_code=("search_cancelled" if collector is not None else ""),
            message=("Операция поиска отменена при закрытии приложения." if collector else ""),
        )
        self._shutdown_complete = True
        return True

    def _abandon_if_queued(self, worker: object) -> None:
        try_take = getattr(self._thread_pool, "tryTake", None)
        if callable(try_take) and bool(try_take(worker)):
            abandon = getattr(worker, "abandon", None)
            if callable(abandon):
                abandon()

    @staticmethod
    def _wait_for_worker(worker: object | None, deadline: float) -> bool:
        if worker is None:
            return True
        event = getattr(worker, "completion_event", None)
        wait = getattr(event, "wait", None)
        if not callable(wait):
            return True
        return bool(wait(timeout=max(0.0, deadline - monotonic())))

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
        rendered = self._safe_worker_failure(
            OperationKind.DOCUMENT_ANALYSIS,
            error_type,
            message,
        )
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
            rendered = self._safe_worker_failure(
                OperationKind.DOCUMENT_ANALYSIS,
                type(exc).__name__,
                str(exc),
            )
            if self._registry_dialog is not None:
                self._registry_dialog.set_status(
                    rendered,
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
            dialog.set_status(
                self._safe_worker_failure(
                    OperationKind.DOCUMENT_ANALYSIS,
                    type(exc).__name__,
                    str(exc),
                ),
                error=True,
            )

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
                    self._safe_worker_failure(
                        OperationKind.DOCUMENT_ANALYSIS,
                        type(exc).__name__,
                        str(exc),
                    ),
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
                    self._safe_worker_failure(
                        OperationKind.DOCUMENT_ANALYSIS,
                        type(exc).__name__,
                        str(exc),
                    ),
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
            dialog.ai_recheck_requested.connect(self.run_ai_recheck)
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
    def run_ai_recheck(self, registry_key: str) -> None:
        normalized = registry_key.strip()
        orchestrator = self.runtime.ai_orchestrator
        if not normalized or orchestrator is None:
            return
        dialog = self._full_analysis_dialogs.get(normalized)
        if normalized in self._ai_recheck_workers:
            if dialog is not None:
                dialog.message_label.setText("Повторная проверка AI уже выполняется.")
            return
        worker = _TenderAiRecheckWorker(orchestrator, normalized)
        worker.signals.succeeded.connect(self._on_ai_recheck_succeeded)
        worker.signals.failed.connect(self._on_ai_recheck_failed)
        self._ai_recheck_workers[normalized] = worker
        if dialog is not None:
            dialog.begin_ai_recheck()
        self.ai_recheck_started.emit(normalized)
        self._thread_pool.start(worker)

    @Slot(str, object)
    def _on_ai_recheck_succeeded(self, registry_key: str, result: object) -> None:
        self._ai_recheck_workers.pop(registry_key, None)
        dialog = self._full_analysis_dialogs.get(registry_key)
        if isinstance(result, TenderAiRecheckResult):
            if dialog is not None:
                dialog.set_ai_recheck_result(result)
            self.ai_recheck_finished.emit(registry_key, result)
            return
        if dialog is not None:
            dialog.set_ai_recheck_error()
        self.ai_recheck_failed.emit(
            registry_key,
            "Сервис вернул неподдерживаемый результат повторной проверки AI.",
        )

    @Slot(str, str, str)
    def _on_ai_recheck_failed(
        self,
        registry_key: str,
        _error_type: str,
        _message: str,
    ) -> None:
        self._ai_recheck_workers.pop(registry_key, None)
        if dialog := self._full_analysis_dialogs.get(registry_key):
            dialog.set_ai_recheck_error()
        self.ai_recheck_failed.emit(
            registry_key,
            "Повторная проверка AI временно недоступна.",
        )

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
        rendered = self._safe_worker_failure(
            OperationKind.DOCUMENT_ANALYSIS,
            error_type,
            message,
        )
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
        rendered = self._safe_worker_failure(
            OperationKind.DOCUMENT_ANALYSIS,
            error_type,
            message,
        )
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
        rendered = self._safe_worker_failure(
            OperationKind.DOCUMENT_ANALYSIS,
            error_type,
            message,
        )
        dialog = self._analysis_dialogs.get(registry_key)
        if dialog is not None:
            dialog.set_analysis_error(rendered)
        self.analysis_failed.emit(registry_key, rendered)

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


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


__all__ = [
    "TenderSearchLifecycleSnapshot",
    "TenderSearchLifecycleState",
    "TenderSearchUiController",
    "safe_manual_health_error_message",
]
