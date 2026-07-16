"""RM-131 existing provider-dialog non-secret configuration contract."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.tenders.collector.provider_control import ProviderDisplayState, ProviderUiState
from app.tenders.collector.provider_settings import (
    ProviderConfiguration,
    ProviderSettingOrigin,
)
from app.ui.tender_provider_manager_dialog import (
    TenderProviderConfigurationDialog,
    TenderProviderManagerDialog,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _commercial_state(*, editable: bool = True) -> ProviderDisplayState:
    return ProviderDisplayState(
        provider_id="b2b_center",
        display_name="B2B-Center",
        enabled=True,
        ui_state=ProviderUiState.NOT_CONFIGURED,
        status_text="Требуется настройка",
        connection_mode="API-доступ ожидает подтверждения",
        implementation_status="commercial_access_pending",
        homepage_url="https://www.b2b-center.ru/",
        last_checked_at="",
        last_success_at="",
        last_error="",
        latency_ms=None,
        configuration=ProviderConfiguration(
            access_confirmed=False,
            api_base_url="https://api.b2b.test/v1",
        ),
        configuration_origin=(
            ProviderSettingOrigin.PERSISTED if editable else ProviderSettingOrigin.ENVIRONMENT
        ),
        configuration_editable=editable,
    )


def test_existing_manager_dialog_routes_commercial_configuration_request() -> None:
    app = _app()
    dialog = TenderProviderManagerDialog((_commercial_state(),))
    requested: list[str] = []
    dialog.provider_configuration_requested.connect(requested.append)

    assert dialog.configure_button.isEnabled()
    dialog.configure_button.click()

    assert requested == ["b2b_center"]
    app.processEvents()


def test_configuration_editor_returns_typed_non_secret_values() -> None:
    app = _app()
    dialog = TenderProviderConfigurationDialog(_commercial_state())
    dialog.access_confirmed_checkbox.setChecked(True)
    dialog.api_base_url_edit.setText("https://api.b2b.test/v2/")

    assert dialog.configuration() == ProviderConfiguration(
        access_confirmed=True,
        api_base_url="https://api.b2b.test/v2",
    )
    app.processEvents()


def test_environment_override_is_visible_and_read_only() -> None:
    app = _app()
    dialog = TenderProviderConfigurationDialog(_commercial_state(editable=False))

    assert "окруж" in dialog.origin_label.text().casefold()
    assert not dialog.access_confirmed_checkbox.isEnabled()
    assert not dialog.api_base_url_edit.isEnabled()
    app.processEvents()
