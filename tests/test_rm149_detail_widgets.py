from __future__ import annotations

from datetime import datetime, timezone
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton

from app.tenders.detail import (
    TenderDetailAssembler,
    TenderIdentity,
    TenderIdentityKind,
    project_tender_card,
)
from app.ui.widgets.tender_detail import TenderCard, TenderDetailPanel
from tests.test_rm149_detail_assembler import (
    RegistryFake,
    StateFake,
    _freshness,
    _record,
    _score,
    _verification,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _snapshot():
    return TenderDetailAssembler(
        RegistryFake(_record()),
        StateFake(
            score=_score(hard_excluded=True),
            verification=_verification(unresolved=1),
            freshness=_freshness(),
        ),
        clock=lambda: datetime(2026, 7, 19, 9, 0, tzinfo=timezone.utc),
    ).assemble(TenderIdentity(TenderIdentityKind.REGISTRY, "registry-key"))


def test_detail_panel_renders_critical_first_with_text_and_one_primary_action() -> None:
    _app()
    panel = TenderDetailPanel()
    snapshot = _snapshot()

    panel.set_snapshot(snapshot)

    assert panel.layout().itemAt(0).widget().objectName() == "TenderDetailCriticalSection"
    assert panel.layout().itemAt(0).widget().isVisibleTo(panel)
    assert "Blocking participation factor" in panel.toPlainText()
    assert "<script>alert(1)</script>" in panel.toPlainText()
    primary = panel.findChild(QPushButton, "TenderDetailPrimaryAction")
    assert primary is not None
    assert primary.text() == snapshot.primary_action.label
    assert primary.accessibleDescription() == snapshot.primary_action.accessible_description


def test_detail_panel_republication_does_not_grow_action_widgets() -> None:
    app = _app()
    panel = TenderDetailPanel()
    snapshot = _snapshot()
    panel.set_snapshot(snapshot)
    initial_count = len(panel.findChildren(QPushButton))

    for _ in range(10):
        panel.set_snapshot(snapshot)
        app.processEvents()

    assert len(panel.findChildren(QPushButton)) == initial_count


def test_compact_card_preserves_snapshot_identity_decision_and_primary_action() -> None:
    _app()
    snapshot = _snapshot()
    card = TenderCard()

    card.set_projection(project_tender_card(snapshot))

    assert card.identity == snapshot.identity
    assert card.snapshot_fingerprint == snapshot.fingerprint
    assert snapshot.primary_action.label in card.toPlainText()
    assert snapshot.decision is not None
    assert snapshot.decision.recommendation in card.toPlainText()
