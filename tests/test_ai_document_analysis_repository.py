from app.core.ai.repository import AiDocumentAnalysisRepository, context_fingerprint
from app.core.ai.schemas import AiDocument, AiDocumentAnalysis


def test_repository_reuses_analysis_for_identical_document_context(tmp_path) -> None:
    repository = AiDocumentAnalysisRepository(tmp_path / "registry.sqlite3")
    documents = (AiDocument("doc", "spec.pdf", "eis", "pdf", "now", "verified", "text", "abc"),)
    fingerprint = context_fingerprint(documents)
    analysis = AiDocumentAnalysis("procurement:test", "Summary", status="complete")

    repository.save(analysis, fingerprint)
    reused = repository.reusable("procurement:test", fingerprint)

    assert reused is not None
    assert reused.to_payload() == analysis.to_payload()


def test_context_fingerprint_changes_with_document_checksum() -> None:
    first = (AiDocument("doc", "spec.pdf", "eis", "pdf", "now", "verified", "text", "abc"),)
    second = (AiDocument("doc", "spec.pdf", "eis", "pdf", "now", "verified", "text", "def"),)

    assert context_fingerprint(first) != context_fingerprint(second)
