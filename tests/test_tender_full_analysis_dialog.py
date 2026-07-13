from __future__ import annotations
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
import pytest

from app.core.ai.schemas import (
    AiDocumentAnalysis,
    AiEvidence,
    AiFinding,
    AiFindingStatus,
)
from app.tenders.full_analysis import (
    FullAnalysisProgress,
    FullAnalysisStage,
    FullAnalysisStatus,
    TenderFullAnalysisResult,
)
from app.ui.tender_full_analysis_dialog import (
    TenderFullAnalysisDialog,
    _render_ai_document_analysis,
)


def _app():
    return QApplication.instance() or QApplication([])


def test_dialog_emits_cancel_and_updates_progress() -> None:
    app = _app()
    dialog = TenderFullAnalysisDialog("procurement:test")
    requested = []
    dialog.cancel_requested.connect(requested.append)
    dialog.begin()
    dialog.update_progress(
        FullAnalysisProgress(
            stage=FullAnalysisStage.DOWNLOADING,
            message="Скачивание",
            completed_steps=2,
        )
    )
    dialog.cancel_button.click()
    assert requested == ["procurement:test"]
    assert dialog.progress.value() == 25
    app.processEvents()


def test_dialog_has_dedicated_ai_summary_tab() -> None:
    dialog = TenderFullAnalysisDialog("procurement:test")

    assert dialog.tabs.count() == 4
    assert dialog.tabs.tabText(2) == "AI summary"
    assert dialog.tabs.tabText(3) == "AI-анализ"


def _result(analysis: AiDocumentAnalysis) -> TenderFullAnalysisResult:
    return TenderFullAnalysisResult(
        registry_key="procurement:test",
        procurement_number="test",
        status=FullAnalysisStatus.PARTIAL,
        started_at="2026-07-13T00:00:00+03:00",
        completed_at="2026-07-13T00:01:00+03:00",
        download=None,
        archives=None,
        text=None,
        requirements=None,
        score=None,
        legacy=None,
        ai_document_analysis=analysis,
    )


@pytest.mark.parametrize(
    ("status", "label"),
    [
        ("complete", "Завершён"),
        ("partial", "Частичный результат"),
        ("no_documents", "Нет документов для анализа"),
        ("provider_disabled", "AI-провайдер отключён"),
        ("provider_error", "AI-провайдер недоступен"),
        ("invalid_response", "Ответ AI отклонён"),
        ("cache_incompatible", "Кеш несовместим"),
    ],
)
def test_ai_tab_has_safe_human_readable_status(status: str, label: str) -> None:
    html = _render_ai_document_analysis(
        _result(AiDocumentAnalysis("procurement:test", "Safe", status=status))
    )

    assert label in html


def test_ai_tab_distinguishes_verified_and_unverified_findings() -> None:
    verified = AiFinding(
        "risk",
        "Confirmed",
        AiEvidence("doc", "exact quote", confidence=0.8),
        AiFindingStatus.VERIFIED,
    )
    unverified = AiFinding("risk", "Unconfirmed", None, AiFindingStatus.UNVERIFIED)
    html = _render_ai_document_analysis(
        _result(
            AiDocumentAnalysis(
                "procurement:test",
                "Safe",
                risks=(verified, unverified),
                status="partial",
            )
        )
    )

    assert "exact quote" in html
    assert "Неподтверждённый вывод" in html


def test_ai_tab_displays_truncated_context_warning_without_traceback() -> None:
    html = _render_ai_document_analysis(
        _result(
            AiDocumentAnalysis(
                "procurement:test",
                "Safe",
                status="partial",
                warnings=("Контекст сокращён.",),
                context_document_count=2,
                context_character_count=100,
                context_truncated=True,
            )
        )
    )

    assert "2 документов" in html
    assert "контекст сокращён" in html.casefold()
    assert "Traceback" not in html


def test_dialog_can_render_successful_retry_after_error() -> None:
    dialog = TenderFullAnalysisDialog("procurement:test")
    dialog.set_error("temporary failure")

    dialog.set_result(
        _result(AiDocumentAnalysis("procurement:test", "Recovered", status="complete"))
    )

    assert "Recovered" in dialog.ai_analysis.toPlainText()
    assert dialog.export_ai_button.isEnabled()
