from app.core.ai.analyzer import TenderDocumentAiAnalysisService
from app.core.ai.repository import AiDocumentAnalysisRepository
from app.core.ai.schemas import AiDocument, AiDocumentAnalysis


class Builder:
    def build(self, _key):
        return (AiDocument("doc", "spec.pdf", "eis", "pdf", "now", "verified", "text", "abc"),)


class Analyzer:
    def __init__(self):
        self.calls = 0
        self.fingerprints = []

    def analyze(self, key, _documents, *, context_fingerprint):
        self.calls += 1
        self.fingerprints.append(context_fingerprint)
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
    assert analyzer.fingerprints and len(analyzer.fingerprints[0]) == 64


def test_service_passes_cache_lookup_fingerprint_to_analyzer() -> None:
    class RecordingRepository:
        last_warning = ""

        def __init__(self):
            self.lookup_fingerprints = []

        def reusable(self, _key, fingerprint):
            self.lookup_fingerprints.append(fingerprint)
            return None

        def save(self, _analysis, _fingerprint):
            return None

    analyzer = Analyzer()
    repository = RecordingRepository()
    TenderDocumentAiAnalysisService(Builder(), analyzer, repository).analyze("procurement:test")

    assert repository.lookup_fingerprints == analyzer.fingerprints


def test_service_force_always_runs_new_analysis(tmp_path) -> None:
    analyzer = Analyzer()
    service = TenderDocumentAiAnalysisService(
        Builder(), analyzer, AiDocumentAnalysisRepository(tmp_path / "ai.sqlite3")
    )

    service.analyze("procurement:test")
    service.analyze("procurement:test", force=True)

    assert analyzer.calls == 2


class WriteFailureRepository:
    last_warning = ""

    def reusable(self, _key, _fingerprint):
        return None

    def save(self, _analysis, _fingerprint):
        raise OSError("database contains SECRET")


def test_service_contains_repository_write_error() -> None:
    service = TenderDocumentAiAnalysisService(Builder(), Analyzer(), WriteFailureRepository())

    result = service.analyze("procurement:test")

    assert result.status == "partial"
    assert "сохранить" in result.warnings[0]
    assert "SECRET" not in " ".join(result.warnings)


class ProviderFailureAnalyzer(Analyzer):
    def analyze(self, key, _documents, *, context_fingerprint):
        self.calls += 1
        self.fingerprints.append(context_fingerprint)
        return AiDocumentAnalysis(key, "Unavailable", status="provider_error")


def test_service_does_not_cache_provider_error(tmp_path) -> None:
    analyzer = ProviderFailureAnalyzer()
    service = TenderDocumentAiAnalysisService(
        Builder(), analyzer, AiDocumentAnalysisRepository(tmp_path / "ai.sqlite3")
    )

    service.analyze("procurement:test")
    service.analyze("procurement:test")

    assert analyzer.calls == 2


class BrokenBuilder:
    def build(self, _key):
        raise OSError("C:/secret/path")


def test_service_contains_context_build_error(tmp_path) -> None:
    result = TenderDocumentAiAnalysisService(
        BrokenBuilder(),
        Analyzer(),
        AiDocumentAnalysisRepository(tmp_path / "ai.sqlite3"),
    ).analyze("procurement:test")

    assert result.status == "invalid_response"
    assert "secret" not in " ".join(result.warnings).casefold()
