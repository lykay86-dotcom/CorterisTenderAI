import json
from dataclasses import replace
import re

import pytest

from app.core.ai.citations import resolve_citation
from app.core.ai.schemas import (
    AI_ANALYSIS_SCHEMA_VERSION,
    AiAnalysisProvenance,
    AiDocument,
    AiDocumentAnalysis,
    AiFinding,
    AiFindingStatus,
    AiSourceSnapshot,
)
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


def test_export_contains_only_escaped_internal_current_citation_sources(tmp_path) -> None:
    fingerprint = "d" * 64
    checksum = "b" * 64
    quote = '<img src=x onerror="SECRET"> https://provider.example/model'
    document = AiDocument(
        "doc",
        "tender.pdf",
        "local_document_store",
        "pdf",
        "2026-07-14T10:00:00+00:00",
        "verified",
        quote,
        checksum,
        original_character_count=len(quote),
    )
    evidence = resolve_citation(
        document_id="doc",
        quote=quote,
        section="<b>unsafe section</b>",
        page=3,
        confidence=0.8,
        documents=(document,),
        context_fingerprint=fingerprint,
    ).evidence
    assert evidence is not None
    evidence = replace(evidence, section="<b>unsafe section</b>", page=3)
    source = AiSourceSnapshot(
        document_id="doc",
        display_name=r"C:\Users\SecretUser\Documents\tender<script>.pdf",
        document_type="pdf",
        checksum_sha256=checksum,
        verification_status="verified",
        received_at="2026-07-14T10:00:00+00:00",
        truncated=True,
        included_character_count=len(quote),
        original_character_count=len(quote) + 100,
    )
    provenance = AiAnalysisProvenance(
        analysis_id="analysis_123",
        context_fingerprint=fingerprint,
        created_at="2026-07-14T10:01:00+00:00",
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
    verified = AiFinding(
        "risk",
        "<script>SECRET statement</script>",
        evidence,
        AiFindingStatus.VERIFIED,
    )
    unverified = AiFinding(
        "risk",
        "Unverified",
        evidence,
        AiFindingStatus.UNVERIFIED,
    )
    analysis = AiDocumentAnalysis(
        "procurement:test",
        "Safe",
        risks=(verified, unverified),
        status="complete",
        provenance=provenance,
    )

    json_path = TenderAiAnalysisExporter().export(analysis, tmp_path / "analysis.json")
    html_path = TenderAiAnalysisExporter().export(analysis, tmp_path / "analysis.html")
    json_text = json_path.read_text(encoding="utf-8")
    payload = json.loads(json_text)
    html = html_path.read_text(encoding="utf-8")

    assert payload == analysis.to_payload()
    assert payload["provenance"]["sources"] == payload["source_registry"]
    assert "<script>" not in json_text
    assert "<img" not in json_text
    assert r"C:\Users\SecretUser" not in json_text
    assert "<script>" not in html
    assert "<img" not in html
    assert "&lt;script&gt;SECRET statement&lt;/script&gt;" in html
    assert "&lt;img src=x onerror=&quot;SECRET&quot;&gt;" in html
    assert "&lt;b&gt;unsafe section&lt;/b&gt;" in html
    assert r"C:\Users\SecretUser" not in html
    assert "file://" not in html
    hrefs = re.findall(r'href="([^"]+)"', html)
    assert hrefs == [f"#source-{evidence.citation_id}"]
    assert f'id="source-{evidence.citation_id}"' in html
    assert checksum[:12] in html
    assert evidence.citation_id in html
    assert "страница 3" in html
    assert html.count(f'href="#source-{evidence.citation_id}"') == 1
