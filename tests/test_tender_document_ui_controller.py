"""Tests for background document download UI integration."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMainWindow

from app.tenders.document_storage import (
    TenderDocumentDownloadResult,
    TenderDocumentStore,
)
from app.tenders.search_profile_repository import (
    TenderSearchProfileRepository,
)
from app.tenders.search_runtime import TenderSearchRuntime
from app.tenders.tender_registry import (
    TenderRegistryRepository,
    tender_registry_key,
)
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


class FakeDocumentService:
    def __init__(self, store: TenderDocumentStore) -> None:
        self.store = store
        self.calls: list[tuple[object, bool]] = []

    def download_for_tender(self, tender, *, force=False):
        self.calls.append((tender, force))
        return TenderDocumentDownloadResult(
            tender_registry_key=tender_registry_key(tender),
            procurement_number=tender.procurement_number,
            folder=self.store.tender_folder(tender),
            documents=(),
        )


class FailingDocumentService:
    def download_for_tender(self, tender, *, force=False):
        raise RuntimeError("network unavailable")


def _runtime(tmp_path, service=None) -> TenderSearchRuntime:
    profiles = TenderSearchProfileRepository(tmp_path / "search_profiles.json")
    profiles.initialize()
    registry_repository = TenderRegistryRepository(tmp_path / "tender_registry.sqlite3")
    registry_repository.record_profile_run(
        _run(_evaluated_tender()),
        run_id="run-documents",
    )
    store = TenderDocumentStore(tmp_path / "tender_documents")
    store.initialize()
    document_service = service or FakeDocumentService(store)
    return TenderSearchRuntime(
        data_directory=Path(tmp_path),
        repository=profiles,
        registry=object(),
        engine=object(),
        search_service=object(),
        runner=FakeRunner(),
        tender_registry=registry_repository,
        document_store=store,
        document_service=document_service,
    )


def test_controller_downloads_registry_documents_in_background(
    tmp_path,
) -> None:
    app = _app()
    runtime = _runtime(tmp_path)
    window = QMainWindow()
    controller = TenderSearchUiController(
        tmp_path,
        runtime=runtime,
        thread_pool=ImmediateThreadPool(),
        parent=window,
    )
    record = runtime.tender_registry.search_tenders()[0]

    controller.open_registry_documents(record.registry_key)

    assert len(runtime.document_service.calls) == 1
    assert len(controller.document_dialogs) == 1
    dialog = controller.document_dialogs[0]
    assert dialog.isVisible()
    assert not dialog.download_busy
    assert "Документов: 0" in dialog.status_label.text()
    app.processEvents()


def test_controller_forwards_force_download(tmp_path) -> None:
    app = _app()
    runtime = _runtime(tmp_path)
    window = QMainWindow()
    controller = TenderSearchUiController(
        tmp_path,
        runtime=runtime,
        thread_pool=ImmediateThreadPool(),
        parent=window,
    )
    tender = runtime.tender_registry.search_tenders()[0]
    unified = runtime.tender_registry.get_tender(tender.registry_key)

    controller.open_tender_documents(unified)
    dialog = controller.document_dialogs[0]
    dialog.force_download_button.click()

    assert runtime.document_service.calls[-1][1] is True
    app.processEvents()


def test_controller_shows_download_failure(tmp_path) -> None:
    app = _app()
    runtime = _runtime(tmp_path)
    runtime = TenderSearchRuntime(
        data_directory=runtime.data_directory,
        repository=runtime.repository,
        registry=runtime.registry,
        engine=runtime.engine,
        search_service=runtime.search_service,
        runner=runtime.runner,
        tender_registry=runtime.tender_registry,
        document_store=runtime.document_store,
        document_service=FailingDocumentService(),
    )
    window = QMainWindow()
    controller = TenderSearchUiController(
        tmp_path,
        runtime=runtime,
        thread_pool=ImmediateThreadPool(),
        parent=window,
    )
    record = runtime.tender_registry.search_tenders()[0]

    controller.open_registry_documents(record.registry_key)

    dialog = controller.document_dialogs[0]
    assert "network unavailable" in dialog.status_label.text()
    assert not dialog.download_busy
    app.processEvents()
