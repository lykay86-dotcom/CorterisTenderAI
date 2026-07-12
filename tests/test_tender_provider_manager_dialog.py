"""PySide6 tests for the provider manager dialog."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.tenders.collector.provider_control import (
    ProviderDisplayState,
    ProviderUiState,
)
from app.ui.tender_provider_manager_dialog import (
    TenderProviderManagerDialog,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _states():
    return (
        ProviderDisplayState(
            provider_id="eis",
            display_name="ЕИС Закупки",
            enabled=True,
            ui_state=ProviderUiState.LIMITED,
            status_text="Резервный HTML-режим",
            connection_mode="Публичный HTML",
            implementation_status="public_html_async",
            homepage_url="https://zakupki.gov.ru/",
            last_checked_at="",
            last_success_at="",
            last_error="",
            latency_ms=None,
            configuration_details=("Без обхода CAPTCHA.",),
        ),
        ProviderDisplayState(
            provider_id="mos_supplier",
            display_name="Портал поставщиков Москвы",
            enabled=False,
            ui_state=ProviderUiState.DISABLED,
            status_text="Отключён пользователем",
            connection_mode="Официальный API",
            implementation_status="official_api_token_required",
            homepage_url="https://zakupki.mos.ru/",
            last_checked_at="",
            last_success_at="",
            last_error="",
            latency_ms=None,
        ),
    )


def test_dialog_renders_sources_and_emits_switch() -> None:
    app = _app()
    dialog = TenderProviderManagerDialog(_states())
    changes: list[tuple[str, bool]] = []
    dialog.provider_enabled_changed.connect(
        lambda provider_id, enabled: changes.append(
            (provider_id, enabled)
        )
    )

    item = dialog.table.item(1, 0)
    item.setCheckState(
        __import__("PySide6").QtCore.Qt.CheckState.Checked
    )

    assert dialog.table.rowCount() == 2
    assert changes == [("mos_supplier", True)]
    app.processEvents()


def test_dialog_emits_provider_check() -> None:
    app = _app()
    dialog = TenderProviderManagerDialog(_states())
    requested: list[str] = []
    dialog.provider_check_requested.connect(requested.append)

    dialog._check_buttons["eis"].click()

    assert requested == ["eis"]
    app.processEvents()
