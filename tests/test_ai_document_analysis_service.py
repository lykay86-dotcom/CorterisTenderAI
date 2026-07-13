from app.core.ai.analyzer import TenderDocumentAiAnalysisService
from app.core.ai.repository import AiDocumentAnalysisRepository
from app.core.ai.schemas import AiDocument, AiDocumentAnalysis


class Builder:
    def build(self, _key):
        return (AiDocument("doc", "spec.pdf", "eis", "pdf", "now", "verified", "text", "abc"),)


class Analyzer:
    def __init__(self):
        self.calls = 0

    def analyze(self, key, _documents):
        self.calls += 1
        return AiDocumentAnalysis(key, "Summary", status="complete")


def test_service_reuses_analysis_for_unchanged_documents(tmp_path) -> None:
    analyzer = Analyzer()
    service = TenderDocumentAiAnalysisService(
        Builder(), analyzer, AiDocumentAnalysisRepository(tmp_path / "ai.sqlite3")
    )

    first = service.analyze("procurement:test")
    second = service.analyze("procurement:test")

    assert first.to_payload() == second.to_payload()
    assert analyzer.calls == 1
