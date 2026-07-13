"""Controller integration tests for automatic Tender Collector runs."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMainWindow

from app.tenders.collector.async_engine import AsyncProviderBatchResult
from app.tenders.collector.models import (
    CollectionPersistenceSummary,
    CollectionRunStatus,
    CollectorRunResult,
    DeduplicationResult,
)
from app.tenders.collector.progress import (
    CollectorProgressEvent,
    CollectorProgressPhase,
)
from app.tenders.collector.provider_control import (
    ProviderDisplayState,
    ProviderUiState,
)
from app.tenders.search_profile_repository import (
    TenderSearchProfileRepository,
)
from app.tenders.search_runtime import TenderSearchRuntime
from app.ui.tender_search_ui_controller import TenderSearchUiController


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


class ImmediateThreadPool:
    def start(self, runnable) -> None:
        runnable.run()


class FakeRunner:
    def run(self, profile_id):
        raise AssertionError(profile_id)


class FakeProviderManager:
    def states(self):
        return (
            ProviderDisplayState(
                provider_id="eis",
                display_name="ЕИС",
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
            ),
        )

    def enabled_provider_ids(self):
        return ("eis",)


class FakeCollectorSession:
    def __init__(self) -> None:
        self.calls = []

    async def run(
        self,
        query,
        *,
        provider_ids=None,
        cancellation_token=None,
        progress_callback=None,
    ):
        self.calls.append((query, tuple(provider_ids or ())))
        if progress_callback is not None:
            progress_callback(
                CollectorProgressEvent(
                    phase=CollectorProgressPhase.PROVIDER_COMPLETED,
                    provider_id="eis",
                    display_name="ЕИС",
                    provider_status="empty",
                    total_providers=1,
                    message="Нет результатов",
                )
            )
        return _result()


def _runtime(tmp_path) -> TenderSearchRuntime:
    repository = TenderSearchProfileRepository(tmp_path / "search_profiles.json")
    repository.initialize()
    return TenderSearchRuntime(
        data_directory=Path(tmp_path),
        repository=repository,
        registry=object(),
        engine=object(),
        search_service=object(),
        runner=FakeRunner(),
    )


def _result() -> CollectorRunResult:
    return CollectorRunResult(
        run_id="run-controller",
        status=CollectionRunStatus.COMPLETED,
        batch_result=AsyncProviderBatchResult(
            results=(),
            outcomes=(),
            started_at="2026-07-12T10:00:00+00:00",
            completed_at="2026-07-12T10:00:01+00:00",
            elapsed_ms=1000,
        ),
        deduplication=DeduplicationResult(
            items=(),
            groups=(),
            raw_count=0,
        ),
        persistence=CollectionPersistenceSummary(
            run_id="run-controller",
            new_count=0,
            unchanged_count=0,
            changed_count=0,
            merged_count=0,
            duplicate_count=0,
            change_count=0,
            version_count=0,
        ),
    )


def test_controller_installs_visible_collector_action(tmp_path) -> None:
    app = _app()
    window = QMainWindow()
    controller = TenderSearchUiController(
        tmp_path,
        runtime=_runtime(tmp_path),
        provider_manager=FakeProviderManager(),
        collector_session=FakeCollectorSession(),
        parent=window,
    )

    controller.install_on_main_window(window)

    assert controller.collector_action in controller._tender_menu.actions()
    assert controller.collector_action in controller._tender_toolbar.actions()
    assert controller.collector_action.objectName() == "actionTenderCollector"
    app.processEvents()


def test_controller_runs_collector_and_updates_dialog(tmp_path) -> None:
    app = _app()
    window = QMainWindow()
    session = FakeCollectorSession()
    controller = TenderSearchUiController(
        tmp_path,
        runtime=_runtime(tmp_path),
        provider_manager=FakeProviderManager(),
        collector_session=session,
        thread_pool=ImmediateThreadPool(),
        parent=window,
    )

    controller.open_collector_dialog()
    controller.start_collector("all-corteris", ("eis",))

    assert len(session.calls) == 1
    assert session.calls[0][1] == ("eis",)
    assert controller.collector_dialog is not None
    assert not controller.collector_dialog.running
    assert "Сбор завершён" in controller.collector_dialog.status_label.text()
    app.processEvents()
