"""Tests for background requirement-analysis UI integration."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMainWindow

from app.tenders.requirement_analysis import (
    TenderAnalysisSource,
    TenderRequirementsAnalyzer,
)
from app.tenders.search_profile_repository import (
    TenderSearchProfileRepository,
)
from app.tenders.search_runtime import TenderSearchRuntime
from app.tenders.tender_registry import TenderRegistryRepository
from app.ui.tender_search_ui_controller import TenderSearchUiController
from tests.test_tender_registry import _evaluated_tender, _run


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


class ImmediateThreadPool:
    def start(self, runnable) -> None:
        runnable.run()


class FakeRunner:
    def run(self, profile_id: str):
        return _run(_evaluated_tender())


class FakeAnalysisService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []
        self._latest = None

    def analyze(self, registry_key: str, *, force_extraction=False):
        self.calls.append((registry_key, force_extraction))
        self._latest = TenderRequirementsAnalyzer().analyze(
            registry_key,
            (
                TenderAnalysisSource(
                    document_key="tz",
                    source_name="Техническое задание.txt",
                    text=(
                        "Техническое задание. Требуется лицензия МЧС. "
                        "Срок выполнения работ 30 календарных дней."
                    ),
                ),
            ),
        )
        return self._latest

    def latest(self, registry_key: str):
        del registry_key
        return self._latest


class FailingAnalysisService(FakeAnalysisService):
    def analyze(self, registry_key: str, *, force_extraction=False):
        del registry_key, force_extraction
        raise RuntimeError("text extraction failed")


def _runtime(tmp_path, service) -> TenderSearchRuntime:
    profiles = TenderSearchProfileRepository(tmp_path / "search_profiles.json")
    profiles.initialize()
    registry_repository = TenderRegistryRepository(tmp_path / "tender_registry.sqlite3")
    registry_repository.record_profile_run(
        _run(_evaluated_tender()),
        run_id="run-analysis",
    )
    return TenderSearchRuntime(
        data_directory=Path(tmp_path),
        repository=profiles,
        registry=object(),
        engine=object(),
        search_service=object(),
        runner=FakeRunner(),
        tender_registry=registry_repository,
        requirement_analysis_service=service,
    )


def test_controller_runs_analysis_in_background(tmp_path) -> None:
    app = _app()
    service = FakeAnalysisService()
    runtime = _runtime(tmp_path, service)
    window = QMainWindow()
    controller = TenderSearchUiController(
        tmp_path,
        runtime=runtime,
        thread_pool=ImmediateThreadPool(),
        parent=window,
    )
    record = runtime.tender_registry.search_tenders()[0]

    controller.open_requirement_analysis(record.registry_key)

    assert service.calls == [(record.registry_key, False)]
    assert len(controller.analysis_dialogs) == 1
    dialog = controller.analysis_dialogs[0]
    assert dialog.analysis is not None
    assert not dialog.analysis_busy
    assert dialog.isVisible()
    app.processEvents()


def test_controller_forwards_force_extraction(tmp_path) -> None:
    app = _app()
    service = FakeAnalysisService()
    runtime = _runtime(tmp_path, service)
    window = QMainWindow()
    controller = TenderSearchUiController(
        tmp_path,
        runtime=runtime,
        thread_pool=ImmediateThreadPool(),
        parent=window,
    )
    record = runtime.tender_registry.search_tenders()[0]

    controller.open_requirement_analysis(record.registry_key)
    dialog = controller.analysis_dialogs[0]
    dialog.force_button.click()

    assert service.calls[-1] == (record.registry_key, True)
    app.processEvents()


def test_controller_shows_analysis_failure(tmp_path) -> None:
    app = _app()
    runtime = _runtime(tmp_path, FailingAnalysisService())
    window = QMainWindow()
    controller = TenderSearchUiController(
        tmp_path,
        runtime=runtime,
        thread_pool=ImmediateThreadPool(),
        parent=window,
    )
    record = runtime.tender_registry.search_tenders()[0]

    controller.open_requirement_analysis(record.registry_key)

    dialog = controller.analysis_dialogs[0]
    rendered = dialog.status_label.text()
    assert "text extraction failed" not in rendered
    assert "diagnostic-" in rendered
    assert not dialog.analysis_busy
    app.processEvents()
