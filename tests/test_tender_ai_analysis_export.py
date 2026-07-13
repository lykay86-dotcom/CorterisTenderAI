import json

from app.core.ai.schemas import AiDocumentAnalysis
from app.reporting.tender_ai_analysis import TenderAiAnalysisExporter


def test_export_creates_json_and_html_sections(tmp_path) -> None:
    analysis = AiDocumentAnalysis("procurement:test", "Summary", final_ai_conclusion="Review", status="complete")
    exporter = TenderAiAnalysisExporter()

    json_path = exporter.export(analysis, tmp_path / "analysis.json")
    html_path = exporter.export(analysis, tmp_path / "analysis.html")

    assert json.loads(json_path.read_text(encoding="utf-8"))["summary"] == "Summary"
    assert "AI-анализ документации" in html_path.read_text(encoding="utf-8")
