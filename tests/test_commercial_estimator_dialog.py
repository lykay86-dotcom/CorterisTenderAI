from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.tenders.collector.deduplicator import TenderDeduplicator
from app.tenders.collector.normalizer import TenderNormalizer
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.commercial_estimator import (
    CommercialEstimateRepository,
    CommercialEstimateStatus,
    CommercialEstimator,
)
from app.tenders.provider_base import TenderSearchQuery
from app.ui.commercial_estimator_dialog import CommercialEstimatorDialog
from tests.collector_c3_helpers import make_tender


def _app():
    return QApplication.instance() or QApplication([])


def test_blank_dialog_builds_honest_incomplete_draft(tmp_path) -> None:
    app = _app()
    database = tmp_path / "registry.sqlite3"
    state = CollectorStateRepository(database)
    tender = make_tender()
    normalized = TenderNormalizer().normalize(tender)
    run_id = state.start_run(TenderSearchQuery())
    state.save_batch(run_id, TenderDeduplicator().deduplicate((normalized,)))
    dialog = CommercialEstimatorDialog(
        normalized.canonical_key,
        CommercialEstimateRepository(database),
        tender=tender,
    )

    draft = dialog.build_draft()
    result = CommercialEstimator().calculate(draft)

    assert draft.proposed_revenue is None
    assert draft.lines == ()
    assert result.status == CommercialEstimateStatus.DATA_INSUFFICIENT
    assert dialog.revenue.text() == ""
    app.processEvents()
