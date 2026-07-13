"""PySide6 action tests for the collector scheduler controller."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMenu,
    QToolBar,
)

from app.tenders.collector.provider_control import (
    ProviderDisplayState,
    ProviderUiState,
)
from app.tenders.search_profile_repository import (
    TenderSearchProfileRepository,
)
from app.ui.tender_collector_scheduler_controller import (
    TenderCollectorSchedulerUiController,
)


class Signals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class ProviderManager:
    def states(self):
        return (
            ProviderDisplayState(
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
            ),
        )


def _app():
    return QApplication.instance() or QApplication([])


def test_scheduler_installs_actions(tmp_path) -> None:
    app = _app()
    repository = TenderSearchProfileRepository(tmp_path / "profiles.json")
    repository.initialize()
    signals = Signals()
    window = QMainWindow()
    menu = QMenu(window)
    toolbar = QToolBar(window)
    controller = TenderCollectorSchedulerUiController(
        tmp_path,
        profile_repository=repository,
        provider_manager=ProviderManager(),
        start_collector=lambda _p, _s: True,
        is_collector_busy=lambda: False,
        collector_finished_signal=signals.finished,
        collector_failed_signal=signals.failed,
        parent=window,
    )

    controller.install_on_main_window(
        window,
        menu=menu,
        toolbar=toolbar,
    )

    assert controller.schedule_action in menu.actions()
    assert controller.notifications_action in menu.actions()
    assert controller.schedule_action in toolbar.actions()
    assert controller.timer.isActive()
    app.processEvents()
