"""Registry verification badge and action tests."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.tenders.collector.deduplicator import TenderDeduplicator
from app.tenders.collector.freshness import TenderFreshnessService
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
        TenderDeduplicator().deduplicate((make_tender(),)),
        observed_at="2026-07-12T12:00:00+00:00",
    )
    freshness = TenderFreshnessService(user_timezone="UTC").evaluate(
        verification,
        now="2026-07-12T12:00:00+00:00",
    )
    collector.save_batch(
        "registry-ui",
        verification.deduplication,
        verification=verification,
        freshness=freshness,
    )
    registry = TenderRegistryRepository(path)
    dialog = TenderRegistryDialog(
        registry,
        verification_repository=collector,
    )
    requested = []
    dialog.verification_requested.connect(requested.append)

    # save_batch() above intentionally receives no participation ranking.
    # Such a record is active but not marked as last_accepted, while the
    # registry dialog defaults to the "Активные релевантные" filter.
    # Switch to "Все активные" before testing the verification action.
    all_active_index = dialog.state_combo.findData("active_all")
    assert all_active_index >= 0
    dialog.state_combo.setCurrentIndex(all_active_index)
    app.processEvents()

    assert dialog.table.rowCount() == 1
    dialog.table.selectRow(0)
    app.processEvents()

    assert dialog.verification_button.isEnabled()
    dialog.verification_button.click()

    assert dialog.table.columnCount() == 13
    assert dialog.table.horizontalHeaderItem(2).text() == "Достоверность"
    assert dialog.table.horizontalHeaderItem(3).text() == "Свежесть"
    assert dialog.table.item(0, 3).text() != "Не рассчитана"
    freshness_tooltip = dialog.table.item(0, 3).toolTip()
    assert "Исходный срок:" in freshness_tooltip
    assert "Часовой пояс источника:" in freshness_tooltip
    assert "UTC:" in freshness_tooltip
    assert "Время пользователя:" in freshness_tooltip
    assert requested
    app.processEvents()
