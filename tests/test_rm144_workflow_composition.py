"""Expected-red contract for one production workflow page and destination."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.core.system_health_monitor import SystemHealthMonitor
from app.repositories.business_metrics import BusinessRecordKind
from app.ui.navigation import NavigationCause, RouteId, RouteRequest
from app.ui.pages.business_workflow_page import BusinessWorkflowPage
from tests.test_rm127_modern_main_window_composition import _window as _rm127_window


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _window(monkeypatch):
    monkeypatch.setattr(
        "app.ui.pages.business_workflow_page.SystemHealthMonitor.request_refresh",
        lambda _self: False,
    )
    return _rm127_window(monkeypatch)


def test_all_workflow_routes_share_one_physical_destination() -> None:
    from app.ui.navigation import DEFAULT_ROUTE_REGISTRY

    assert {
        DEFAULT_ROUTE_REGISTRY.get(route_id).destination
        for route_id in (
            RouteId.WORKFLOW,
            RouteId.WORKFLOW_PROPOSALS,
            RouteId.WORKFLOW_ESTIMATES,
            RouteId.WORKFLOW_PROJECTS,
        )
    } == {"workflow"}


def test_production_shell_constructs_one_workflow_owner(monkeypatch) -> None:
    app = _app()
    window = _window(monkeypatch)

    assert window.workflow_page is window.quotes_page
    assert window.workflow_page is window.estimates_page
    assert window.findChildren(BusinessWorkflowPage) == [window.workflow_page]
    assert window.findChildren(SystemHealthMonitor) == [window.workflow_page.system_health_monitor]
    assert tuple(window.workspace._page_index) == (
        "dashboard",
        "tenders",
        "workflow",
    )
    assert window.workspace.pages.count() == 3

    window.close()
    window.deleteLater()
    app.processEvents()


def test_child_route_intents_reuse_page_and_apply_exact_kind(monkeypatch) -> None:
    app = _app()
    window = _window(monkeypatch)

    for route_id, kind in (
        (RouteId.WORKFLOW_PROPOSALS, BusinessRecordKind.PROPOSAL),
        (RouteId.WORKFLOW_ESTIMATES, BusinessRecordKind.ESTIMATE),
        (RouteId.WORKFLOW_PROJECTS, BusinessRecordKind.PROJECT),
    ):
        result = window.workspace.navigate(
            RouteRequest(route_id, cause=NavigationCause.PROGRAMMATIC)
        )
        assert result.succeeded
        assert window.workspace.pages.currentWidget() is window.workflow_page
        assert window.workflow_page.kind_filter.currentData() == kind.value

    window.close()
    window.deleteLater()
    app.processEvents()
