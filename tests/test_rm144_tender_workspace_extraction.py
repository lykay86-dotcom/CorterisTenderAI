"""Expected-red contract for canonical tender workspace ownership."""

from __future__ import annotations

import inspect

from app.ui.pages.tender_workspace_page import TenderWorkspacePage


def test_canonical_page_module_owns_the_single_implementation() -> None:
    assert TenderWorkspacePage.__module__ == "app.ui.pages.tender_workspace_page"
    assert "class TenderWorkspacePage" in inspect.getsource(
        __import__(
            "app.ui.pages.tender_workspace_page",
            fromlist=["TenderWorkspacePage"],
        )
    )


def test_legacy_main_window_module_is_retired() -> None:
    from pathlib import Path

    assert not Path("app/ui/main_window.py").exists()
