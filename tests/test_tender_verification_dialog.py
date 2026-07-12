"""PySide6 verification-dialog contract tests."""

from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.tenders.collector.deduplicator import TenderDeduplicator
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.collector.verification import TenderVerificationService
from app.tenders.collector.verification_review import (
    TenderVerificationReviewService,
)
from app.tenders.models import TenderSource
from app.tenders.provider_base import TenderSearchQuery
from app.ui.tender_verification_dialog import TenderVerificationDialog
from tests.collector_c3_helpers import make_tender


def _app():
    return QApplication.instance() or QApplication([])


def _review(tmp_path):
    repository = CollectorStateRepository(tmp_path / "registry.sqlite3")
    repository.start_run(TenderSearchQuery(), run_id="ui-run")
    verification = TenderVerificationService().verify(
        TenderDeduplicator().deduplicate(
            (
                make_tender(source=TenderSource.EIS, external_id="ui-eis"),
                make_tender(
                    source=TenderSource.CUSTOM,
                    external_id="ui-agg",
                    amount="1700000.00",
                    raw_metadata={"aggregator": True},
                ),
            )
        )
    )
    repository.save_batch(
        "ui-run",
        verification.deduplication,
        verification=verification,
    )
    key = verification.deduplication.items[0].canonical_key
    return TenderVerificationReviewService(repository).load(key)


def test_dialog_renders_fields_and_emits_resolution(tmp_path) -> None:
    app = _app()
    review = _review(tmp_path)
    dialog = TenderVerificationDialog(review)
    emitted = []
    dialog.resolve_requested.connect(
        lambda *args: emitted.append(args)
    )
    price_row = next(
        index
        for index, field in enumerate(review.fields)
        if field.field_name == "price"
    )
    dialog.fields_table.selectRow(price_row)
    dialog.candidates_table.selectRow(0)
    dialog.select_button.click()

    assert dialog.fields_table.rowCount() == len(review.fields)
    assert emitted
    assert emitted[0][0] == review.registry_key
    assert emitted[0][1] == "price"
    app.processEvents()
