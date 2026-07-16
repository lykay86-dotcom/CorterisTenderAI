"""RM-128 page, topbar and controller composition contract."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.ui.modern_main_window import ModernMainWindow
from app.ui.tender_unified_search_panel import TenderUnifiedSearchPanel
from app.ui.widgets.topbar import TopBar
from tests.test_rm127_modern_main_window_composition import _window
from tests.test_rm127_tender_workspace_contract import _page


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_workspace_hosts_one_panel_above_tabs_and_install_is_idempotent(monkeypatch) -> None:
    _app()
    page = _page(monkeypatch)
    panel = TenderUnifiedSearchPanel()

    assert page.submit_unified_search_text("камеры") is False
    page.install_unified_search_panel(panel)
    page.install_unified_search_panel(panel)

    assert page.findChildren(TenderUnifiedSearchPanel) == [panel]
    assert page.layout().indexOf(panel) == 0
    assert page.layout().indexOf(page.tabs) == 1


def test_topbar_is_explicit_tender_search_and_does_not_touch_catalog(monkeypatch) -> None:
    app = _app()
    window: ModernMainWindow = _window(monkeypatch)
    panel = TenderUnifiedSearchPanel()
    window.tender_workspace_page.install_unified_search_panel(panel)
    submitted: list[str] = []
    panel.query_submitted.connect(submitted.append)
    window.tender_workspace_page.catalog_query.setText("прайс остаётся")

    window._global_search("  тепловизоры  ")

    assert window.workspace.sidebar.current_item == "tenders"
    assert submitted == ["тепловизоры"]
    assert window.tender_workspace_page.catalog_query.text() == "прайс остаётся"
    assert window.workspace.topbar.search.placeholderText() == "Поиск тендеров…"

    window.close()
    window.deleteLater()
    app.processEvents()


def test_topbar_emits_one_string() -> None:
    _app()
    topbar = TopBar()
    requested: list[str] = []
    topbar.search_requested.connect(requested.append)
    topbar.search.setText("камеры")

    topbar.search.returnPressed.emit()

    assert requested == ["камеры"]
