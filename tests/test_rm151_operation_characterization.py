"""Passing characterization of operation-feedback seams inherited by RM-151.

Known unsafe behavior is named explicitly here so the later expected-red tests can
require its replacement without pretending that the legacy behavior is acceptable.
"""

from __future__ import annotations

from datetime import datetime
import inspect
import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QMainWindow, QMenu, QToolBar

from app.core.crash_reporting import CrashReportService
from app.tenders.collector.notifications import (
    CollectorNotification,
    CollectorNotificationKind,
    CollectorNotificationRepository,
    CollectorNotificationService,
)
from app.tenders.search_profile_repository import TenderSearchProfileRepository
from app.ui.controllers.dashboard_controller import DashboardController
from app.ui.modern_main_window import ModernMainWindow
from app.ui.pages.business_workflow_page import BusinessWorkflowPage
from app.ui.tender_collector_scheduler_controller import (
    TenderCollectorSchedulerUiController,
)
from app.ui.tender_search_ui_controller import TenderSearchLifecycleState
from tests.test_rm140_search_lifecycle import QueuedThreadPool, _controller


MALICIOUS_MARKER = "RM151_RAW_SECRET_SENTINEL"


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


class _CollectorSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class _ProviderManager:
    def states(self) -> tuple[object, ...]:
        return ()


def _notification(identifier: str, *, created_at: str = "2026-07-20T10:00:00+03:00"):
    return CollectorNotification(
        id=identifier,
        created_at=created_at,
        title="Characterization",
        message="Existing collector notification",
        kind=CollectorNotificationKind.INFO,
        run_id="run-151",
    )


def test_rm140_generation_revision_close_and_late_result_contract_is_inherited(tmp_path) -> None:
    pool = QueuedThreadPool()
    controller = _controller(tmp_path, pool)

    assert controller.try_start_collector("all-corteris", ("eis",))
    queued = controller.lifecycle_snapshot
    worker = pool.runnables[0]
    assert queued.state is TenderSearchLifecycleState.QUEUED
    assert queued.generation == 1

    assert controller.shutdown(timeout_ms=50)
    closed = controller.lifecycle_snapshot
    assert closed.state is TenderSearchLifecycleState.CLOSED
    assert closed.revision > queued.revision

    worker.run()
    assert controller.lifecycle_snapshot == closed
    assert controller.shutdown(timeout_ms=50)


def test_notification_v1_deduplicates_caps_and_marks_all_read(tmp_path) -> None:
    repository = CollectorNotificationRepository(
        tmp_path / "collector_notifications.json",
        max_items=2,
    )
    first = _notification("n-1", created_at="2026-07-20T10:00:00+03:00")
    newer = _notification("n-2", created_at="2026-07-20T11:00:00+03:00")
    newest = _notification("n-3", created_at="2026-07-20T12:00:00+03:00")

    repository.add_many((first, newer, newest, newest))

    assert tuple(item.id for item in repository.list_notifications()) == ("n-3", "n-2")
    assert repository.unread_count() == 2
    assert repository.mark_all_read() == 2
    assert repository.unread_count() == 0
    payload = json.loads(repository.path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1


def test_known_gap_notification_v1_has_no_single_dismiss_or_action_identity(tmp_path) -> None:
    repository = CollectorNotificationRepository(tmp_path / "collector_notifications.json")

    assert not hasattr(repository, "dismiss")
    assert not hasattr(repository, "resolve_action")
    assert set(_notification("n-1").to_dict()) == {
        "id",
        "created_at",
        "title",
        "message",
        "kind",
        "read",
        "run_id",
    }


def test_known_gap_corrupt_and_future_notification_store_fail_open_to_legacy_views(
    tmp_path,
) -> None:
    path = tmp_path / "collector_notifications.json"
    repository = CollectorNotificationRepository(path)
    path.write_text("{damaged", encoding="utf-8")
    assert repository.list_notifications() == ()

    path.write_text(
        json.dumps(
            {
                "schema_version": 999,
                "notifications": [_notification("future-visible").to_dict()],
            }
        ),
        encoding="utf-8",
    )
    assert tuple(item.id for item in repository.list_notifications()) == ("future-visible",)


def test_menu_toolbar_and_shortcut_share_the_same_notification_action(tmp_path) -> None:
    app = _app()
    profiles = TenderSearchProfileRepository(tmp_path / "profiles.json")
    profiles.initialize()
    signals = _CollectorSignals()
    window = QMainWindow()
    menu = QMenu(window)
    toolbar = QToolBar(window)
    controller = TenderCollectorSchedulerUiController(
        tmp_path,
        profile_repository=profiles,
        provider_manager=_ProviderManager(),
        start_collector=lambda _profile, _providers: True,
        is_collector_busy=lambda: False,
        collector_finished_signal=signals.finished,
        collector_failed_signal=signals.failed,
        parent=window,
    )

    controller.install_on_main_window(window, menu=menu, toolbar=toolbar)

    action = controller.notifications_action
    assert action.objectName() == "actionTenderCollectorNotifications"
    assert action in menu.actions()
    assert action in toolbar.actions()
    assert action.shortcut().toString() == "Ctrl+Shift+N"
    assert (
        inspect.getsource(ModernMainWindow._register_navigation_destinations).count(
            '"notifications_action"'
        )
        == 1
    )

    controller.shutdown()
    assert not controller.timer.isActive()
    window.close()
    app.processEvents()


def test_crash_report_keeps_local_correlation_and_redacts_common_secret(tmp_path) -> None:
    service = CrashReportService(tmp_path / "crashes")
    try:
        raise RuntimeError(f"api_key={MALICIOUS_MARKER}")
    except RuntimeError:
        exc_type, exc_value, traceback_object = sys.exc_info()

    assert exc_type is not None
    assert exc_value is not None
    result = service.create_report(
        exc_type,
        exc_value,
        traceback_object,
        origin="rm151-characterization",
        created_at=datetime(2026, 7, 20, 12, 0),
    )
    inspection = service.inspect_report(result.path)
    details = service.read_report(result.path)

    assert inspection.valid
    assert details.crash_id == result.crash_id
    assert details.origin == "rm151-characterization"
    assert MALICIOUS_MARKER not in details.exception_message
    assert "<REDACTED>" in details.exception_message


def test_backup_recovery_requires_cancel_default_confirmation_before_mutation() -> None:
    source = inspect.getsource(BusinessWorkflowPage._recover_latest_database_backup)

    confirmation = source.index("QMessageBox.warning")
    mutation = source.index("self.database_health_service.recover_latest(")
    assert confirmation < mutation
    assert source.count("QMessageBox.StandardButton.Cancel") >= 2
    assert "if answer != QMessageBox.StandardButton.Yes" in source


def test_known_gap_legacy_failure_notification_preserves_raw_payload() -> None:
    payload = (
        f"{MALICIOUS_MARKER} C:\\Users\\private\\report.txt "
        "https://example.invalid/?token=secret <b>unsafe</b>"
    )
    settings_type = (
        inspect.signature(CollectorNotificationService.for_failure)
        .parameters["settings"]
        .annotation
    )
    assert settings_type  # Document the typed owner without constructing a second service.

    from app.tenders.collector.scheduler import CollectorScheduleSettings

    rendered = (
        CollectorNotificationService()
        .for_failure(
            payload,
            CollectorScheduleSettings(),
            run_id="legacy-leak",
        )[0]
        .message
    )

    assert MALICIOUS_MARKER in rendered
    assert "C:\\Users\\private\\report.txt" in rendered
    assert "token=secret" in rendered
    assert "<b>unsafe</b>" in rendered


def test_migrated_dashboard_and_recovery_no_longer_present_raw_exceptions() -> None:
    dashboard_source = inspect.getsource(DashboardController._handle_refresh_failure)
    recovery_source = inspect.getsource(BusinessWorkflowPage._recover_latest_database_backup)

    assert "{error}" not in dashboard_source
    assert "str(exc)" not in recovery_source
