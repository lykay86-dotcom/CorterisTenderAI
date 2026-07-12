"""PySide6 tests for the participation score dialog."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.tenders.collector.participation_score import (
    CorterisParticipationRanker,
)
from app.ui.tender_participation_score_dialog import (
    TenderParticipationScoreDialog,
)
from tests.collector_c3_helpers import make_tender


def _app():
    return QApplication.instance() or QApplication([])


def test_dialog_renders_components_and_recalculate_signal() -> None:
    app = _app()
    score = CorterisParticipationRanker().score(make_tender())
    dialog = TenderParticipationScoreDialog(
        "procurement:test",
        score=score,
    )
    requested = []
    dialog.recalculate_requested.connect(requested.append)

    dialog.recalculate_button.click()

    assert dialog.components_table.rowCount() == len(score.components)
    assert requested == ["procurement:test"]
    app.processEvents()
