"""RM-142 characterization of navigation compatibility inputs."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

from app.repositories.business_metrics import BusinessRecordKind
from app.ui.dashboard.quick_actions import DEFAULT_QUICK_ACTIONS
from app.ui.pages.tender_workspace_page import TenderWorkspacePage
from app.ui.widgets.dashboard_layout import DashboardLayout


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_legacy_add_page_and_sidebar_select_keep_page_and_title_contract() -> None:
    _app()
    layout = DashboardLayout()
    dashboard = QWidget()
    tenders = QWidget()
    layout.add_page("dashboard", "Рабочий стол", dashboard)
    layout.add_page("tenders", "Тендеры и рабочие модули", tenders)

    layout.sidebar.select("tenders")

    assert layout.pages.currentWidget() is tenders
    assert layout.topbar.page_title.text() == "Тендеры и рабочие модули"
    assert layout.sidebar.current_item == "tenders"

    layout.sidebar.select("unknown-route")

    assert layout.pages.currentWidget() is tenders
    assert layout.topbar.page_title.text() == "Тендеры и рабочие модули"


def test_dashboard_quick_action_keys_remain_compatibility_inputs() -> None:
    assert tuple(spec.key for spec in DEFAULT_QUICK_ACTIONS) == (
        "find_tenders",
        "analyze_documents",
        "create_proposal",
        "create_estimate",
    )


def test_tender_embedded_keys_and_workflow_kind_values_are_stable() -> None:
    assert TenderWorkspacePage.SECTION_KEYS == (
        "overview",
        "analysis",
        "estimate",
        "catalog",
        "readiness",
        "tools",
        "price_monitor",
        "settings",
    )
    assert TenderWorkspacePage.SETTINGS_SECTION_KEYS == (
        "platforms",
        "ai",
        "company",
        "economics",
        "templates",
        "database",
    )
    assert {kind.value for kind in BusinessRecordKind} == {
        "proposal",
        "estimate",
        "project",
    }
