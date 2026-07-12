"""PySide6 tests for the collector schedule dialog."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.tenders.collector.provider_control import (
    ProviderDisplayState,
    ProviderUiState,
)
from app.tenders.collector.scheduler import (
    CollectorScheduleFrequency,
    CollectorScheduleSettings,
    CollectorScheduleState,
)
from app.tenders.search_profiles import (
    create_builtin_search_profiles,
)
from app.ui.tender_collector_schedule_dialog import (
    TenderCollectorScheduleDialog,
)


def _app():
    return QApplication.instance() or QApplication([])


def _provider():
    return ProviderDisplayState(
        provider_id="eis",
        display_name="ЕИС",
        enabled=True,
        ui_state=ProviderUiState.LIMITED,
        status_text="Резервный HTML",
        connection_mode="Публичный HTML",
        implementation_status="public_html_async",
        homepage_url="https://zakupki.gov.ru/",
        last_checked_at="",
        last_success_at="",
        last_error="",
        latency_ms=None,
    )


def test_dialog_builds_enabled_settings() -> None:
    app = _app()
    dialog = TenderCollectorScheduleDialog()
    settings = CollectorScheduleSettings(
        enabled=True,
        profile_id="all-corteris",
        provider_ids=("eis",),
        frequency=CollectorScheduleFrequency.HOURLY,
    )
    dialog.set_configuration(
        settings,
        CollectorScheduleState(),
        create_builtin_search_profiles(),
        (_provider(),),
    )

    result = dialog.build_settings()

    assert result.enabled
    assert result.profile_id == "all-corteris"
    assert result.provider_ids == ("eis",)
    app.processEvents()
