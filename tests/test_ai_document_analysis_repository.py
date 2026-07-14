from dataclasses import replace
from datetime import datetime
import json
import sqlite3

import pytest

from app.core.ai.output_schema import AI_PROVIDER_OUTPUT_SCHEMA_VERSION
from app.core.ai.prompts import AI_PROMPT_VERSION
from app.core.ai.citations import CITATION_RESOLVER_VERSION
from app.core.ai.repository import (
    AI_ANALYZER_VERSION,
    AiDocumentAnalysisRepository,
    context_fingerprint,
)
from app.core.ai.schemas import (
    AI_ANALYSIS_SCHEMA_VERSION,
    AiAnalysisProvenance,
    AiDocument,
    AiDocumentAnalysis,
    AiSourceSnapshot,
)


def _current_analysis(
    fingerprint: str,
    *,
    summary: str = "Summary",
    checksum: str = "a" * 64,
) -> AiDocumentAnalysis:
    source = AiSourceSnapshot(
        document_id="doc",
        display_name="spec.pdf",
        document_type="pdf",
        checksum_sha256=checksum,
        verification_status="verified",
        received_at="unknown",
        truncated=False,
        included_character_count=4,
        original_character_count=4,
    )
    provenance = AiAnalysisProvenance(
        analysis_id="analysis_123",
        context_fingerprint=fingerprint,
        created_at="2026-07-14T10:00:00+00:00",
        prompt_version="3",
        output_schema_version="1",
        persisted_schema_version=AI_ANALYSIS_SCHEMA_VERSION,
        analyzer_version="4",
        context_version="2",
        citation_resolver_version="1",
        provider_id="openai",
        provider_model="gpt-5",
        provider_response_id="resp_" + "a" * 64,
        sources=(source,),
    )
    return AiDocumentAnalysis(
        "procurement:test",
        summary,
        status="complete",
        provenance=provenance,
    )


def _insert_newest_raw_row(
    repository: AiDocumentAnalysisRepository,
    fingerprint: str,
    *,
    payload_json: object,
    stored_version: object,
) -> None:
    repository.initialize()
    with sqlite3.connect(repository.path) as connection:
        connection.execute(
            """
            INSERT INTO tender_ai_document_analyses (
                analysis_id, registry_key, context_fingerprint, status,
                payload_json, created_at, payload_version
            ) VALUES ('newest-raw', ?, ?, 'complete', ?, ?, ?)
            """,
            (
                "procurement:test",
                fingerprint,
                payload_json,
                "9999-01-01T00:00:00+00:00",
                stored_version,
            ),
        )


def _assert_previous_is_reused_without_secret_leak(
    repository: AiDocumentAnalysisRepository,
    fingerprint: str,
) -> None:
    reused = repository.reusable("procurement:test", fingerprint)

    assert reused is not None
    assert reused.summary == "Previous"
    assert repository.last_warning == "Повреждённая или несовместимая запись AI-анализа пропущена."
    assert "SECRET" not in repository.last_warning


def test_repository_reuses_analysis_for_identical_document_context(tmp_path) -> None:
    repository = AiDocumentAnalysisRepository(tmp_path / "registry.sqlite3")
    documents = (AiDocument("doc", "spec.pdf", "eis", "pdf", "now", "verified", "text", "abc"),)
    fingerprint = context_fingerprint(documents)
    analysis = _current_analysis(fingerprint)

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
    assert baseline != context_fingerprint(
        documents,
        provider_output_schema_version="next",
    )
    assert baseline != context_fingerprint(documents, context_version="next")
    assert baseline != context_fingerprint(documents, citation_resolver_version="next")
    assert baseline != context_fingerprint(
        documents,
        context_parameters={"max_total_characters": 1},
    )


def test_rm116_versions_are_current_without_changing_provider_output_schema() -> None:
    assert AI_PROMPT_VERSION == "3"
    assert AI_ANALYZER_VERSION == "4"
    assert CITATION_RESOLVER_VERSION == "1"
    assert AI_PROVIDER_OUTPUT_SCHEMA_VERSION == "1"
    assert AI_ANALYSIS_SCHEMA_VERSION == 3


def test_strict_fingerprint_does_not_reuse_old_lenient_result(tmp_path) -> None:
    repository = AiDocumentAnalysisRepository(tmp_path / "registry.sqlite3")
    documents = (AiDocument("doc", "spec.pdf", "eis", "pdf", "now", "verified", "text", "abc"),)
    old_fingerprint = context_fingerprint(
        documents,
        prompt_version="1",
        analyzer_version="2",
        provider_output_schema_version="0",
    )
    strict_fingerprint = context_fingerprint(documents)
    repository.save(
        AiDocumentAnalysis("procurement:test", "Old lenient", status="complete"),
        old_fingerprint,
    )

    assert old_fingerprint != strict_fingerprint
    assert repository.reusable("procurement:test", strict_fingerprint) is None
    assert repository.latest("procurement:test").summary == "Old lenient"  # type: ignore[union-attr]


def test_rm116_adds_no_table_or_column_migration(tmp_path) -> None:
    repository = AiDocumentAnalysisRepository(tmp_path / "registry.sqlite3")

    repository.initialize()

    with sqlite3.connect(repository.path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(tender_ai_document_analyses)")
        }
    assert tables == {"tender_ai_document_analyses"}
    assert columns == {
        "analysis_id",
        "registry_key",
        "context_fingerprint",
        "status",
        "payload_json",
        "created_at",
        "payload_version",
    }


def test_repository_skips_corrupt_latest_row_and_uses_previous_valid(tmp_path) -> None:
    repository = AiDocumentAnalysisRepository(tmp_path / "registry.sqlite3")
    fingerprint = "a" * 64
    expected = _current_analysis(fingerprint, summary="Previous")
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


def test_repository_reusable_rejects_v2_but_latest_returns_safe_display(tmp_path) -> None:
    repository = AiDocumentAnalysisRepository(tmp_path / "registry.sqlite3")
    fingerprint = "a" * 64
    legacy = replace(_current_analysis(fingerprint), payload_version=2, provenance=None)
    payload = legacy.to_payload()
    payload["risks"] = [
        {
            "category": "risk",
            "statement": "Legacy display statement",
            "status": "verified",
            "evidence": {"document_id": "doc", "quote": "legacy"},
        }
    ]
    repository.initialize()
    with sqlite3.connect(repository.path) as connection:
        connection.execute(
            """
            INSERT INTO tender_ai_document_analyses (
                analysis_id, registry_key, context_fingerprint, status,
                payload_json, created_at, payload_version
            ) VALUES ('legacy', ?, ?, 'complete', ?, ?, 2)
            """,
            (
                "procurement:test",
                fingerprint,
                json.dumps(payload),
                "2026-07-14T10:00:00+00:00",
            ),
        )

    assert repository.reusable("procurement:test", fingerprint) is None
    latest = repository.latest("procurement:test")
    assert latest is not None
    assert latest.summary == "Summary"
    assert latest.payload_version == 2
    assert latest.provenance is None
    assert latest.risks[0].statement == "Legacy display statement"
    assert latest.risks[0].status == "unverified"
    assert latest.risks[0].evidence is None


def test_repository_reusable_requires_payload_provenance_fingerprint_match(tmp_path) -> None:
    repository = AiDocumentAnalysisRepository(tmp_path / "registry.sqlite3")
    query_fingerprint = "a" * 64
    other_fingerprint = "b" * 64
    repository.save(_current_analysis(other_fingerprint), query_fingerprint)

    assert repository.reusable("procurement:test", query_fingerprint) is None
    assert repository.last_warning == "Повреждённая запись AI-анализа пропущена."


def test_repository_skips_damaged_current_provenance_and_reuses_previous_valid_v3(
    tmp_path,
) -> None:
    repository = AiDocumentAnalysisRepository(tmp_path / "registry.sqlite3")
    fingerprint = "a" * 64
    previous = _current_analysis(fingerprint, summary="Previous")
    repository.save(previous, fingerprint)
    damaged = _current_analysis(fingerprint, summary="SECRET newest payload").to_payload()
    damaged["provenance"]["context_fingerprint"] = "not-a-fingerprint"
    damaged["source_registry"] = damaged["provenance"]["sources"]
    with sqlite3.connect(repository.path) as connection:
        connection.execute(
            """
            INSERT INTO tender_ai_document_analyses (
                analysis_id, registry_key, context_fingerprint, status,
                payload_json, created_at, payload_version
            ) VALUES ('damaged', ?, ?, 'complete', ?, ?, ?)
            """,
            (
                "procurement:test",
                fingerprint,
                json.dumps(damaged),
                "9999-01-01T00:00:00+00:00",
                AI_ANALYSIS_SCHEMA_VERSION,
            ),
        )

    reused = repository.reusable("procurement:test", fingerprint)

    assert reused is not None
    assert reused.summary == "Previous"
    assert repository.last_warning == "Повреждённая или несовместимая запись AI-анализа пропущена."
    assert "SECRET" not in repository.last_warning


@pytest.mark.parametrize(
    "stored_version",
    ["SECRET-version", sqlite3.Binary(b"SECRET-version"), 3.5],
    ids=["text", "blob", "float"],
)
def test_repository_skips_sqlite_malformed_stored_version_and_reuses_previous_v3(
    tmp_path,
    stored_version,
) -> None:
    repository = AiDocumentAnalysisRepository(tmp_path / "registry.sqlite3")
    fingerprint = "a" * 64
    repository.save(_current_analysis(fingerprint, summary="Previous"), fingerprint)
    payload = _current_analysis(fingerprint, summary="SECRET newest payload").to_payload()
    _insert_newest_raw_row(
        repository,
        fingerprint,
        payload_json=json.dumps(payload),
        stored_version=stored_version,
    )

    _assert_previous_is_reused_without_secret_leak(repository, fingerprint)


@pytest.mark.parametrize("stored_version", [True, None], ids=["bool", "null-like"])
def test_repository_skips_injected_non_exact_integer_stored_version(
    tmp_path,
    stored_version,
) -> None:
    repository = AiDocumentAnalysisRepository(tmp_path / "registry.sqlite3")
    fingerprint = "a" * 64
    previous = _current_analysis(fingerprint, summary="Previous")
    newest = _current_analysis(fingerprint, summary="SECRET newest payload")

    result = repository._latest_valid(
        [
            (json.dumps(newest.to_payload()), stored_version),
            (json.dumps(previous.to_payload()), AI_ANALYSIS_SCHEMA_VERSION),
        ],
        expected_registry_key="procurement:test",
        return_incompatible=False,
        reusable_fingerprint=fingerprint,
    )

    assert result is not None
    assert result.summary == "Previous"
    assert repository.last_warning == "Повреждённая или несовместимая запись AI-анализа пропущена."
    assert "SECRET" not in repository.last_warning


@pytest.mark.parametrize(
    "payload_json",
    ['"SECRET scalar"', '["SECRET array"]', "{SECRET malformed"],
    ids=["scalar", "array", "malformed"],
)
def test_repository_skips_non_mapping_or_malformed_json_and_reuses_previous_v3(
    tmp_path,
    payload_json,
) -> None:
    repository = AiDocumentAnalysisRepository(tmp_path / "registry.sqlite3")
    fingerprint = "a" * 64
    repository.save(_current_analysis(fingerprint, summary="Previous"), fingerprint)
    _insert_newest_raw_row(
        repository,
        fingerprint,
        payload_json=payload_json,
        stored_version=AI_ANALYSIS_SCHEMA_VERSION,
    )

    _assert_previous_is_reused_without_secret_leak(repository, fingerprint)


def test_repository_skips_column_payload_version_mismatch_and_reuses_previous_v3(
    tmp_path,
) -> None:
    repository = AiDocumentAnalysisRepository(tmp_path / "registry.sqlite3")
    fingerprint = "a" * 64
    repository.save(_current_analysis(fingerprint, summary="Previous"), fingerprint)
    payload = _current_analysis(fingerprint, summary="SECRET newest payload").to_payload()
    payload["payload_version"] = 2
    _insert_newest_raw_row(
        repository,
        fingerprint,
        payload_json=json.dumps(payload),
        stored_version=AI_ANALYSIS_SCHEMA_VERSION,
    )

    _assert_previous_is_reused_without_secret_leak(repository, fingerprint)


def test_repository_skips_future_version_and_reuses_previous_v3(tmp_path) -> None:
    repository = AiDocumentAnalysisRepository(tmp_path / "registry.sqlite3")
    fingerprint = "a" * 64
    repository.save(_current_analysis(fingerprint, summary="Previous"), fingerprint)
    _insert_newest_raw_row(
        repository,
        fingerprint,
        payload_json=json.dumps({"summary": "SECRET future payload"}),
        stored_version=AI_ANALYSIS_SCHEMA_VERSION + 1,
    )

    _assert_previous_is_reused_without_secret_leak(repository, fingerprint)


@pytest.mark.parametrize(
    "status",
    ["invalid_response", "cache_incompatible"],
)
def test_repository_skips_decoded_non_reusable_status_and_reuses_previous_v3(
    tmp_path,
    status,
) -> None:
    repository = AiDocumentAnalysisRepository(tmp_path / "registry.sqlite3")
    fingerprint = "a" * 64
    repository.save(_current_analysis(fingerprint, summary="Previous"), fingerprint)
    payload = _current_analysis(fingerprint, summary="SECRET newest payload").to_payload()
    payload["status"] = status
    _insert_newest_raw_row(
        repository,
        fingerprint,
        payload_json=json.dumps(payload),
        stored_version=AI_ANALYSIS_SCHEMA_VERSION,
    )

    _assert_previous_is_reused_without_secret_leak(repository, fingerprint)


def test_repository_save_is_append_only_and_preserves_schema(tmp_path) -> None:
    repository = AiDocumentAnalysisRepository(tmp_path / "registry.sqlite3")
    fingerprint = "a" * 64
    repository.save(_current_analysis(fingerprint, summary="First"), fingerprint)
    repository.save(_current_analysis(fingerprint, summary="Second"), fingerprint)

    with sqlite3.connect(repository.path) as connection:
        rows = list(
            connection.execute(
                "SELECT payload_json FROM tender_ai_document_analyses ORDER BY rowid"
            )
        )
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(tender_ai_document_analyses)")
        }

    assert [json.loads(row[0])["summary"] for row in rows] == ["First", "Second"]
    assert columns == {
        "analysis_id",
        "registry_key",
        "context_fingerprint",
        "status",
        "payload_json",
        "created_at",
        "payload_version",
    }


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
