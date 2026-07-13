from __future__ import annotations

import json

from app.ai.provider import AIProvider
from app.core.ai.analyzer import TenderDocumentAiAnalyzer
from app.core.ai.schemas import AiDocument, AiFindingStatus


class Provider(AIProvider):
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def analyze(self, prompt: str, documents: list[str]) -> dict:
        return {"status": "ok", "text": json.dumps(self.payload)}


def _document() -> AiDocument:
    return AiDocument("doc-1", "TZ.pdf", "eis", "technical_specification", "2026-07-13T00:00:00+00:00", "verified", "The delivery period is 10 days.")


def test_analyzer_keeps_only_quote_backed_findings_verified() -> None:
    analyzer = TenderDocumentAiAnalyzer(Provider({"summary": "Summary", "requirements": {"deadlines": [{"statement": "Ten days", "document_id": "doc-1", "quote": "delivery period is 10 days", "confidence": 0.8}]}}))

    result = analyzer.analyze("procurement:test", (_document(),))

    finding = result.requirements.deadlines[0]
    assert finding.status == AiFindingStatus.VERIFIED
    assert finding.evidence is not None


def test_analyzer_marks_hallucinated_or_unknown_document_unverified() -> None:
    analyzer = TenderDocumentAiAnalyzer(Provider({"risks": [{"statement": "Invented", "document_id": "unknown", "quote": "not present", "confidence": 0.9}]}))

    result = analyzer.analyze("procurement:test", (_document(),))

    assert result.risks[0].status == AiFindingStatus.UNVERIFIED
    assert result.risks[0].evidence is None


def test_analyzer_handles_missing_documents_and_invalid_provider_response() -> None:
    analyzer = TenderDocumentAiAnalyzer(Provider({}))

    assert analyzer.analyze("procurement:test", ()).status == "no_documents"
