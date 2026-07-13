"""Qt timer and actions for automatic collector runs."""

from __future__ import annotations

from collections.abc import Callable
import logging
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow,
    QMenu,
    QToolBar,
    QWidget,
)

from app.tenders.collector.models import CollectorRunResult
from app.tenders.collector.notifications import (
    CollectorNotification,
    CollectorNotificationRepository,
    CollectorNotificationService,
)
from app.tenders.collector.provider_control import (
    CollectorProviderManager,
)
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.collector.scheduler import (
    CollectorScheduleRepository,
    CollectorScheduleSettings,
    CollectorScheduler,
    ScheduledCollectorRequest,
)
from app.tenders.search_profile_repository import (
    TenderSearchProfileRepository,
)
from app.ui.tender_collector_notifications_dialog import (
    TenderCollectorNotificationsDialog,
)
from app.ui.tender_collector_schedule_dialog import (
    TenderCollectorScheduleDialog,
)
from app.ui.theme.colors import ThemeName


LOGGER = logging.getLogger("corteris.tenders.collector.scheduler_ui")


StartCollectorCallback = Callable[
    [str, object],
    bool,
]
BusyCallback = Callable[[], bool]


class TenderCollectorSchedulerUiController(QObject):
    """Own scheduler timer, dialogs and in-app notifications."""

    notification_created = Signal(object)

    def __init__(
        self,
        data_directory: str | Path,
        *,
        profile_repository: TenderSearchProfileRepository,
        provider_manager: CollectorProviderManager,
        start_collector: StartCollectorCallback,
        is_collector_busy: BusyCallback,
        collector_finished_signal: object,
        collector_failed_signal: object,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.data_directory = Path(data_directory).expanduser()
        self.profile_repository = profile_repository
        self.provider_manager = provider_manager
        self.start_collector_callback = start_collector
        self.is_collector_busy = is_collector_busy
        self.scheduler = CollectorScheduler(
            CollectorScheduleRepository(self.data_directory / "collector_schedule.json")
        )
        self.freshness_repository = CollectorStateRepository(
            self.data_directory / "tender_registry.sqlite3"
        )
        self.notification_repository = CollectorNotificationRepository(
            self.data_directory / "collector_notifications.json"
        )
        self.notification_service = CollectorNotificationService()
        self._theme = ThemeName(theme)
        self._main_window: QWidget | None = None
        self._schedule_dialog: TenderCollectorScheduleDialog | None = None
        self._notifications_dialog: TenderCollectorNotificationsDialog | None = None
        self._scheduled_active = False

        self.schedule_action = QAction(
            "Планировщик тендеров…",
            self,
        )
        self.schedule_action.setObjectName("actionTenderCollectorSchedule")
        self.schedule_action.setShortcut(QKeySequence("Ctrl+Shift+P"))
        self.schedule_action.triggered.connect(self.open_schedule_dialog)

        self.notifications_action = QAction(
            "Уведомления сборщика…",
            self,
        )
        self.notifications_action.setObjectName("actionTenderCollectorNotifications")
        self.notifications_action.setShortcut(QKeySequence("Ctrl+Shift+N"))
        self.notifications_action.triggered.connect(self.open_notifications_dialog)

        self.timer = QTimer(self)
        self.timer.setInterval(30_000)
        self.timer.timeout.connect(self.poll)

        collector_finished_signal.connect(self.on_collector_finished)
        collector_failed_signal.connect(self.on_collector_failed)
        self._update_notification_action()

    def install_on_main_window(
        self,
        main_window: QWidget,
        *,
        menu: QMenu | None = None,
        toolbar: QToolBar | None = None,
    ) -> None:
        self._main_window = main_window
        if menu is not None:
            if self.schedule_action not in menu.actions():
                menu.addAction(self.schedule_action)
            if self.notifications_action not in menu.actions():
                menu.addAction(self.notifications_action)
        if toolbar is not None:
            if self.schedule_action not in toolbar.actions():
                toolbar.addAction(self.schedule_action)
            if self.notifications_action not in toolbar.actions():
                toolbar.addAction(self.notifications_action)
        if menu is None and toolbar is None:
            if self.schedule_action not in main_window.actions():
                main_window.addAction(self.schedule_action)
            if self.notifications_action not in main_window.actions():
                main_window.addAction(self.notifications_action)

        if not self.timer.isActive():
            self.timer.start()
            QTimer.singleShot(
                1500,
                self.check_startup_run,
            )

    @property
    def schedule_dialog(
        self,
    ) -> TenderCollectorScheduleDialog | None:
        return self._schedule_dialog

    @property
    def notifications_dialog(
        self,
    ) -> TenderCollectorNotificationsDialog | None:
        return self._notifications_dialog

    @Slot()
    def open_schedule_dialog(self) -> None:
        parent = self._main_window if isinstance(self._main_window, QWidget) else None
        if self._schedule_dialog is None:
            self._schedule_dialog = TenderCollectorScheduleDialog(
                theme=self._theme,
                parent=parent,
            )
            self._schedule_dialog.save_requested.connect(self.save_settings)
            self._schedule_dialog.run_now_requested.connect(self.run_now)
            self._schedule_dialog.notifications_requested.connect(self.open_notifications_dialog)
        self.refresh_schedule_dialog()
        self._schedule_dialog.open()
        self._schedule_dialog.raise_()
        self._schedule_dialog.activateWindow()

    @Slot()
    def refresh_schedule_dialog(self) -> None:
        if self._schedule_dialog is None:
            return
        settings, state = self.scheduler.snapshot()
        profiles = self.profile_repository.list_profiles(include_disabled=False)
        providers = self.provider_manager.states()
        self._schedule_dialog.set_configuration(
            settings,
            state,
            profiles,
            providers,
        )

    @Slot(object)
    def save_settings(self, value: object) -> None:
        if not isinstance(
            value,
            CollectorScheduleSettings,
        ):
            return
        try:
            self.scheduler.update_settings(value)
        except Exception as exc:
            if self._schedule_dialog is not None:
                self._schedule_dialog.set_status(
                    f"Не удалось сохранить: {exc}",
                    error=True,
                )
            return
        self.refresh_schedule_dialog()
        if self._schedule_dialog is not None:
            self._schedule_dialog.set_status("Расписание сохранено.")

    @Slot(str, object)
    def run_now(
        self,
        profile_id: str,
        provider_ids: object,
    ) -> None:
        started = self.start_collector_callback(
            profile_id,
            provider_ids,
        )
        if self._schedule_dialog is not None:
            self._schedule_dialog.set_status(
                (
                    "Сбор запущен."
                    if started
                    else (
                        "Сбор не запущен. Проверьте профиль, "
                        "источники или дождитесь завершения "
                        "текущей операции."
                    )
                ),
                error=not started,
            )

    @Slot()
    def check_startup_run(self) -> None:
        request = self.scheduler.startup_request()
        if request is not None:
            self._start_scheduled(request)

    @Slot()
    def poll(self) -> None:
        freshness_due_at = ""
        try:
            due_items = self.freshness_repository.list_due_reverification(limit=1)
            if due_items:
                freshness_due_at = due_items[0].verification_due_at or due_items[0].updated_at
        except Exception as exc:
            # The regular schedule must remain operational even when the
            # registry is temporarily locked or has not been created yet.
            LOGGER.warning(
                "Freshness queue is temporarily unavailable: %s",
                exc,
            )
            freshness_due_at = ""
        request = self.scheduler.poll(
            busy=self.is_collector_busy(),
            freshness_due_at=freshness_due_at,
        )
        if request is not None:
            self._start_scheduled(request)
        self.refresh_schedule_dialog()

    def _start_scheduled(
        self,
        request: ScheduledCollectorRequest,
    ) -> None:
        if self.is_collector_busy():
            return
        self.scheduler.mark_started(request)
        self._scheduled_active = True
        started = self.start_collector_callback(
            request.profile_id,
            request.provider_ids,
        )
        if not started:
            self._scheduled_active = False
            self.scheduler.mark_finished(
                "start_rejected",
                error=("Запуск отклонён: профиль или источники недоступны."),
            )
            self.refresh_schedule_dialog()

    @Slot(object)
    def on_collector_finished(
        self,
        result: object,
    ) -> None:
        if not isinstance(result, CollectorRunResult):
            return
        if self._scheduled_active:
            self.scheduler.mark_finished(result.status.value)
            self._scheduled_active = False
        settings, _ = self.scheduler.snapshot()
        notifications = self.notification_service.for_result(
            result,
            settings,
        )
        self._publish(notifications)
        self.refresh_schedule_dialog()

    @Slot(str)
    def on_collector_failed(
        self,
        message: str,
    ) -> None:
        if self._scheduled_active:
            self.scheduler.mark_finished(
                "failed",
                error=message,
            )
            self._scheduled_active = False
        settings, _ = self.scheduler.snapshot()
        self._publish(
            self.notification_service.for_failure(
                message,
                settings,
            )
        )
        self.refresh_schedule_dialog()

    def _publish(
        self,
        notifications: tuple[
            CollectorNotification,
            ...,
        ],
    ) -> None:
        if not notifications:
            return
        self.notification_repository.add_many(notifications)
        self._update_notification_action()
        self.refresh_notifications_dialog()
        for item in notifications:
            self.notification_created.emit(item)
        last = notifications[0]
        if isinstance(self._main_window, QMainWindow):
            self._main_window.statusBar().showMessage(
                last.message,
                15_000,
            )

    @Slot()
    def open_notifications_dialog(self) -> None:
        parent = self._main_window if isinstance(self._main_window, QWidget) else None
        if self._notifications_dialog is None:
            self._notifications_dialog = TenderCollectorNotificationsDialog(
                theme=self._theme,
                parent=parent,
            )
            self._notifications_dialog.mark_all_read_requested.connect(
                self.mark_all_notifications_read
            )
            self._notifications_dialog.registry_requested.connect(self._open_registry_via_parent)
        self.refresh_notifications_dialog()
        self._notifications_dialog.open()
        self._notifications_dialog.raise_()
        self._notifications_dialog.activateWindow()

    @Slot()
    def refresh_notifications_dialog(self) -> None:
        if self._notifications_dialog is not None:
            self._notifications_dialog.set_notifications(
                self.notification_repository.list_notifications()
            )

    @Slot()
    def mark_all_notifications_read(self) -> None:
        self.notification_repository.mark_all_read()
        self._update_notification_action()
        self.refresh_notifications_dialog()

    def _update_notification_action(self) -> None:
        unread = self.notification_repository.unread_count()
        self.notifications_action.setText(
            (f"Уведомления сборщика ({unread})…" if unread else "Уведомления сборщика…")
        )

    def _open_registry_via_parent(self) -> None:
        parent = self.parent()
        method = getattr(
            parent,
            "open_registry_dialog",
            None,
        )
        if callable(method):
            method()


__all__ = ["TenderCollectorSchedulerUiController"]
