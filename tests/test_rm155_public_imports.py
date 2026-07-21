"""Final supported/retired import contract for the redesigned application."""

from __future__ import annotations

import importlib
import importlib.util

import pytest


@pytest.mark.parametrize(
    "module_name,symbol",
    (
        ("app.ui.modern_main_window", "ModernMainWindow"),
        ("app.ui.pages.tender_workspace_page", "TenderWorkspacePage"),
        ("app.ui.controllers", "DashboardController"),
        ("app.ui.navigation", "DEFAULT_ROUTE_REGISTRY"),
        ("app.ui.charts", "ChartSpec"),
        ("app.tenders.analytics", "TenderAnalyticsService"),
        ("app.financial", "MoneyAmount"),
        ("app.tenders.detail", "TenderDetailSnapshot"),
        ("app.ui.tables", "TableSnapshot"),
        ("app.operations", "OperationEpisode"),
    ),
)
def test_supported_redesign_imports_are_explicit(module_name: str, symbol: str) -> None:
    module = importlib.import_module(module_name)
    assert getattr(module, symbol) is not None
    assert symbol in getattr(module, "__all__", ())


def test_retired_shell_import_fails_without_a_shadow_module() -> None:
    assert importlib.util.find_spec("app.ui.main_window") is None
    with pytest.raises(ModuleNotFoundError, match="app.ui.main_window"):
        importlib.import_module("app.ui.main_window")
