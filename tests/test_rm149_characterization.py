"""Passing characterization of RM-149 inherited tender-detail seams."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import inspect
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.tenders.tender_registry import TenderRegistryRepository
from app.ui.controllers.dashboard_controller import DashboardSnapshotBuilder
from app.ui.navigation import RouteContext
from app.ui.tender_registry_dialog import TenderRegistryDialog
from app.ui.tender_search_results_dialog import TenderSearchResultsDialog
from app.ui.tender_search_ui_controller import TenderSearchUiController
from tests.tender_search_ui_helpers import make_profile_run
from tests.test_tender_registry import _evaluated_tender, _run


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


@dataclass
class _LegacyTender:
    id: str
    number: str
    title: str = "Legacy tender"
    customer: str = "Customer"
    nmck: Decimal = Decimal("100.00")
    deadline: str = "2026-07-31"
    score: int = 80
    recommendation: str = "Legacy recommendation"
    status: str = "New"
    platform: str = "Manual"
    created_at: datetime = datetime(2026, 7, 19, tzinfo=timezone.utc)
    analyses: tuple[object, ...] = ()


def test_legacy_route_context_carries_an_untyped_tender_string() -> None:
    context = RouteContext(tender_id="42")

    assert context.tender_id == "42"
    assert "tender_identity_kind" not in RouteContext.field_names()


def test_dashboard_feed_maps_display_number_to_legacy_orm_id() -> None:
    snapshot = DashboardSnapshotBuilder().build(
        [_LegacyTender(id="orm-42", number="0373100000126000001")],
        now=datetime(2026, 7, 19, 12, tzinfo=timezone.utc),
    )

    assert snapshot.number_to_id == {"0373100000126000001": "orm-42"}
    assert snapshot.tenders[0].number == "0373100000126000001"


def test_registry_detail_uses_exact_registry_key_but_local_html(tmp_path) -> None:
    app = _app()
    repository = TenderRegistryRepository(tmp_path / "tender_registry.sqlite3")
    repository.record_profile_run(_run(_evaluated_tender()), run_id="run-1")
    record = repository.get_by_procurement_number("0373100000126000001")
    assert record is not None

    dialog = TenderRegistryDialog(repository)

    assert dialog.select_registry_key(record.registry_key)
    assert dialog.selected_record() == record
    text = dialog.details.toPlainText()
    assert record.title in text
    assert "Последняя релевантность" in text
    assert "Достоверность данных" in text
    app.processEvents()


def test_search_result_renders_relevance_without_persisted_decision() -> None:
    _app()
    dialog = TenderSearchResultsDialog(make_profile_run())

    text = dialog.details.toPlainText()
    assert "Релевантность: 88/100" in text
    assert "Почему закупка подходит" in text
    assert "Решение об участии" not in text


def test_existing_controller_remains_the_single_registry_action_owner() -> None:
    source = inspect.getsource(TenderSearchUiController.open_registry_dialog)

    assert "TenderRegistryDialog" in source
    assert "documents_requested.connect(self.open_registry_documents)" in source
    assert "score_requested.connect(self.open_participation_score)" in source
    assert "verification_requested.connect(self.open_verification_details)" in source
