"""Tests for main-window tender search integration and background runs."""

from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMainWindow

from app.tenders.search_profile_repository import (
    TenderSearchProfileRepository,
)
from app.tenders.search_runtime import TenderSearchRuntime
from app.tenders.document_storage import TenderDocumentStore
from app.tenders.http_client import HttpResponse
from app.tenders.models import (
    TenderCustomer,
    TenderDocument,
    TenderSource,
    TenderStatus,
    UnifiedTender,
)
from app.tenders.tender_registry import tender_registry_key
from app.tenders.unified_search import UnifiedTenderSearchRequest
from app.ui.tender_search_ui_controller import (
    TenderSearchUiController,
)
from tests.test_tender_collector_dialog import _result as make_collector_result
from tests.test_rm127_tender_workspace_contract import _page
from tests.tender_search_ui_helpers import make_profile_run


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


class ImmediateThreadPool:
    def start(self, runnable) -> None:
        runnable.run()


class FakeRunner:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[str] = []

    def run(self, profile_id: str):
        self.calls.append(profile_id)
        if self.error is not None:
            raise self.error
        return make_profile_run()


class FakeCollectorSession:
    def __init__(self) -> None:
        self.calls: list[tuple[object, tuple[str, ...]]] = []

    async def run(
        self,
        query,
        *,
        provider_ids,
        cancellation_token,
        progress_callback,
    ):
        self.calls.append((query, tuple(provider_ids)))
        return make_collector_result()


class FakeTenderRegistry:
    def __init__(self, tender: UnifiedTender, path: Path) -> None:
        self.tender = tender
        self.path = path

    def get_tender(self, registry_key: str) -> UnifiedTender | None:
        return self.tender if registry_key == tender_registry_key(self.tender) else None


def _runtime(tmp_path, runner) -> TenderSearchRuntime:
    repository = TenderSearchProfileRepository(tmp_path / "search_profiles.json")
    repository.initialize()
    return TenderSearchRuntime(
        data_directory=Path(tmp_path),
        repository=repository,
        registry=object(),
        engine=object(),
        search_service=object(),
        runner=runner,
    )


def test_controller_installs_tender_menu_action(tmp_path) -> None:
    app = _app()
    window = QMainWindow()
    controller = TenderSearchUiController(
        tmp_path,
        runtime=_runtime(tmp_path, FakeRunner()),
        thread_pool=ImmediateThreadPool(),
        parent=window,
    )

    action = controller.install_on_main_window(window)

    # Do not obtain the menu through repeated QAction.menu() calls.
    # On PySide6/Windows/offscreen those temporary wrappers may be
    # invalidated even though the real QMenu is still owned by QMenuBar.
    menu = controller._tender_menu

    assert menu is not None
    assert menu.objectName() == "tendersMenu"
    assert menu.menuAction() in window.menuBar().actions()
    assert action in menu.actions()
    assert action.objectName() == "actionTenderSearchProfiles"
    assert window._tender_search_ui_controller is controller
    assert window._tender_search_menu is menu

    app.processEvents()


def test_controller_runs_profile_and_opens_results(tmp_path) -> None:
    app = _app()
    window = QMainWindow()
    runner = FakeRunner()
    controller = TenderSearchUiController(
        tmp_path,
        runtime=_runtime(tmp_path, runner),
        thread_pool=ImmediateThreadPool(),
        parent=window,
    )
    controller.install_on_main_window(window)
    controller.open_profiles_dialog()

    controller.run_profile("video-surveillance")
    app.processEvents()

    assert runner.calls == ["video-surveillance"]
    assert len(controller.result_dialogs) == 1
    assert controller.result_dialogs[0].table.rowCount() == 1
    assert controller.profiles_dialog is not None
    assert not controller.profiles_dialog.isVisible()


def test_controller_reports_search_error_in_profiles_dialog(
    tmp_path,
) -> None:
    app = _app()
    window = QMainWindow()
    runner = FakeRunner(error=RuntimeError("ЕИС недоступна"))
    controller = TenderSearchUiController(
        tmp_path,
        runtime=_runtime(tmp_path, runner),
        thread_pool=ImmediateThreadPool(),
        parent=window,
    )
    controller.open_profiles_dialog()

    controller.run_profile("video-surveillance")
    app.processEvents()

    assert controller.result_dialogs == ()
    assert controller.profiles_dialog is not None
    assert "ЕИС недоступна" in (controller.profiles_dialog.panel.status_label.text())
    assert controller.profiles_dialog.panel.run_button.isEnabled()


def test_controller_opens_existing_document_dialog_for_analysis_citation(
    tmp_path,
    monkeypatch,
) -> None:
    app = _app()
    document = TenderDocument(
        id="doc-1",
        name="Техническое задание.pdf",
        url="https://files.example.org/tz.pdf",
        mime_type="application/pdf",
    )
    tender = UnifiedTender(
        source=TenderSource.EIS,
        external_id="eis-1",
        procurement_number="0373100000126000001",
        title="Монтаж систем видеонаблюдения",
        customer=TenderCustomer(name="Заказчик"),
        source_url="https://zakupki.example.org/1",
        status=TenderStatus.ACCEPTING_APPLICATIONS,
        documents=(document,),
    )
    store = TenderDocumentStore(tmp_path / "documents")
    store.save_response(
        tender,
        document,
        HttpResponse(
            url=document.url,
            status_code=200,
            headers={"content-type": "application/pdf"},
            body=b"%PDF-1.4 test document",
        ),
    )
    stored = store.list_documents(tender_registry_key(tender))[0]
    runtime = replace(
        _runtime(tmp_path, FakeRunner()),
        tender_registry=FakeTenderRegistry(tender, tmp_path / "tender_registry.sqlite3"),
        document_store=store,
        document_service=object(),
    )
    window = QMainWindow()
    controller = TenderSearchUiController(
        tmp_path,
        runtime=runtime,
        thread_pool=ImmediateThreadPool(),
        parent=window,
    )
    opened_urls: list[object] = []
    monkeypatch.setattr(
        "app.ui.tender_documents_dialog.QDesktopServices.openUrl",
        lambda url: opened_urls.append(url),
    )

    controller.open_analysis_citation(tender_registry_key(tender), stored.document_key)
    app.processEvents()

    assert len(controller.document_dialogs) == 1
    dialog = controller.document_dialogs[0]
    assert dialog.selected_document() is not None
    assert dialog.selected_document().document_key == stored.document_key
    assert dialog.isVisible()
    assert opened_urls == []


def test_controller_installs_one_panel_and_routes_it_only_to_collector(
    tmp_path,
    monkeypatch,
) -> None:
    app = _app()
    page = _page(monkeypatch)
    runner = FakeRunner()
    collector_session = FakeCollectorSession()
    controller = TenderSearchUiController(
        tmp_path,
        runtime=_runtime(tmp_path, runner),
        collector_session=collector_session,
        thread_pool=ImmediateThreadPool(),
    )

    controller.install_on_tender_workspace(page)
    controller.install_on_tender_workspace(page)
    panel = controller.unified_search_panel
    assert panel is not None
    assert page.findChildren(type(panel)) == [panel]
    request = UnifiedTenderSearchRequest(
        panel.selected_profile_id(),
        "  камеры   IP  ",
        panel.selected_provider_ids(),
    )

    controller.start_unified_search(request)
    app.processEvents()

    assert len(collector_session.calls) == 1
    query, provider_ids = collector_session.calls[0]
    assert query.keywords == ("камеры IP",)
    assert provider_ids == ("eis",)
    assert runner.calls == []
    assert controller._collector_worker is None
    assert not panel.running
    assert "Поиск завершён" in panel.status_label.text()


def test_unified_search_rejects_stale_provider_without_starting_network(
    tmp_path,
    monkeypatch,
) -> None:
    _app()
    page = _page(monkeypatch)
    collector_session = FakeCollectorSession()
    controller = TenderSearchUiController(
        tmp_path,
        runtime=_runtime(tmp_path, FakeRunner()),
        collector_session=collector_session,
        thread_pool=ImmediateThreadPool(),
    )
    controller.install_on_tender_workspace(page)
    panel = controller.unified_search_panel
    assert panel is not None

    controller.start_unified_search(
        UnifiedTenderSearchRequest("all-corteris", "камеры", ("stale-source",))
    )

    assert collector_session.calls == []
    assert "не найден" in panel.status_label.text()
