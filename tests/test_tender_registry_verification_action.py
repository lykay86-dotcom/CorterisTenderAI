"""Registry verification badge and action tests."""

from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.tenders.collector.deduplicator import TenderDeduplicator
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.collector.verification import TenderVerificationService
from app.tenders.provider_base import TenderSearchQuery
from app.tenders.tender_registry import TenderRegistryRepository
from app.ui.tender_registry_dialog import TenderRegistryDialog
from tests.collector_c3_helpers import make_tender


def _app():
    return QApplication.instance() or QApplication([])


def test_registry_shows_verification_column_and_signal(tmp_path) -> None:
    app = _app()
    path = tmp_path / "registry.sqlite3"
    collector = CollectorStateRepository(path)
    collector.start_run(TenderSearchQuery(), run_id="registry-ui")
    verification = TenderVerificationService().verify(
        TenderDeduplicator().deduplicate((make_tender(),))
    )
    collector.save_batch(
        "registry-ui",
        verification.deduplication,
        verification=verification,
    )
    registry = TenderRegistryRepository(path)
    dialog = TenderRegistryDialog(
        registry,
        verification_repository=collector,
    )
    requested = []
    dialog.verification_requested.connect(requested.append)
    dialog.table.selectRow(0)

    assert dialog.verification_button.isEnabled()
    dialog.verification_button.click()

    assert dialog.table.columnCount() == 12
    assert dialog.table.horizontalHeaderItem(2).text() == "Достоверность"
    assert requested
    app.processEvents()
