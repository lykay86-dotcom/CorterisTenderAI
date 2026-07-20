"""Expected-red notification adapter, dedupe and exact-action contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from importlib import import_module
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QMainWindow, QMenu, QToolBar

from app.tenders.collector.notifications import (
    CollectorNotification,
    CollectorNotificationKind,
)
from app.tenders.search_profile_repository import TenderSearchProfileRepository
from app.ui.tender_collector_scheduler_controller import TenderCollectorSchedulerUiController


NOW = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
MALICIOUS = (
    "RM151_NOTIFICATION_SECRET C:\\Users\\private\\report.txt "
    "https://example.invalid/?token=secret <script>unsafe</script>"
)


def _modules():
    return (
        import_module("app.operations.contracts"),
        import_module("app.operations.diagnostics"),
        import_module("app.operations.notifications"),
    )


def _envelope(*, revision: int = 1):
    contracts, _, notifications = _modules()
    subject = contracts.OperationSubject("collector_run", "run-151")
    action = notifications.NotificationAction(
        action_id="open-run",
        route_id="workspace.tenders.registry",
        subject=subject,
        freshness_token="run-151:revision-7",
        label=contracts.SafeText("РћС‚РєСЂС‹С‚СЊ СЂРµРµСЃС‚СЂ"),
        accessible_label=contracts.SafeText("РћС‚РєСЂС‹С‚СЊ СЃР±РѕСЂ run-151 РІ СЂРµРµСЃС‚СЂРµ"),
    )
    return notifications.NotificationEnvelope(
        notification_id="notification-151-a",
        event_id="event-151-a",
        episode_id=contracts.OperationEpisodeId("episode-151-a"),
        correlation_id=contracts.DiagnosticCorrelationId("diagnostic-151-a"),
        kind=notifications.NotificationKind.FAILURE,
        severity=contracts.FeedbackSeverity.ERROR,
        title=contracts.SafeText("РћРїРµСЂР°С†РёСЏ РЅРµ Р·Р°РІРµСЂС€РµРЅР°"),
        summary=contracts.SafeText(
            "РћС‚РєСЂРѕР№С‚Рµ РґРёР°РіРЅРѕСЃС‚РёРєСѓ Рё РїРѕРІС‚РѕСЂРёС‚Рµ."
        ),
        subject=subject,
        actions=(action,),
        created_at=NOW,
        revision=revision,
        terminal_state=contracts.OperationState.FAILED,
        read_at=None,
        dismissed_at=None,
    )


def test_legacy_adapter_sanitizes_rows_and_future_schema_fails_closed() -> None:
    contracts, diagnostics, notifications = _modules()
    registry = diagnostics.DiagnosticRegistry(
        max_records=4,
        id_factory=lambda: "diagnostic-legacy-151",
    )
    adapter = notifications.LegacyCollectorNotificationAdapter(registry=registry)
    legacy = CollectorNotification(
        id="legacy-151",
        created_at=NOW.isoformat(),
        title=MALICIOUS,
        message=MALICIOUS,
        kind=CollectorNotificationKind.ERROR,
        run_id="run-151",
    )

    envelope = adapter.adapt(legacy, schema_version=1)

    assert MALICIOUS not in envelope.title.value
    assert MALICIOUS not in envelope.summary.value
    assert envelope.subject == contracts.OperationSubject("collector_run", "run-151")
    assert envelope.correlation_id is not None
    assert registry.get(envelope.correlation_id) is not None
    with pytest.raises(notifications.UnsupportedNotificationSchema):
        adapter.adapt(legacy, schema_version=999)


def test_dedupe_revision_preserves_read_and_dismiss_state() -> None:
    _, _, notifications = _modules()
    ledger = notifications.NotificationLedger(max_items=200)
    original = _envelope(revision=1)

    assert ledger.upsert(original) is notifications.NotificationDisposition.INSERTED
    assert ledger.upsert(original) is notifications.NotificationDisposition.DUPLICATE
    read = ledger.mark_read(original.notification_id, occurred_at=NOW)
    dismissed = ledger.dismiss(original.notification_id, occurred_at=NOW)
    assert read.read_at == NOW
    assert dismissed.dismissed_at == NOW

    revised = _envelope(revision=2)
    assert ledger.upsert(revised) is notifications.NotificationDisposition.REVISED
    stored = ledger.get(original.notification_id)
    assert stored is not None
    assert stored.revision == 2
    assert stored.read_at == NOW
    assert stored.dismissed_at == NOW
    assert ledger.active() == ()


def test_equal_revision_conflict_fails_closed_and_exact_action_checks_freshness() -> None:
    contracts, _, notifications = _modules()
    ledger = notifications.NotificationLedger(max_items=200)
    envelope = _envelope()
    ledger.upsert(envelope)
    conflicting = notifications.NotificationEnvelope(
        **{
            **envelope.to_dict(native=True),
            "summary": contracts.SafeText("Different safe summary"),
        }
    )

    assert ledger.upsert(conflicting) is notifications.NotificationDisposition.CONFLICT
    action = notifications.resolve_notification_action(
        envelope,
        action_id="open-run",
        current_subject=contracts.OperationSubject("collector_run", "run-151"),
        current_freshness_token="run-151:revision-7",
    )
    assert action.action_id == "open-run"

    with pytest.raises(notifications.StaleNotificationAction):
        notifications.resolve_notification_action(
            envelope,
            action_id="open-run",
            current_subject=contracts.OperationSubject("collector_run", "run-152"),
            current_freshness_token="run-151:revision-7",
        )


class _Signals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class _Providers:
    def states(self) -> tuple[object, ...]:
        return ()


def test_j08_existing_controller_owns_one_adapter_and_one_canonical_action(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    profiles = TenderSearchProfileRepository(tmp_path / "profiles.json")
    profiles.initialize()
    signals = _Signals()
    window = QMainWindow()
    menu = QMenu(window)
    toolbar = QToolBar(window)
    controller = TenderCollectorSchedulerUiController(
        tmp_path,
        profile_repository=profiles,
        provider_manager=_Providers(),
        start_collector=lambda _profile, _providers: True,
        is_collector_busy=lambda: False,
        collector_finished_signal=signals.finished,
        collector_failed_signal=signals.failed,
        parent=window,
    )
    controller.install_on_main_window(window, menu=menu, toolbar=toolbar)

    assert controller.notification_envelope_adapter is not None
    assert controller.notifications_action in menu.actions()
    assert controller.notifications_action in toolbar.actions()
    assert controller.notifications_action.shortcut().toString() == "Ctrl+Shift+N"

    controller.shutdown()
    window.close()
    app.processEvents()
