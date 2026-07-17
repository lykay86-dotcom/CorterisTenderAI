"""RM-134 controlled Qt form and canonical manager action."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton

from app.connectors.manual import ManualConnectorTester
from app.tenders.collector.manual_provider_protocol import (
    ManualProviderAuthenticationKind,
    ManualProviderPayloadFormat,
    ManualProviderProtocolFamily,
)
from app.tenders.collector.manual_provider_registration import ManualProviderDraft
from app.tenders.collector.provider_control import CollectorProviderManager
from app.ui.tender_provider_manager_dialog import (
    ManualProviderProtocolDialog,
    TenderProviderManagerDialog,
)


MANUAL_ID = f"manual_{'9' * 32}"


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _manager(tmp_path) -> CollectorProviderManager:
    manager = CollectorProviderManager(
        tmp_path,
        environment={},
        manual_provider_id_factory=lambda: MANUAL_ID,
    )
    manager.register_manual_provider(ManualProviderDraft("Площадка", "https://example.test"))
    return manager


def test_manager_exposes_protocol_action_only_for_manual_row(tmp_path) -> None:
    app = _app()
    manager = _manager(tmp_path)
    dialog = TenderProviderManagerDialog(manager.states())
    requested: list[str] = []
    dialog.manual_provider_protocol_requested.connect(requested.append)

    builtin_row = next(i for i, item in enumerate(dialog.states) if item.provider_id == "eis")
    dialog.table.selectRow(builtin_row)
    app.processEvents()
    assert dialog.manual_provider_protocol_button.isEnabled() is False

    manual_row = next(i for i, item in enumerate(dialog.states) if item.provider_id == MANUAL_ID)
    dialog.table.selectRow(manual_row)
    app.processEvents()
    assert dialog.manual_provider_protocol_button.isEnabled() is True
    dialog.manual_provider_protocol_button.click()
    assert requested == [MANUAL_ID]


def test_dialog_has_one_endpoint_input_and_family_controlled_options(tmp_path, monkeypatch) -> None:
    app = _app()
    manager = _manager(tmp_path)
    registration = manager.settings_snapshot().get_manual(MANUAL_ID)
    monkeypatch.setattr(
        ManualConnectorTester,
        "test",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("legacy network tester must not run")
        ),
    )
    dialog = ManualProviderProtocolDialog(registration)

    edits = dialog.findChildren(QLineEdit)
    assert [item.objectName() for item in edits] == ["ManualProviderProtocolEndpoint"]
    assert dialog.family_combo.count() == 4
    assert [dialog.family_combo.itemData(i) for i in range(4)] == [
        ManualProviderProtocolFamily.API,
        ManualProviderProtocolFamily.RSS,
        ManualProviderProtocolFamily.FTP,
        ManualProviderProtocolFamily.FTPS,
    ]

    dialog.endpoint_edit.setText("https://api.example.test/v1")
    app.processEvents()
    assert dialog.save_button.isEnabled()
    assert dialog.draft().payload_format is ManualProviderPayloadFormat.JSON
    assert dialog.draft().authentication_kind is ManualProviderAuthenticationKind.NONE

    dialog.family_combo.setCurrentIndex(2)
    dialog.endpoint_edit.setText("ftp://files.example.test/tenders")
    app.processEvents()
    assert dialog.payload_combo.isEnabled() is False
    assert dialog.payload_combo.currentData() is None
    assert "без TLS" in dialog.warning_label.text()
    assert "адаптер" in dialog.validation_label.text().casefold()
    assert not any(
        marker in item.objectName().casefold()
        for item in edits
        for marker in ("password", "secret", "token", "username", "key")
    )


def test_invalid_endpoint_is_locally_gated_without_connection_action(tmp_path) -> None:
    app = _app()
    manager = _manager(tmp_path)
    dialog = ManualProviderProtocolDialog(manager.settings_snapshot().get_manual(MANUAL_ID))
    dialog.endpoint_edit.setText("https://127.0.0.1/private?token=secret")
    app.processEvents()

    assert dialog.save_button.isEnabled() is False
    assert dialog.clear_button.isEnabled() is False
    assert not any(
        "проверить" in button.text().casefold() for button in dialog.findChildren(QPushButton)
    )
