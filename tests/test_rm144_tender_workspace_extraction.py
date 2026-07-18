"""Expected-red contract for canonical tender workspace ownership."""

from __future__ import annotations

import inspect

from app.ui.main_window import MainWindow, TenderWorkspacePage as LegacyTenderWorkspacePage
from app.ui.pages.tender_workspace_page import TenderWorkspacePage


def test_canonical_page_module_owns_the_single_implementation() -> None:
    assert TenderWorkspacePage.__module__ == "app.ui.pages.tender_workspace_page"
    assert LegacyTenderWorkspacePage is TenderWorkspacePage
    assert "class TenderWorkspacePage" in inspect.getsource(
        __import__(
            "app.ui.pages.tender_workspace_page",
            fromlist=["TenderWorkspacePage"],
        )
    )


def test_legacy_main_window_is_only_a_compatibility_wrapper() -> None:
    module_source = inspect.getsource(__import__("app.ui.main_window", fromlist=["MainWindow"]))

    assert "class TenderWorkspacePage" not in module_source
    assert MainWindow.__module__ == "app.ui.main_window"
    assert LegacyTenderWorkspacePage is TenderWorkspacePage
