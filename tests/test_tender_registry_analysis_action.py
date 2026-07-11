"""Tests for launching analysis from the tender registry."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.tenders.tender_registry import TenderRegistryRepository
from app.ui.tender_registry_dialog import TenderRegistryDialog
from tests.test_tender_registry import _evaluated_tender, _run


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_registry_dialog_requests_analysis_for_selected_tender(
    tmp_path,
) -> None:
    app = _app()
    repository = TenderRegistryRepository(
        tmp_path / "tender_registry.sqlite3"
    )
    repository.record_profile_run(
        _run(_evaluated_tender()),
        run_id="run-analysis",
    )
    dialog = TenderRegistryDialog(repository)
    requested: list[str] = []
    dialog.analysis_requested.connect(requested.append)

    dialog.analysis_button.click()

    assert requested == [dialog.records[0].registry_key]
    assert dialog.analysis_button.isEnabled()
    app.processEvents()
