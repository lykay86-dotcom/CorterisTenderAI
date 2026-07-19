"""Expected-red canonical navigation and exact registry drill-down contracts."""

from __future__ import annotations

import inspect
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.tenders.tender_registry import TenderRegistryRepository
from app.ui.modern_main_window import ModernMainWindow
from app.ui.navigation import (
    DEFAULT_ROUTE_REGISTRY,
    RouteAvailability,
    RouteId,
    RouteKind,
)
from app.ui.tender_registry_dialog import TenderRegistryDialog
from tests.test_tender_registry import _evaluated_tender, _run


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_canonical_registry_and_shell_own_analytics_activation() -> None:
    route = DEFAULT_ROUTE_REGISTRY.get(RouteId.FUTURE_ANALYTICS)

    assert route.kind is RouteKind.PRIMARY
    assert route.availability is RouteAvailability.AVAILABLE
    assert route.destination == "analytics"
    assert route.show_in_primary
    assert DEFAULT_ROUTE_REGISTRY.primary_routes[3] is route
    source = inspect.getsource(ModernMainWindow)
    assert "_show_analytics_page" in source
    assert '"analytics"' in source


def test_registry_drilldown_preselects_exact_registry_key(tmp_path) -> None:
    app = _app()
    repository = TenderRegistryRepository(tmp_path / "tender_registry.sqlite3")
    repository.record_profile_run(
        _run(
            _evaluated_tender(score=95),
            _evaluated_tender(
                procurement_number="0373100000126000002",
                external_id="eis-2",
                score=70,
            ),
        ),
        run_id="run-1",
    )
    exact_key = repository.get_by_procurement_number("0373100000126000002").registry_key
    dialog = TenderRegistryDialog(repository)

    assert dialog.select_registry_key(exact_key)
    assert dialog.selected_record() is not None
    assert dialog.selected_record().registry_key == exact_key
    app.processEvents()
