"""Tests for non-blocking Dashboard refresh."""

from __future__ import annotations

import os
import threading
from time import sleep

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

from app.ui.controllers.dashboard_controller import DashboardController


class FakeViewModel(QObject):
    refresh_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.kpis: dict[str, str] = {}
        self.tenders = []
        self.recommendations = []

    def set_kpi(self, key: str, *, value: str, **_kwargs) -> None:
        self.kpis[key] = value

    def set_recent_tenders(self, tenders) -> None:
        self.tenders = list(tenders)

    def set_ai_recommendations(self, recommendations) -> None:
        self.recommendations = list(recommendations)

    def apply_snapshot(
        self,
        kpis,
        *,
        recent_tenders,
        ai_recommendations,
        loaded_at,
    ) -> None:
        self.kpis = {item.key: item.value for item in kpis}
        self.tenders = list(recent_tenders)
        self.recommendations = list(ai_recommendations)


class FakePage(QObject):
    tender_open_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.demo_mode = False
        self.viewmodel = FakeViewModel()
        self.refresh_calls: list[tuple[bool, bool, bool]] = []
        self.states = []
        self.activities = []
        self.errors: list[str] = []
        self.partial_messages: list[str] = []

    def set_refreshing(
        self,
        refreshing: bool,
        *,
        preserve_content: bool = False,
        successful: bool = True,
    ) -> None:
        self.refresh_calls.append((refreshing, preserve_content, successful))

    def set_data_state(self, state) -> None:
        self.states.append(state)

    def set_activities(self, activities) -> None:
        self.activities = list(activities)

    def show_error(self, message: str, **_kwargs) -> None:
        self.errors.append(message)

    def set_partial_data(self, message: str) -> None:
        self.partial_messages.append(message)


class FakeRepository:
    def __init__(self) -> None:
        self.thread_ids: list[int] = []
        self.raise_error = False
        self.delay = 0.0

    def list_for_dashboard(self, *, limit: int | None):
        assert limit is None
        self.thread_ids.append(threading.get_ident())
        if self.delay:
            sleep(self.delay)
        if self.raise_error:
            raise RuntimeError("database unavailable")
        return []


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _wait_for_cycle(
    controller: DashboardController,
    timeout_ms: int = 3000,
) -> None:
    loop = QEventLoop()
    controller.refresh_cycle_finished.connect(loop.quit)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()


def test_refresh_runs_repository_outside_ui_thread() -> None:
    _app()
    page = FakePage()
    repository = FakeRepository()
    controller = DashboardController(
        page,
        repository=repository,
        auto_refresh_ms=0,
    )
    main_thread_id = threading.get_ident()

    assert controller.refresh() is True
    assert controller.is_refreshing is True
    _wait_for_cycle(controller)

    assert repository.thread_ids
    assert repository.thread_ids[0] != main_thread_id
    assert controller.is_refreshing is False
    assert page.refresh_calls[0] == (True, False, True)
    assert page.refresh_calls[-1] == (False, False, True)


def test_second_refresh_preserves_existing_content() -> None:
    _app()
    page = FakePage()
    repository = FakeRepository()
    controller = DashboardController(
        page,
        repository=repository,
        auto_refresh_ms=0,
    )

    assert controller.refresh() is True
    _wait_for_cycle(controller)
    assert controller.has_loaded_once is True

    assert controller.refresh() is True
    _wait_for_cycle(controller)

    assert page.refresh_calls[-2] == (True, True, True)
    assert page.refresh_calls[-1] == (False, True, True)


def test_background_error_keeps_previous_data() -> None:
    _app()
    page = FakePage()
    repository = FakeRepository()
    controller = DashboardController(
        page,
        repository=repository,
        auto_refresh_ms=0,
    )

    assert controller.refresh() is True
    _wait_for_cycle(controller)

    repository.raise_error = True
    assert controller.refresh() is True
    _wait_for_cycle(controller)

    assert page.partial_messages
    assert "ранее загруженные данные" in page.partial_messages[-1]
    assert page.refresh_calls[-1] == (False, True, False)


def test_duplicate_refresh_is_ignored() -> None:
    _app()
    page = FakePage()
    repository = FakeRepository()
    repository.delay = 0.1
    controller = DashboardController(
        page,
        repository=repository,
        auto_refresh_ms=0,
    )

    assert controller.refresh() is True
    assert controller.refresh() is False
    _wait_for_cycle(controller)


def test_auto_refresh_can_be_disabled() -> None:
    _app()
    controller = DashboardController(
        FakePage(),
        repository=FakeRepository(),
        auto_refresh_ms=0,
    )

    assert controller.auto_refresh_interval == 0
