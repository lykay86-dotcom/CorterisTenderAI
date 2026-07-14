from __future__ import annotations
from dataclasses import replace
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication
import pytest

from app.core.ai.schemas import (
    AI_ANALYSIS_SCHEMA_VERSION,
    AiAnalysisProvenance,
    AiDocument,
    AiDocumentAnalysis,
    AiFinding,
    AiFindingStatus,
    AiSourceSnapshot,
    AiTechnicalSpecificationAnalysis,
    AiTechnicalSpecificationStatus,
)
from app.core.ai.citations import resolve_citation
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


def _current_analysis() -> AiDocumentAnalysis:
    fingerprint = "d" * 64
    checksum = "b" * 64
    document = AiDocument(
        "doc",
        "tender.pdf",
        "local_document_store",
        "pdf",
        "2026-07-14T10:00:00+00:00",
        "verified",
        "exact quote",
        checksum,
        original_character_count=11,
    )
    evidence = resolve_citation(
        document_id="doc",
        quote="exact quote",
        section="Раздел 1",
        page=2,
        confidence=0.8,
        documents=(document,),
        context_fingerprint=fingerprint,
    ).evidence
    assert evidence is not None
    evidence = replace(evidence, section="Раздел 1", page=2)
    source = AiSourceSnapshot(
        document_id="doc",
        display_name="tender.pdf",
        document_type="pdf",
        checksum_sha256=checksum,
        verification_status="verified",
        received_at="2026-07-14T10:00:00+00:00",
        truncated=True,
        included_character_count=11,
        original_character_count=20,
    )
    provenance = AiAnalysisProvenance(
        analysis_id="analysis_123",
        context_fingerprint=fingerprint,
        created_at="2026-07-14T10:01:00+00:00",
        prompt_version="4",
        output_schema_version="2",
        persisted_schema_version=AI_ANALYSIS_SCHEMA_VERSION,
        analyzer_version="5",
        context_version="3",
        citation_resolver_version="1",
        provider_id="openai",
        provider_model="gpt-5",
        provider_response_id="resp_" + "a" * 64,
        sources=(source,),
    )
    verified = AiFinding("risk", "Confirmed", evidence, AiFindingStatus.VERIFIED)
    unverified = AiFinding("risk", "Unconfirmed", None, AiFindingStatus.UNVERIFIED)
    return AiDocumentAnalysis(
        "procurement:test",
        "Safe",
        risks=(verified, unverified),
        status="partial",
        provenance=provenance,
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
    assert dialog.progress.value() == 22
    app.processEvents()


def test_dialog_has_dedicated_ai_summary_tab() -> None:
    dialog = TenderFullAnalysisDialog("procurement:test")

    assert dialog.tabs.count() == 4
    assert dialog.tabs.tabText(2) == "AI summary"
    assert dialog.tabs.tabText(3) == "AI-анализ"


def test_dialog_shows_dedicated_ai_progress_stage() -> None:
    dialog = TenderFullAnalysisDialog("procurement:test")

    row = dialog._stage_rows[FullAnalysisStage.RUNNING_AI]
    assert dialog.stages.item(row, 0).text() == "AI-анализ документации"


def test_dialog_renders_technical_specification_status_groups_and_evidence() -> None:
    analysis = _current_analysis()
    verified = analysis.risks[0]
    unverified = analysis.risks[1]
    analysis = replace(
        analysis,
        technical_specification=AiTechnicalSpecificationAnalysis(
            status=AiTechnicalSpecificationStatus.PARTIAL,
            document_ids=("doc",),
            scope=(verified,),
            ambiguities=(unverified,),
            warnings=("Контекст технического задания неполон.",),
        ),
    )

    html = _render_ai_document_analysis(_result(analysis))

    assert "Техническое задание" in html
    assert "Частичный результат" in html
    assert "Confirmed" in html
    assert "Неподтверждённый вывод" in html
    assert "Контекст технического задания неполон" in html


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
    html = _render_ai_document_analysis(_result(_current_analysis()))

    assert "exact quote" in html
    assert "Неподтверждённый вывод" in html


def test_ai_tab_renders_safe_current_citation_details() -> None:
    analysis = _current_analysis()
    evidence = analysis.risks[0].evidence
    assert evidence is not None

    html = _render_ai_document_analysis(_result(analysis))

    assert "tender.pdf" in html
    assert "страница 2" in html
    assert "раздел Раздел 1" in html
    assert "Цитата: exact quote" in html
    assert "уверенность AI 80%" in html
    assert f"{evidence.citation_id[:12]}…" in html
    assert "контекст источника сокращён" in html
    assert f"corteris-citation://open/{evidence.citation_id}" in html


def test_dialog_emits_only_known_strict_citation_links() -> None:
    dialog = TenderFullAnalysisDialog("procurement:test")
    analysis = _current_analysis()
    evidence = analysis.risks[0].evidence
    assert evidence is not None
    requests: list[tuple[str, str]] = []
    dialog.citation_requested.connect(
        lambda registry, document: requests.append((registry, document))
    )
    dialog.set_result(_result(analysis))

    invalid_urls = (
        "file:///C:/secret.pdf",
        "http://open/cit_" + "a" * 32,
        "https://open/cit_" + "a" * 32,
        "data:text/plain,secret",
        "javascript:alert(1)",
        r"\\server\share\secret.pdf",
        "corteris-citation://open/cit_" + "0" * 32,
        f"corteris-citation://open/{evidence.citation_id}?document=secret",
        f"corteris-citation://open/{evidence.citation_id}#secret",
        f"corteris-citation://user@open/{evidence.citation_id}",
    )
    for value in invalid_urls:
        dialog.ai_analysis.anchorClicked.emit(QUrl(value))

    assert requests == []

    dialog.ai_analysis.anchorClicked.emit(QUrl(f"corteris-citation://open/{evidence.citation_id}"))
    assert requests == [("procurement:test", "doc")]


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
