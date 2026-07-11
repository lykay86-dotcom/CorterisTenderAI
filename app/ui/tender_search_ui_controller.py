"""Qt integration controller for tender-search profiles and results."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMainWindow, QMenu, QWidget

from app.tenders.document_storage import (
    TenderDocumentDownloadResult,
    TenderDocumentDownloadService,
)
from app.tenders.models import UnifiedTender
from app.tenders.search_profile_runner import (
    TenderSearchProfileRun,
    TenderSearchProfileRunner,
)
from app.tenders.tender_registry import tender_registry_key
from app.tenders.search_runtime import (
    TenderSearchRuntime,
    create_tender_search_runtime,
)
from app.ui.tender_documents_dialog import TenderDocumentsDialog
from app.ui.tender_registry_dialog import TenderRegistryDialog
from app.ui.tender_search_profiles_dialog import (
    TenderSearchProfilesDialog,
)
from app.ui.tender_search_results_dialog import (
    TenderSearchResultsDialog,
)
from app.ui.theme.colors import ThemeName


class _ThreadPoolLike(Protocol):
    def start(self, runnable: QRunnable) -> None:
        ...


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


class TenderSearchUiController(QObject):
    """Install tender search in the main window and run it off-thread."""

    search_started = Signal(str)
    search_finished = Signal(str, object)
    search_failed = Signal(str, str)
    document_download_started = Signal(str)
    document_download_finished = Signal(str, object)
    document_download_failed = Signal(str, str)

    def __init__(
        self,
        data_directory: str | Path,
        *,
        runtime: TenderSearchRuntime | None = None,
        theme: ThemeName | str = ThemeName.DARK,
        thread_pool: _ThreadPoolLike | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self.runtime = runtime or create_tender_search_runtime(
            data_directory
        )
        try:
            self._theme = ThemeName(theme)
        except (TypeError, ValueError, AttributeError):
            self._theme = ThemeName.DARK
        self._thread_pool = thread_pool or QThreadPool.globalInstance()
        self._profiles_dialog: TenderSearchProfilesDialog | None = None
        self._registry_dialog: TenderRegistryDialog | None = None
        self._result_dialogs: list[TenderSearchResultsDialog] = []
        self._document_dialogs: dict[str, TenderDocumentsDialog] = {}
        self._active_workers: dict[str, _TenderSearchWorker] = {}
        self._document_workers: dict[
            str,
            _TenderDocumentWorker,
        ] = {}
        # PySide6 can release a QMenu wrapper created by QMenuBar.addMenu()
        # when no Python-side strong reference is retained, especially with
        # the offscreen test platform. Keep the menu alive with the controller.
        self._tender_menu: QMenu | None = None

        self.action = QAction(
            "Профили и поиск тендеров…",
            self,
        )
        self.action.setObjectName("actionTenderSearchProfiles")
        self.action.setShortcut(QKeySequence("Ctrl+Shift+F"))
        self.action.setStatusTip(
            "Открыть профили и запустить поиск тендеров"
        )
        self.action.triggered.connect(
            self.open_profiles_dialog
        )

        self.registry_action = QAction(
            "Реестр найденных тендеров…",
            self,
        )
        self.registry_action.setObjectName("actionTenderRegistry")
        self.registry_action.setShortcut(QKeySequence("Ctrl+Shift+R"))
        self.registry_action.setStatusTip(
            "Открыть локальный реестр найденных тендеров"
        )
        self.registry_action.setEnabled(
            self.runtime.tender_registry is not None
        )
        self.registry_action.triggered.connect(
            self.open_registry_dialog
        )

    @property
    def profiles_dialog(self) -> TenderSearchProfilesDialog | None:
        return self._profiles_dialog

    @property
    def registry_dialog(self) -> TenderRegistryDialog | None:
        return self._registry_dialog

    @property
    def result_dialogs(self) -> tuple[TenderSearchResultsDialog, ...]:
        return tuple(self._result_dialogs)

    @property
    def document_dialogs(self) -> tuple[TenderDocumentsDialog, ...]:
        return tuple(self._document_dialogs.values())

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
        else:
            # Fallback for a QWidget-based shell: shortcuts still work.
            if self.action not in main_window.actions():
                main_window.addAction(self.action)
            if self.registry_action not in main_window.actions():
                main_window.addAction(self.registry_action)

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
        parent_widget = (
            parent if isinstance(parent, QWidget) else None
        )

        if self._profiles_dialog is None:
            self._profiles_dialog = TenderSearchProfilesDialog(
                self.runtime.repository,
                theme=self._theme,
                parent=parent_widget,
            )
            self._profiles_dialog.profile_run_requested.connect(
                self.run_profile
            )

        self._profiles_dialog.refresh_profiles()
        self._profiles_dialog.open()
        self._profiles_dialog.raise_()
        self._profiles_dialog.activateWindow()

    @Slot()
    def open_registry_dialog(self) -> None:
        repository = self.runtime.tender_registry
        if repository is None:
            self._set_profiles_status(
                "Локальный реестр тендеров недоступен."
            )
            return

        parent = self.parent()
        parent_widget = (
            parent if isinstance(parent, QWidget) else None
        )
        if self._registry_dialog is None:
            self._registry_dialog = TenderRegistryDialog(
                repository,
                theme=self._theme,
                parent=parent_widget,
            )
            self._registry_dialog.profiles_requested.connect(
                self.open_profiles_dialog
            )
            self._registry_dialog.documents_requested.connect(
                self.open_registry_documents
            )

        self._registry_dialog.refresh_records()
        self._registry_dialog.open()
        self._registry_dialog.raise_()
        self._registry_dialog.activateWindow()

    @Slot(str)
    def run_profile(self, profile_id: str) -> None:
        normalized = profile_id.strip().casefold()
        if not normalized:
            return

        if normalized in self._active_workers:
            self._set_profiles_status(
                "Этот профиль уже выполняется. Дождитесь завершения."
            )
            return

        worker = _TenderSearchWorker(
            self.runtime.runner,
            normalized,
        )
        worker.signals.succeeded.connect(
            self._on_search_succeeded
        )
        worker.signals.failed.connect(
            self._on_search_failed
        )
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
            self._profiles_dialog.set_status(
                "Поиск завершён. Открыта таблица результатов."
            )
            self._profiles_dialog.hide()

        if not isinstance(run, TenderSearchProfileRun):
            self._on_search_failed(
                profile_id,
                "TypeError",
                "Поисковый сервис вернул неподдерживаемый результат.",
            )
            return

        parent = self.parent()
        parent_widget = (
            parent if isinstance(parent, QWidget) else None
        )
        dialog = TenderSearchResultsDialog(
            run,
            theme=self._theme,
            parent=parent_widget,
        )
        dialog.rerun_requested.connect(self.run_profile)
        dialog.profiles_requested.connect(
            self.open_profiles_dialog
        )
        dialog.documents_requested.connect(
            self.open_tender_documents
        )
        dialog.finished.connect(
            lambda _result, current=dialog: (
                self._forget_result_dialog(current)
            )
        )
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
            self._set_document_status(
                "Локальный реестр тендеров недоступен."
            )
            return

        tender = repository.get_tender(registry_key)
        if tender is None:
            self._set_document_status(
                "Не удалось восстановить карточку закупки из реестра."
            )
            return
        self.open_tender_documents(tender)

    @Slot(object)
    def open_tender_documents(self, tender: object) -> None:
        if not isinstance(tender, UnifiedTender):
            self._set_document_status(
                "Выбрана неподдерживаемая карточка закупки."
            )
            return

        store = self.runtime.document_store
        service = self.runtime.document_service
        if store is None or service is None:
            self._set_document_status(
                "Локальное хранилище документации недоступно."
            )
            return

        registry_key = tender_registry_key(tender)
        dialog = self._document_dialogs.get(registry_key)
        if dialog is None:
            parent = self.parent()
            parent_widget = (
                parent if isinstance(parent, QWidget) else None
            )
            dialog = TenderDocumentsDialog(
                tender,
                store,
                theme=self._theme,
                parent=parent_widget,
            )
            dialog.download_requested.connect(
                self.download_tender_documents
            )
            dialog.finished.connect(
                lambda _result, key=registry_key, current=dialog: (
                    self._forget_document_dialog(key, current)
                )
            )
            self._document_dialogs[registry_key] = dialog

        dialog.refresh_documents()
        dialog.open()
        dialog.raise_()
        dialog.activateWindow()

        # The button in results/registry explicitly means download, so start
        # the background operation immediately after opening the local view.
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
            self._set_document_status(
                "Сервис загрузки документации недоступен."
            )
            return

        registry_key = tender_registry_key(tender)
        dialog = self._document_dialogs.get(registry_key)
        if registry_key in self._document_workers:
            if dialog is not None:
                dialog.set_status(
                    "Документация этой закупки уже загружается."
                )
            return

        worker = _TenderDocumentWorker(
            service,
            tender,
            force=force,
        )
        worker.signals.succeeded.connect(
            self._on_document_download_succeeded
        )
        worker.signals.failed.connect(
            self._on_document_download_failed
        )
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
        if (
            dialog is not None
            and isinstance(result, TenderDocumentDownloadResult)
        ):
            dialog.set_download_result(result)
        elif dialog is not None:
            dialog.set_download_error(
                "Сервис вернул неподдерживаемый результат."
            )

        if self._registry_dialog is not None:
            self._registry_dialog.refresh_records()

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
            if (
                menu.objectName() == "tendersMenu"
                or title == "тендеры"
            ):
                return menu

        menu = menu_bar.addMenu("Тендеры")
        menu.setObjectName("tendersMenu")
        return menu


__all__ = ["TenderSearchUiController"]
