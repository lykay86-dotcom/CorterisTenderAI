from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.tenders.collector.aggregator_discovery import (
    AggregatorDiscoveryRepository,
)
from app.tenders.models import TenderSource
from app.ui.aggregator_discovery_dialog import AggregatorDiscoveryDialog
from tests.collector_c3_helpers import make_tender


def _app():
    return QApplication.instance() or QApplication([])


def test_dialog_displays_pending_discovery(tmp_path) -> None:
    app = _app()
    repository = AggregatorDiscoveryRepository(tmp_path / "registry.sqlite3")
    repository.enqueue(make_tender(
        source=TenderSource.CUSTOM,
        external_id="agg-ui",
        raw_metadata={"aggregator": True},
    ))

    dialog = AggregatorDiscoveryDialog(repository)

    assert dialog.table.rowCount() == 1
    assert dialog.table.item(0, 0).text() == "pending_official_verification"
    assert dialog.table.item(0, 3).text()
    app.processEvents()
