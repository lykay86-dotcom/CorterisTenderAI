from datetime import datetime
import sqlite3

from app.core.ai.repository import AiDocumentAnalysisRepository, context_fingerprint
from app.core.ai.schemas import (
    AI_ANALYSIS_SCHEMA_VERSION,
    AiDocument,
    AiDocumentAnalysis,
)


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


def test_context_fingerprint_is_order_independent() -> None:
    first = AiDocument("a", "a.pdf", "eis", "pdf", "now", "verified", "A", "a")
    second = AiDocument("b", "b.pdf", "eis", "pdf", "now", "verified", "B", "b")

    assert context_fingerprint((first, second)) == context_fingerprint((second, first))


def test_context_fingerprint_changes_with_all_contract_versions_and_limits() -> None:
    documents = (AiDocument("doc", "spec.pdf", "eis", "pdf", "now", "verified", "text", "abc"),)
    baseline = context_fingerprint(documents)

    assert baseline != context_fingerprint(documents, prompt_version="next")
    assert baseline != context_fingerprint(documents, schema_version=999)
    assert baseline != context_fingerprint(documents, analyzer_version="next")
    assert baseline != context_fingerprint(documents, context_version="next")
    assert baseline != context_fingerprint(
        documents,
        context_parameters={"max_total_characters": 1},
    )


def test_repository_skips_corrupt_latest_row_and_uses_previous_valid(tmp_path) -> None:
    repository = AiDocumentAnalysisRepository(tmp_path / "registry.sqlite3")
    fingerprint = "fingerprint"
    expected = AiDocumentAnalysis("procurement:test", "Previous", status="complete")
    repository.save(expected, fingerprint)
    with sqlite3.connect(repository.path) as connection:
        connection.execute(
            """
            INSERT INTO tender_ai_document_analyses (
                analysis_id, registry_key, context_fingerprint, status,
                payload_json, created_at, payload_version
            ) VALUES ('corrupt', ?, ?, 'complete', '{bad json', ?, ?)
            """,
            (
                "procurement:test",
                fingerprint,
                "9999-01-01T00:00:00+00:00",
                AI_ANALYSIS_SCHEMA_VERSION,
            ),
        )

    reused = repository.reusable("procurement:test", fingerprint)

    assert reused is not None
    assert reused.summary == "Previous"
    assert "пропущена" in repository.last_warning


def test_repository_reports_incompatible_cache_without_success(tmp_path) -> None:
    repository = AiDocumentAnalysisRepository(tmp_path / "registry.sqlite3")
    repository.initialize()
    with sqlite3.connect(repository.path) as connection:
        connection.execute(
            """
            INSERT INTO tender_ai_document_analyses (
                analysis_id, registry_key, context_fingerprint, status,
                payload_json, created_at, payload_version
            ) VALUES ('future', ?, 'fp', 'complete', '{}', ?, ?)
            """,
            (
                "procurement:test",
                "2026-07-13T00:00:00+00:00",
                AI_ANALYSIS_SCHEMA_VERSION + 1,
            ),
        )

    assert repository.reusable("procurement:test", "fp") is None
    latest = repository.latest("procurement:test")
    assert latest is not None
    assert latest.registry_key == "procurement:test"
    assert latest.status == "cache_incompatible"


def test_repository_migrates_rm109_table_without_deleting_history(tmp_path) -> None:
    path = tmp_path / "registry.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE tender_ai_document_analyses (
                analysis_id TEXT PRIMARY KEY,
                registry_key TEXT NOT NULL,
                context_fingerprint TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    repository = AiDocumentAnalysisRepository(path)

    repository.initialize()

    with sqlite3.connect(path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(tender_ai_document_analyses)")
        }
    assert "payload_version" in columns


def test_repository_persists_timezone_aware_dates_and_stable_latest(tmp_path) -> None:
    repository = AiDocumentAnalysisRepository(tmp_path / "registry.sqlite3")
    first = AiDocumentAnalysis(
        "procurement:test",
        "First",
        status="complete",
        created_at="2026-07-13T10:00:00+03:00",
    )
    second = AiDocumentAnalysis(
        "procurement:test",
        "Second",
        status="complete",
        created_at="2026-07-13T11:00:00+03:00",
    )
    repository.save(first, "one")
    repository.save(second, "two")

    latest = repository.latest("procurement:test")
    with sqlite3.connect(repository.path) as connection:
        dates = [
            row[0]
            for row in connection.execute("SELECT created_at FROM tender_ai_document_analyses")
        ]

    assert latest is not None and latest.summary == "Second"
    assert all(datetime.fromisoformat(value).utcoffset() is not None for value in dates)
