"""Expected-red retirement contract for the narrow RM-155 cleanup island."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from app.ui.navigation import DEFAULT_ROUTE_REGISTRY, RouteId
from app.ui.pages.tender_workspace_page import TenderWorkspacePage


ROOT = Path(__file__).parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_old_public_shell_module_is_retired() -> None:
    assert not (ROOT / "app" / "ui" / "main_window.py").exists()
    assert importlib.util.find_spec("app.ui.main_window") is None


def test_repository_consumers_import_the_canonical_tender_page() -> None:
    obsolete = []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        if path.name == Path(__file__).name:
            continue
        if "app.ui.main_window" in path.read_text(encoding="utf-8"):
            obsolete.append(path.name)
    assert obsolete == []


def test_shell_exposes_only_the_canonical_workflow_page() -> None:
    source = _source("app/ui/modern_main_window.py")
    assert "quotes_page" not in source
    assert "estimates_page" not in source


def test_bootstrap_support_lookup_has_no_retired_page_fallback() -> None:
    source = _source("app/bootstrap.py")
    assert 'for attribute in ("workflow_page",):' in source
    assert "quotes_page" not in source
    assert "estimates_page" not in source


def test_obsolete_catalog_search_action_cannot_bypass_unified_search() -> None:
    assert not hasattr(TenderWorkspacePage, "apply_compatibility_search_text")
    assert hasattr(TenderWorkspacePage, "submit_unified_search_text")


def test_one_production_qmainwindow_entry_point_remains() -> None:
    ui_sources = {
        path.relative_to(ROOT).as_posix(): path.read_text(encoding="utf-8")
        for path in (ROOT / "app" / "ui").rglob("*.py")
    }
    owners = {
        path
        for path, source in ui_sources.items()
        if "class ModernMainWindow(QMainWindow)" in source
        or "class MainWindow(QMainWindow)" in source
    }
    assert owners == {"app/ui/modern_main_window.py"}


def test_retained_route_aliases_still_use_typed_admission() -> None:
    assert DEFAULT_ROUTE_REGISTRY.resolve("quotes").route_id is RouteId.WORKFLOW_PROPOSALS  # type: ignore[union-attr]
    assert DEFAULT_ROUTE_REGISTRY.resolve("ai").route_id is RouteId.TENDER_AI  # type: ignore[union-attr]
    assert DEFAULT_ROUTE_REGISTRY.resolve("clients").route_id is RouteId.FUTURE_CLIENTS  # type: ignore[union-attr]


def test_settings_and_visual_object_names_are_not_renamed_by_cleanup() -> None:
    shell = _source("app/ui/modern_main_window.py")
    page = _source("app/ui/pages/tender_workspace_page.py")
    assert 'value("ui/theme"' in shell and 'setValue("ui/theme"' in shell
    assert 'setObjectName("TenderWorkspaceTabs")' in page
    assert 'setObjectName("TenderWorkspaceSettingsTabs")' in page


def test_frozen_spec_never_collects_retired_shell_or_visual_review_data() -> None:
    spec = _source("installer/corteris_tender_ai.spec")
    assert "app.ui.main_window" not in spec
    assert "rm154-visual-artifacts" not in spec
    assert "rm154-v1" not in spec


def test_canonical_public_page_import_is_type_stable() -> None:
    from app.ui.pages.tender_workspace_page import TenderWorkspacePage as PublicPage

    assert PublicPage is TenderWorkspacePage
