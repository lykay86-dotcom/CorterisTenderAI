"""RM-133 Qt contract for the existing canonical provider manager."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QComboBox, QLineEdit, QPushButton

from app.tenders.collector.manual_provider_registration import ManualProviderDraft
from app.tenders.collector.provider_control import CollectorProviderManager
from app.tenders.search_runtime import create_tender_search_runtime
from app.ui.tender_provider_manager_dialog import (
    ManualProviderRegistrationDialog,
    TenderProviderManagerDialog,
)
from app.ui.tender_search_ui_controller import TenderSearchUiController


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_existing_manager_dialog_has_one_canonical_add_action() -> None:
    app = _app()
    dialog = TenderProviderManagerDialog(())
    requested: list[bool] = []
    dialog.manual_provider_add_requested.connect(lambda: requested.append(True))

    button = dialog.findChild(QPushButton, "AddManualProviderButton")
    assert button is dialog.add_manual_provider_button
    assert button.text() == "Добавить площадку вручную"
    button.click()

    assert requested == [True]
    app.processEvents()


def test_registration_form_contains_only_audited_non_secret_fields() -> None:
    app = _app()
    dialog = ManualProviderRegistrationDialog()
    edits = {item.objectName() for item in dialog.findChildren(QLineEdit)}

    assert edits == {
        "ManualProviderDisplayName",
        "ManualProviderHomepageUrl",
        "ManualProviderEndpointUrl",
    }
    assert not dialog.findChildren(QComboBox)
    assert "credential" not in dialog.windowTitle().casefold()
    assert "протокол" not in dialog.windowTitle().casefold()
    assert not any(
        "провер" in button.text().casefold() for button in dialog.findChildren(QPushButton)
    )
    app.processEvents()


def test_save_is_locally_gated_and_returns_typed_draft() -> None:
    app = _app()
    dialog = ManualProviderRegistrationDialog()

    assert not dialog.save_button.isEnabled()
    dialog.display_name_edit.setText("Новая площадка")
    dialog.homepage_url_edit.setText("https://example.test/")
    dialog.endpoint_url_edit.setText("https://api.example.test/v1/")
    app.processEvents()

    assert dialog.save_button.isEnabled()
    assert dialog.draft() == ManualProviderDraft(
        display_name="Новая площадка",
        homepage_url="https://example.test",
        endpoint_url="https://api.example.test/v1",
    )
    dialog.save_button.click()
    assert not dialog.save_button.isEnabled()


def test_created_manual_row_disables_enable_check_credentials_and_configuration(tmp_path) -> None:
    app = _app()
    manager = CollectorProviderManager(
        tmp_path,
        manual_provider_id_factory=lambda: f"manual_{'b' * 32}",
    )
    created = manager.register_manual_provider(
        ManualProviderDraft("Площадка", "https://example.test", "https://api.example.test")
    )
    dialog = TenderProviderManagerDialog(manager.states())
    row = next(
        index
        for index, state in enumerate(dialog.states)
        if state.provider_id == created.provider_id
    )
    dialog.table.selectRow(row)
    app.processEvents()

    assert dialog.table.item(row, 0).flags().value & 16 == 0
    assert dialog.table.cellWidget(row, 6).isEnabled() is False
    assert dialog.configure_button.isEnabled() is False
    assert dialog.credentials_button.isEnabled() is False
    assert "Требуется выбор протокола" in dialog.details.toPlainText()


def test_manual_edit_signal_preserves_selected_id(tmp_path) -> None:
    app = _app()
    manager = CollectorProviderManager(
        tmp_path,
        manual_provider_id_factory=lambda: f"manual_{'c' * 32}",
    )
    created = manager.register_manual_provider(
        ManualProviderDraft("Площадка", "https://example.test")
    )
    dialog = TenderProviderManagerDialog(manager.states())
    requested: list[str] = []
    dialog.manual_provider_edit_requested.connect(requested.append)
    row = next(i for i, item in enumerate(dialog.states) if item.provider_id == created.provider_id)
    dialog.table.selectRow(row)
    app.processEvents()

    dialog.edit_manual_provider_button.click()

    assert requested == [created.provider_id]


def test_saved_profile_and_scheduler_entry_reject_manual_id_before_worker(tmp_path) -> None:
    app = _app()
    manager = CollectorProviderManager(
        tmp_path,
        manual_provider_id_factory=lambda: f"manual_{'6' * 32}",
    )
    created = manager.register_manual_provider(
        ManualProviderDraft("Площадка", "https://example.test")
    )
    runtime = create_tender_search_runtime(tmp_path)

    class _ThreadPoolTripwire:
        def start(self, _runnable) -> None:
            raise AssertionError("collector worker must not start")

    controller = TenderSearchUiController(
        tmp_path,
        runtime=runtime,
        provider_manager=manager,
        thread_pool=_ThreadPoolTripwire(),
    )
    profile = runtime.repository.list_profiles(include_disabled=False)[0]

    assert controller.try_start_collector(profile.id, (created.provider_id,)) is False
    assert controller._collector_worker is None
    app.processEvents()
