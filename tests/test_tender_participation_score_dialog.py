"""PySide6 tests for the participation score dialog."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.tenders.collector.participation_score import (
    CorterisParticipationRanker,
    ParticipationScoringContext,
)
from app.tenders.collector.stop_factor import StopFactorEngine
from app.ui.tender_participation_score_dialog import (
    TenderParticipationScoreDialog,
)
from app.tenders.participation_decision import (
    ParticipationDecision,
    ParticipationDecisionEvidence,
    ParticipationDecisionInput,
    ParticipationDecisionRecommendation,
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


def test_dialog_renders_structured_stop_factor_evidence() -> None:
    app = _app()
    tender = make_tender()
    assessment = StopFactorEngine().evaluate(
        "procurement:test",
        tender,
    )
    score = CorterisParticipationRanker().score(
        tender,
        ParticipationScoringContext(stop_factor_assessment=assessment),
    )
    dialog = TenderParticipationScoreDialog(
        "procurement:test",
        score=score,
    )

    rendered = dialog.details.toPlainText()
    assert "DATA_INSUFFICIENT" in rendered
    assert "Файл:" in rendered
    assert "Страница:" in rendered
    assert "Confidence:" in rendered
    assert "Способ устранения:" in rendered
    app.processEvents()


def test_dialog_renders_explainable_decision_and_action_plan() -> None:
    dialog = TenderParticipationScoreDialog("procurement:test")
    decision = ParticipationDecision(
        decision_id="decision",
        registry_key="procurement:test",
        recommendation=ParticipationDecisionRecommendation.PARTICIPATE_AFTER_REVIEW,
        confidence=0.65,
        summary="Review required.",
        evidence=(
            ParticipationDecisionEvidence(
                "missing_contract",
                "Project contract",
                "Document is missing.",
                0.65,
                "documents",
                -8,
            ),
        ),
        input=ParticipationDecisionInput(registry_key="procurement:test"),
        decided_at="2026-07-13T00:00:00+00:00",
        policy_version="rm-107-v2",
        score=71,
        stop_factors=("License check",),
        missing=("Project contract",),
        actions=("Request project contract",),
    )

    dialog.set_decision(decision)
    rendered = dialog.decision_label.text()

    assert "71/100" in rendered
    assert "65%" in rendered
    assert "Project contract" in rendered
    assert "License check" in rendered
    assert "Request project contract" in rendered
