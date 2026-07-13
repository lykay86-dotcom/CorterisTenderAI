"""Controller integration tests for the provider manager UI."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMainWindow

from app.tenders.collector.provider_control import (
    ProviderDisplayState,
    ProviderUiState,
)
from app.ui.tender_search_ui_controller import (
    TenderSearchUiController,
)
from tests.test_tender_search_ui_controller import (
    FakeRunner,
    _runtime,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


class FakeProviderManager:
    def __init__(self) -> None:
        self.enabled: dict[str, bool] = {"eis": True}
        self.checks: list[tuple[str, ...]] = []

    def states(self):
        return (
            ProviderDisplayState(
                provider_id="eis",
                display_name="ЕИС Закупки",
                enabled=self.enabled["eis"],
                ui_state=ProviderUiState.LIMITED,
                status_text="Не проверен",
                connection_mode="Публичный HTML",
                implementation_status="public_html_async",
                homepage_url="https://zakupki.gov.ru/",
                last_checked_at="",
                last_success_at="",
                last_error="",
                latency_ms=None,
            ),
        )

    def enabled_provider_ids(self):
        return tuple(key for key, value in self.enabled.items() if value)

    def set_enabled(self, provider_id, enabled):
        self.enabled[provider_id] = enabled
        return self.states()[0]

    async def check_providers(self, provider_ids):
        self.checks.append(tuple(provider_ids))
        return self.states()


class ImmediateThreadPool:
    def start(self, runnable) -> None:
        runnable.run()


def test_controller_installs_visible_sources_action(tmp_path) -> None:
    app = _app()
    window = QMainWindow()
    controller = TenderSearchUiController(
        tmp_path,
        runtime=_runtime(tmp_path, FakeRunner()),
        provider_manager=FakeProviderManager(),
        parent=window,
    )

    controller.install_on_main_window(window)

    assert controller.providers_action in (controller._tender_menu.actions())
    assert controller.providers_action in (controller._tender_toolbar.actions())
    assert controller.providers_action.objectName() == ("actionTenderProviders")
    app.processEvents()


def test_controller_opens_and_checks_provider(tmp_path) -> None:
    app = _app()
    manager = FakeProviderManager()
    window = QMainWindow()
    controller = TenderSearchUiController(
        tmp_path,
        runtime=_runtime(tmp_path, FakeRunner()),
        provider_manager=manager,
        thread_pool=ImmediateThreadPool(),
        parent=window,
    )

    controller.open_provider_manager_dialog()
    controller.check_provider_connection("eis")

    assert controller.provider_dialog is not None
    assert controller.provider_dialog.isVisible()
    assert manager.checks == [("eis",)]
    app.processEvents()
