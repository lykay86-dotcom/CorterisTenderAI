from __future__ import annotations

from types import SimpleNamespace
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.tenders.collector.store import CollectorStateRepository
from app.tenders.detail import TenderDetailAssembler
from app.tenders.tender_registry import TenderRegistryRepository, tender_registry_key
from app.ui.modern_main_window import ModernMainWindow
from app.ui.navigation import RouteContext
from app.ui.tender_registry_dialog import TenderRegistryDialog
from app.ui.tender_search_results_dialog import TenderSearchResultsDialog
from tests.tender_search_ui_helpers import make_profile_run
from tests.test_rm149_detail_assembler import _score


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_persisted_search_and_registry_publish_the_same_snapshot(tmp_path) -> None:
    app = _app()
    run = make_profile_run()
    repository = TenderRegistryRepository(tmp_path / "registry.sqlite3")
    repository.record_profile_run(run, run_id="parity-run")
    state = CollectorStateRepository(repository.path)
    tender = run.result.filter_result.accepted[0].tender
    registry_key = tender_registry_key(tender)
    state.save_score(registry_key, _score(hard_excluded=True), run_id="score-run")
    assembler = TenderDetailAssembler(repository, state)

    registry = TenderRegistryDialog(repository, verification_repository=state)
    registry.state_combo.setCurrentIndex(registry.state_combo.findData("active_all"))
    registry.refresh_records()
    search = TenderSearchResultsDialog(run, detail_assembler=assembler)

    registry_snapshot = registry.details.snapshot
    search_snapshot = search.details.snapshot
    assert registry_snapshot is not None
    assert search_snapshot is not None
    assert search_snapshot.identity == registry_snapshot.identity
    assert search_snapshot.decision == registry_snapshot.decision
    assert search_snapshot.critical_warnings == registry_snapshot.critical_warnings
    assert search_snapshot.primary_action.action_id == registry_snapshot.primary_action.action_id
    assert search_snapshot.fingerprint == registry_snapshot.fingerprint
    assert "Поисковая релевантность: 88/100" in search.details.toPlainText()
    assert "не решение об участии" in search.details.toPlainText()
    app.processEvents()


def test_typed_registry_route_dispatches_exact_key_without_legacy_guessing() -> None:
    opened: list[str] = []
    legacy: list[str] = []
    tender_page = SimpleNamespace(
        section_keys=frozenset({"overview"}),
        settings_section_keys=frozenset(),
        apply_dashboard_filter=lambda _value: None,
        open_tender=legacy.append,
        select_settings_section=lambda _value: True,
        select_section=lambda _value: True,
    )
    shell = SimpleNamespace(
        tender_workspace_page=tender_page,
        _tender_search_ui_controller=SimpleNamespace(
            open_registry_record=lambda key: opened.append(key) or True
        ),
    )

    result = ModernMainWindow._activate_tender_route(
        shell,
        RouteContext(tender_id="registry-key", tender_identity_kind="registry"),
    )

    assert result is True
    assert opened == ["registry-key"]
    assert legacy == []
