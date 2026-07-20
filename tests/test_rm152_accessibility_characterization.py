"""RM-152 characterization of inherited accessibility and focus owners."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.operations import (
    AnnouncementCoalescer,
    OperationCapabilities,
    OperationEpisode,
    OperationEpisodeId,
    OperationKind,
    OperationProgress,
    OperationState,
    OperationSubject,
    SafeText,
)
from app.tenders.provider_credentials import CredentialState, CredentialStateResult
from app.ui.dashboard.keyboard_navigation import DEFAULT_DASHBOARD_SHORTCUTS
from app.ui.navigation import NavigationCause, RouteId, RouteRequest
from app.ui.provider_credentials_dialog import ProviderCredentialsDialog
from app.ui.theme.colors import DARK_PALETTE, LIGHT_PALETTE
from app.ui.theme.contrast import approved_contrast_pairs
from app.ui.widgets.button import PrimaryButton
from app.ui.widgets.dashboard_layout import DashboardLayout
from app.ui.widgets.topbar import TopBar


NOW = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_inherited_route_history_restores_one_live_stable_focus_token() -> None:
    app = _app()
    layout = DashboardLayout()
    dashboard = QWidget()
    dashboard_layout = QVBoxLayout(dashboard)
    origin = QPushButton("Открыть поиск", dashboard)
    origin.setObjectName("DashboardSearchOrigin")
    dashboard_layout.addWidget(origin)
    tenders = QWidget()
    layout.add_page("dashboard", "Рабочий стол", dashboard)
    layout.add_page("tenders", "Тендеры", tenders)
    layout.show()
    app.processEvents()

    origin.setFocus(Qt.FocusReason.ShortcutFocusReason)
    layout.navigate(
        RouteRequest(
            RouteId.TENDERS,
            cause=NavigationCause.QUICK_ACTION,
            focus_token="DashboardSearchOrigin",
        )
    )
    returned = layout.back()
    app.processEvents()

    assert returned.succeeded
    assert layout.pages.currentWidget() is dashboard
    assert app.focusWidget() is origin


def test_inherited_dashboard_shortcut_catalog_is_unique_and_context_bounded() -> None:
    keys = tuple(item.key for item in DEFAULT_DASHBOARD_SHORTCUTS)
    sequences = tuple(item.sequence for item in DEFAULT_DASHBOARD_SHORTCUTS)

    assert len(keys) == len(set(keys))
    assert len(sequences) == len(set(sequences))
    assert sequences == (
        "Ctrl+F",
        "Ctrl+A",
        "Ctrl+K",
        "Ctrl+S",
        "Ctrl+R",
        "Alt+1",
        "Alt+2",
        "Alt+3",
        "Alt+4",
        "Alt+5",
        "Escape",
    )


def test_inherited_topbar_icon_actions_have_native_focus_and_safe_names() -> None:
    _app()
    topbar = TopBar()

    expected = {
        "TopBarAiButton": "AI",
        "TopBarNotificationsButton": "Уведомления",
        "TopBarThemeButton": "Тема",
        "TopBarProfileButton": "Профиль",
    }
    for button in (
        topbar.ai_button,
        topbar.notify_button,
        topbar.theme_button,
        topbar.profile_button,
    ):
        assert button.objectName() in expected
        assert button.accessibleName() == expected[button.objectName()]
        assert button.focusPolicy() != Qt.FocusPolicy.NoFocus


def test_inherited_non_default_button_pointer_and_space_emit_the_same_action() -> None:
    app = _app()
    button = PrimaryButton("Продолжить")
    button.show()
    button.setFocus()
    app.processEvents()
    activations: list[str] = []
    button.clicked.connect(lambda: activations.append("activate"))

    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    QTest.keyClick(button, Qt.Key.Key_Return)
    QTest.keyClick(button, Qt.Key.Key_Space)

    assert activations == ["activate", "activate"]
    assert not button.isDefault()
    assert button.accessibleName() == "Продолжить"


def test_credential_dialog_keeps_secret_write_only_and_safe_default() -> None:
    app = _app()
    state = CredentialStateResult(
        provider_id="synthetic-provider",
        secret_name="synthetic-secret-name",
        state=CredentialState.CONFIGURED,
        message="Credential настроен",
        observed_at="2026-07-20T12:00:00+03:00",
    )
    dialog = ProviderCredentialsDialog(
        "synthetic-provider",
        "Синтетический источник",
        state=state,
    )
    dialog.show()
    dialog.activateWindow()
    app.processEvents()

    related_labels = [
        label for label in dialog.findChildren(QLabel) if label.buddy() is dialog.token_input
    ]
    save = dialog.buttons.button(QDialogButtonBox.StandardButton.Save)

    assert app.focusWidget() is dialog.token_input
    assert related_labels and related_labels[0].text() == "API credential:"
    assert dialog.token_input.text() == ""
    assert "synthetic-secret-name" not in dialog.accessibleName()
    assert save.isDefault()
    assert not dialog.delete_button.isDefault()

    dialog.token_input.setText("synthetic-value-never-persisted")
    QTest.keyClick(dialog.token_input, Qt.Key.Key_Escape)
    app.processEvents()

    assert dialog.result() == QDialog.DialogCode.Rejected
    assert dialog.token_input.text() == ""


def test_inherited_theme_pairs_remain_machine_checkable() -> None:
    for palette in (DARK_PALETTE, LIGHT_PALETTE):
        pairs = approved_contrast_pairs(palette)
        assert len(pairs) == 13
        assert all(pair.ratio >= pair.minimum_ratio for pair in pairs)
        assert {pair.pair_id for pair in pairs} >= {
            "focus_ring",
            "selection_text",
            "semantic_danger",
            "disabled_text",
        }


def test_rm151_announcement_owner_stays_bounded_and_terminal() -> None:
    coalescer = AnnouncementCoalescer(bucket_percent=10)
    base = OperationEpisode(
        episode_id=OperationEpisodeId("episode-rm152-characterization"),
        kind=OperationKind.TENDER_SEARCH,
        subject=OperationSubject("collector_run", "synthetic-run"),
        state=OperationState.RUNNING,
        attempt=1,
        generation=1,
        revision=1,
        progress=OperationProgress.bounded(current=0, total=100, phase="collect"),
        started_at=NOW,
        updated_at=NOW,
        finished_at=None,
        reason=None,
        summary=SafeText("Поиск выполняется"),
        diagnostic_id=None,
        capabilities=OperationCapabilities(can_cancel=True),
        parent_episode_id=None,
    )
    emitted = []
    for current in range(101):
        snapshot = replace(
            base,
            revision=current + 1,
            progress=OperationProgress.bounded(
                current=current,
                total=100,
                phase="collect",
            ),
        )
        if (announcement := coalescer.offer(snapshot)) is not None:
            emitted.append(announcement)
    terminal = replace(
        snapshot,
        state=OperationState.SUCCEEDED,
        revision=snapshot.revision + 1,
        finished_at=NOW,
        capabilities=OperationCapabilities(can_close=True),
    )
    emitted.append(coalescer.offer(terminal))

    assert len(emitted) <= 12
    assert emitted[-1] is not None and emitted[-1].terminal
    assert coalescer.active_count == 0
