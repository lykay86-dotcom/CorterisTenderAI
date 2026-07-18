"""Controller integration tests for automatic Tender Collector runs."""

from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

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
from app.ui.tender_search_ui_controller import (
    TenderSearchUiController,
    _CollectorRunWorker,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


class ImmediateThreadPool:
    def start(self, runnable) -> None:
        runnable.run()


class CapturingThreadPool:
    def __init__(self) -> None:
        self.runnables = []

    def start(self, runnable) -> None:
        self.runnables.append(runnable)


class FakeWorkspace(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setLayout(QVBoxLayout())
        self.actions_bound = ()
        self.panel = None

    def bind_tender_actions(self, actions) -> None:
        self.actions_bound = tuple(actions)

    def install_unified_search_panel(self, panel) -> None:
        if self.panel is panel:
            return
        assert self.panel is None
        self.panel = panel
        self.layout().addWidget(panel)


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


class FailingCollectorSession:
    async def run(self, query, **kwargs):
        del query, kwargs
        raise RuntimeError("token=ui-secret https://private.example/path?q=secret")


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


def test_panel_and_dialog_share_busy_cancel_and_worker_cleanup(tmp_path) -> None:
    _app()
    pool = CapturingThreadPool()
    controller = TenderSearchUiController(
        tmp_path,
        runtime=_runtime(tmp_path),
        provider_manager=FakeProviderManager(),
        collector_session=FakeCollectorSession(),
        thread_pool=pool,
    )
    workspace = FakeWorkspace()
    controller.install_on_tender_workspace(workspace)
    controller.open_collector_dialog()

    assert controller.try_start_collector("all-corteris", ("eis",)) is True
    worker = controller._collector_worker
    assert worker is not None
    assert len(pool.runnables) == 1
    assert controller.collector_dialog is not None
    assert controller.collector_dialog.running
    assert controller.unified_search_panel is not None
    assert controller.unified_search_panel.running

    assert controller.try_start_collector("all-corteris", ("eis",)) is False
    assert len(pool.runnables) == 1
    controller.stop_collector()

    assert worker.cancellation_token.is_cancelled
    assert not controller.collector_dialog.stop_button.isEnabled()
    assert not controller.unified_search_panel.stop_button.isEnabled()

    controller._on_collector_succeeded(_result())

    assert controller._collector_worker is None
    assert not controller.collector_dialog.running
    assert not controller.unified_search_panel.running


def test_partial_failure_and_invalid_result_are_not_reported_as_success(tmp_path) -> None:
    _app()
    controller = TenderSearchUiController(
        tmp_path,
        runtime=_runtime(tmp_path),
        provider_manager=FakeProviderManager(),
        collector_session=FakeCollectorSession(),
        thread_pool=CapturingThreadPool(),
    )
    workspace = FakeWorkspace()
    controller.install_on_tender_workspace(workspace)
    controller.open_collector_dialog()
    panel = controller.unified_search_panel
    dialog = controller.collector_dialog
    assert panel is not None
    assert dialog is not None

    assert controller.try_start_collector("all-corteris", ("eis",)) is True
    controller._on_collector_succeeded(replace(_result(), status=CollectionRunStatus.PARTIAL))
    assert "частично" in panel.status_label.text().casefold()
    assert "ошибками" in dialog.status_label.text().casefold()

    assert controller.try_start_collector("all-corteris", ("eis",)) is True
    controller._on_collector_failed(
        "provider_internal_error",
        "bounded failure ui-secret",
    )
    assert controller._collector_worker is None
    assert "ошибкой" in panel.status_label.text().casefold()
    assert "безопасно скрытой ошибкой" in dialog.status_label.text()
    assert "ui-secret" not in dialog.status_label.text()

    assert controller.try_start_collector("all-corteris", ("eis",)) is True
    controller._on_collector_succeeded(object())
    assert controller._collector_worker is None
    assert "безопасно скрытой ошибкой" in panel.status_label.text().casefold()


def test_collector_worker_emits_only_safe_typed_failure() -> None:
    _app()
    worker = _CollectorRunWorker(FailingCollectorSession(), object(), ("eis",), 7)
    failures: list[tuple[int, str, str]] = []
    worker.signals.failed.connect(
        lambda generation, code, message: failures.append((generation, code, message))
    )

    worker.run()

    assert failures == [
        (
            7,
            "provider_internal_error",
            "Источник завершил поиск с безопасно скрытой ошибкой.",
        )
    ]
    assert "ui-secret" not in failures[0][2]
