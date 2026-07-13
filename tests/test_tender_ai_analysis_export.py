import json

import pytest

from app.core.ai.schemas import AiDocumentAnalysis
from app.reporting.tender_ai_analysis import TenderAiAnalysisExporter


def test_export_creates_json_and_html_sections(tmp_path) -> None:
    analysis = AiDocumentAnalysis(
        "procurement:test", "Summary", final_ai_conclusion="Review", status="complete"
    )
    exporter = TenderAiAnalysisExporter()

    json_path = exporter.export(analysis, tmp_path / "analysis.json")
    html_path = exporter.export(analysis, tmp_path / "analysis.html")

    assert json.loads(json_path.read_text(encoding="utf-8"))["summary"] == "Summary"
    assert "AI-анализ документации" in html_path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "status",
    [
        "partial",
        "no_documents",
        "provider_disabled",
        "provider_error",
        "invalid_response",
        "cache_incompatible",
    ],
)
def test_export_supports_all_error_safe_statuses(tmp_path, status: str) -> None:
    analysis = AiDocumentAnalysis(
        "procurement:test",
        "Safe result",
        status=status,
        warnings=("Безопасное предупреждение.",),
    )

    json_path = TenderAiAnalysisExporter().export(analysis, tmp_path / f"{status}.json")
    html_path = TenderAiAnalysisExporter().export(analysis, tmp_path / f"{status}.html")

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    html = html_path.read_text(encoding="utf-8")
    assert payload["status"] == status
    assert payload["payload_version"] >= 1
    assert status in html
    assert "Traceback" not in html


def test_export_marks_truncated_context(tmp_path) -> None:
    analysis = AiDocumentAnalysis(
        "procurement:test",
        "Partial",
        status="partial",
        context_document_count=3,
        context_character_count=400_000,
        context_truncated=True,
    )

    path = TenderAiAnalysisExporter().export(analysis, tmp_path / "partial.html")

    html = path.read_text(encoding="utf-8")
    assert "Контекст сокращён" in html
    assert "400000" in html
