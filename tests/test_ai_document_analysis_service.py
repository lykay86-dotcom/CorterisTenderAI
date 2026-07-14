from app.core.ai.analyzer import TenderDocumentAiAnalysisService
from app.core.ai.document_context import AiContextStatistics, AiDocumentContext
from app.core.ai.repository import AiDocumentAnalysisRepository
from app.core.ai.schemas import (
    AI_ANALYSIS_SCHEMA_VERSION,
    AiAnalysisProvenance,
    AiDocument,
    AiDocumentAnalysis,
)


def _provenance(fingerprint: str) -> AiAnalysisProvenance:
    return AiAnalysisProvenance(
        analysis_id="analysis_123",
        context_fingerprint=fingerprint,
        created_at="2026-07-14T10:00:00+00:00",
        prompt_version="4",
        output_schema_version="2",
        persisted_schema_version=AI_ANALYSIS_SCHEMA_VERSION,
        analyzer_version="5",
        context_version="3",
        citation_resolver_version="1",
        provider_id="openai",
        provider_model="gpt-5",
        provider_response_id="resp_" + "a" * 64,
        sources=(),
    )


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
        return AiDocumentAnalysis(
            key,
            "Summary",
            status="complete",
            provenance=_provenance(context_fingerprint),
        )


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


def test_ts_omission_metadata_changes_cache_fingerprint() -> None:
    class ContextBuilder:
        omitted = 0
        fingerprint_parameters = {"context_version": "3"}

        def build_context(self, _key):
            document = AiDocument(
                "ts",
                "Техническое задание.pdf",
                "local_document_store",
                "pdf",
                "2026-07-15T00:00:00+00:00",
                "verified",
                "text",
                "a" * 64,
                document_kind="technical_specification",
            )
            return AiDocumentContext(
                (document,),
                AiContextStatistics(
                    source_document_count=1 + self.omitted,
                    included_document_count=1,
                    character_count=4,
                    omitted_document_count=self.omitted,
                    technical_specification_document_count=1 + self.omitted,
                    included_technical_specification_document_count=1,
                    technical_specification_truncated=bool(self.omitted),
                    technical_specification_document_ids=("ts",),
                    included_technical_specification_document_ids=("ts",),
                ),
            )

    builder = ContextBuilder()
    analyzer = Analyzer()
    repository = WriteFailureRepository()
    service = TenderDocumentAiAnalysisService(builder, analyzer, repository)

    service.analyze("procurement:test", force=True)
    builder.omitted = 1
    service.analyze("procurement:test", force=True)

    assert analyzer.fingerprints[0] != analyzer.fingerprints[1]


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


def test_service_current_provider_failure_is_not_replaced_by_stale_success(tmp_path) -> None:
    class MutableBuilder:
        checksum = "a" * 64

        def build(self, _key):
            return (
                AiDocument(
                    "doc",
                    "spec.pdf",
                    "eis",
                    "pdf",
                    "now",
                    "verified",
                    "text",
                    self.checksum,
                ),
            )

    builder = MutableBuilder()
    repository = AiDocumentAnalysisRepository(tmp_path / "ai.sqlite3")
    successful = TenderDocumentAiAnalysisService(builder, Analyzer(), repository).analyze(
        "procurement:test"
    )
    builder.checksum = "b" * 64

    current = TenderDocumentAiAnalysisService(
        builder,
        ProviderFailureAnalyzer(),
        repository,
    ).analyze("procurement:test")

    assert successful.status == "complete"
    assert current.status == "provider_error"
    assert current.summary == "Unavailable"


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
