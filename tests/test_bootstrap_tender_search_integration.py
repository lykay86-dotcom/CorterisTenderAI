"""Static integration test for tender search installation at startup."""

from __future__ import annotations

from pathlib import Path


def test_bootstrap_installs_tender_search_controller() -> None:
    source = (Path(__file__).parents[1] / "app" / "bootstrap.py").read_text(encoding="utf-8")

    assert "TenderSearchUiController" in source
    assert "context.paths.data_dir" in source
    assert "install_on_main_window(window)" in source
    assert "install_on_tender_workspace(window.tender_workspace_page)" in source
