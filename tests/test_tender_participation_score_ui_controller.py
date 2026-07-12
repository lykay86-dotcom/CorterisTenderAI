"""Background participation-score UI integration tests."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMainWindow

from app.tenders.collector.participation_score import (
    CorterisParticipationRanker,
)
from app.tenders.search_profile_repository import (
    TenderSearchProfileRepository,
)
from app.tenders.search_runtime import TenderSearchRuntime
from app.tenders.tender_registry import TenderRegistryRepository
from app.ui.tender_search_ui_controller import TenderSearchUiController
from tests.collector_c3_helpers import make_tender
from tests.test_tender_registry import _evaluated_tender, _run


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


class ImmediateThreadPool:
    def start(self, runnable) -> None:
        runnable.run()


class FakeRunner:
    def run(self, profile_id: str):
        del profile_id
        return _run(_evaluated_tender())


class FakeScoreService:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self._latest = None

    def latest(self, registry_key: str):
        del registry_key
        return self._latest

    def evaluate(self, registry_key: str, *, persist=True):
        assert persist
        self.calls.append(registry_key)
        self._latest = CorterisParticipationRanker().score(
            make_tender(deadline_day=30)
        )
        return self._latest


class FailingScoreService(FakeScoreService):
    def evaluate(self, registry_key: str, *, persist=True):
        del registry_key, persist
        raise RuntimeError("score calculation failed")


def _runtime(tmp_path, service) -> TenderSearchRuntime:
    profiles = TenderSearchProfileRepository(
        tmp_path / "search_profiles.json"
    )
    profiles.initialize()
    registry_repository = TenderRegistryRepository(
        tmp_path / "tender_registry.sqlite3"
    )
    registry_repository.record_profile_run(
        _run(_evaluated_tender()),
        run_id="run-score",
    )
    return TenderSearchRuntime(
        data_directory=Path(tmp_path),
        repository=profiles,
        registry=object(),
        engine=object(),
        search_service=object(),
        runner=FakeRunner(),
        tender_registry=registry_repository,
        participation_score_service=service,
    )


def test_controller_runs_score_in_background(tmp_path) -> None:
    app = _app()
    service = FakeScoreService()
    runtime = _runtime(tmp_path, service)
    window = QMainWindow()
    controller = TenderSearchUiController(
        tmp_path,
        runtime=runtime,
        thread_pool=ImmediateThreadPool(),
        parent=window,
    )
    record = runtime.tender_registry.search_tenders()[0]

    controller.open_participation_score(record.registry_key)

    assert service.calls == [record.registry_key]
    assert len(controller.score_dialogs) == 1
    dialog = controller.score_dialogs[0]
    assert dialog.score is not None
    assert dialog.isVisible()
    app.processEvents()


def test_controller_shows_score_failure(tmp_path) -> None:
    app = _app()
    runtime = _runtime(tmp_path, FailingScoreService())
    window = QMainWindow()
    controller = TenderSearchUiController(
        tmp_path,
        runtime=runtime,
        thread_pool=ImmediateThreadPool(),
        parent=window,
    )
    record = runtime.tender_registry.search_tenders()[0]

    controller.open_participation_score(record.registry_key)

    dialog = controller.score_dialogs[0]
    assert "score calculation failed" in dialog.status_label.text()
    assert dialog.recalculate_button.isEnabled()
    app.processEvents()
