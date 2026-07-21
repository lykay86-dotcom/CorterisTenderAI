"""Passing RM-155 characterization before compatibility retirement."""

from __future__ import annotations

import inspect
from pathlib import Path

from app.bootstrap import _find_support_bundle_provider
from app.ui.navigation import DEFAULT_ROUTE_REGISTRY, RouteId
from app.ui.pages.tender_workspace_page import TenderWorkspacePage


ROOT = Path(__file__).parents[1]


class _SupportPage:
    def create_diagnostic_support_bundle(self, target: str) -> str:
        return target


def test_canonical_tender_page_is_the_only_page_implementation() -> None:
    source = inspect.getsource(TenderWorkspacePage)
    assert TenderWorkspacePage.__module__ == "app.ui.pages.tender_workspace_page"
    assert "class TenderWorkspacePage" in source
    assert not (ROOT / "app" / "ui" / "main_window.py").exists()


def test_support_bundle_lookup_prefers_the_canonical_workflow_page() -> None:
    canonical = _SupportPage()
    window = type(
        "Window",
        (),
        {
            "workflow_page": canonical,
        },
    )()

    provider = _find_support_bundle_provider(window)

    assert provider is not None
    assert provider.__self__ is canonical


def test_temporary_workflow_aliases_are_retired() -> None:
    source = (ROOT / "app" / "ui" / "modern_main_window.py").read_text(encoding="utf-8")
    assert "quotes_page" not in source
    assert "estimates_page" not in source


def test_retained_route_aliases_have_exact_safe_dispositions() -> None:
    expected = {
        "dashboard": RouteId.DASHBOARD,
        "tenders": RouteId.TENDERS,
        "quotes": RouteId.WORKFLOW_PROPOSALS,
        "estimates": RouteId.WORKFLOW_ESTIMATES,
        "ai": RouteId.TENDER_AI,
        "settings": RouteId.TENDER_SETTINGS,
        "documents": RouteId.TENDER_DOCUMENTS,
        "analytics": RouteId.FUTURE_ANALYTICS,
        "clients": RouteId.FUTURE_CLIENTS,
    }
    assert {
        alias: DEFAULT_ROUTE_REGISTRY.resolve(alias).route_id  # type: ignore[union-attr]
        for alias in expected
    } == expected


def test_theme_setting_and_visual_object_names_remain_contract_inputs() -> None:
    shell = (ROOT / "app" / "ui" / "modern_main_window.py").read_text(encoding="utf-8")
    page = (ROOT / "app" / "ui" / "pages" / "tender_workspace_page.py").read_text(encoding="utf-8")
    assert 'value("ui/theme"' in shell
    assert 'setValue("ui/theme"' in shell
    assert 'setObjectName("TenderWorkspaceTabs")' in page
    assert 'setObjectName("TenderWorkspaceSettingsTabs")' in page


def test_frozen_spec_has_no_old_shell_hidden_import_or_visual_artifact() -> None:
    spec = (ROOT / "installer" / "corteris_tender_ai.spec").read_text(encoding="utf-8")
    assert "app.ui.main_window" not in spec
    assert "rm154-visual-artifacts" not in spec
    assert "rm154-v1" not in spec
