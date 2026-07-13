from __future__ import annotations
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from app.tenders.full_analysis import FullAnalysisProgress, FullAnalysisStage
from app.ui.tender_full_analysis_dialog import TenderFullAnalysisDialog


def _app(): return QApplication.instance() or QApplication([])


def test_dialog_emits_cancel_and_updates_progress() -> None:
    app = _app()
    dialog = TenderFullAnalysisDialog("procurement:test")
    requested=[]
    dialog.cancel_requested.connect(requested.append)
    dialog.begin()
    dialog.update_progress(FullAnalysisProgress(
        stage=FullAnalysisStage.DOWNLOADING,
        message="Скачивание",
        completed_steps=2,
    ))
    dialog.cancel_button.click()
    assert requested == ["procurement:test"]
    assert dialog.progress.value() == 25
    app.processEvents()


def test_dialog_has_dedicated_ai_summary_tab() -> None:
    dialog = TenderFullAnalysisDialog("procurement:test")

    assert dialog.tabs.count() == 4
    assert dialog.tabs.tabText(2) == "AI summary"
    assert dialog.tabs.tabText(3) == "AI-анализ"
