import json
from dataclasses import replace
import re

import pytest

from app.core.ai.citations import resolve_citation
from app.core.ai.schemas import (
    AI_ANALYSIS_SCHEMA_VERSION,
    AiApplicationRequirementsStatus,
    AiAnalysisProvenance,
    AiDocument,
    AiDocumentAnalysis,
    AiDraftContractAnalysis,
    AiDraftContractStatus,
    AiFinding,
    AiFindingStatus,
    AiFinancialReviewPriority,
    AiFinancialRiskAssessment,
    AiFinancialRiskCategory,
    AiFinancialRiskItem,
    AiFinancialRiskSourceRef,
    AiFinancialRiskStatus,
    AiLegalReviewPriority,
    AiLegalRiskAssessment,
    AiLegalRiskCategory,
    AiLegalRiskItem,
    AiLegalRiskSourceRef,
    AiLegalRiskStatus,
    AiSourceSnapshot,
    AiTechnicalSpecificationAnalysis,
    AiTechnicalSpecificationStatus,
    TenderRequirements,
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


def test_export_round_trips_and_escapes_technical_specification(tmp_path) -> None:
    unverified = AiFinding(
        "scope",
        "<script>unsafe technical statement</script>",
        None,
        AiFindingStatus.UNVERIFIED,
    )
    analysis = AiDocumentAnalysis(
        "procurement:test",
        "Summary",
        status="partial",
        technical_specification=AiTechnicalSpecificationAnalysis(
            status=AiTechnicalSpecificationStatus.PARTIAL,
            document_ids=("ts-1",),
            scope=(unverified,),
            warnings=("ТЗ сокращено",),
        ),
    )

    json_path = TenderAiAnalysisExporter().export(analysis, tmp_path / "ts.json")
    html_path = TenderAiAnalysisExporter().export(analysis, tmp_path / "ts.html")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    html = html_path.read_text(encoding="utf-8")

    assert AiDocumentAnalysis.from_payload(payload).technical_specification.scope[0].statement == (
        "<script>unsafe technical statement</script>"
    )
    assert payload["technical_specification"]["status"] == "partial"
    assert "<script>" not in html
    assert "&lt;script&gt;unsafe technical statement&lt;/script&gt;" in html
    assert "ТЗ сокращено" in html


def test_export_round_trips_and_escapes_draft_contract(tmp_path) -> None:
    unverified = AiFinding(
        "draft_contract.subject_and_scope",
        "<script>unsafe contract statement</script>",
        None,
        AiFindingStatus.UNVERIFIED,
    )
    analysis = AiDocumentAnalysis(
        "procurement:test",
        "Summary",
        status="partial",
        draft_contract=AiDraftContractAnalysis(
            status=AiDraftContractStatus.PARTIAL,
            document_ids=("contract-1",),
            included_document_ids=("contract-1",),
            subject_and_scope=(unverified,),
            warnings=("Договор сокращён",),
        ),
    )

    json_path = TenderAiAnalysisExporter().export(analysis, tmp_path / "contract.json")
    html_path = TenderAiAnalysisExporter().export(analysis, tmp_path / "contract.html")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    html = html_path.read_text(encoding="utf-8")

    restored = AiDocumentAnalysis.from_payload(payload)
    assert restored.draft_contract.subject_and_scope[0].statement == (
        "<script>unsafe contract statement</script>"
    )
    assert payload["draft_contract"]["status"] == "partial"
    assert "Проект договора/контракта" in html
    assert "subject_and_scope" in html
    assert "<script>" not in html
    assert "&lt;script&gt;unsafe contract statement&lt;/script&gt;" in html
    assert "Договор сокращён" in html


def test_export_round_trips_scoped_application_requirements_and_escapes_xss(tmp_path) -> None:
    unverified = AiFinding(
        "requirements.documents",
        "<script>unsafe requirement</script>",
        None,
        AiFindingStatus.UNVERIFIED,
    )
    analysis = AiDocumentAnalysis(
        "procurement:test",
        "Summary",
        status="partial",
        requirements=TenderRequirements(
            status=AiApplicationRequirementsStatus.PARTIAL,
            document_ids=("requirements-1", "missing"),
            included_document_ids=("requirements-1",),
            documents=(unverified,),
            warnings=("Контекст требований к заявке неполон.",),
        ),
    )

    json_path = TenderAiAnalysisExporter().export(analysis, tmp_path / "requirements.json")
    html_path = TenderAiAnalysisExporter().export(analysis, tmp_path / "requirements.html")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    html = html_path.read_text(encoding="utf-8")

    restored = AiDocumentAnalysis.from_payload(payload)
    assert restored.requirements.status is AiApplicationRequirementsStatus.PARTIAL
    assert restored.requirements.documents[0].statement == "<script>unsafe requirement</script>"
    assert payload["requirements"]["document_ids"] == ["requirements-1", "missing"]
    assert "Требования к заявке" in html
    assert "найдено документов: 2; включено: 1" in html
    assert "Контекст требований к заявке неполон." in html
    assert "<script>" not in html
    assert "&lt;script&gt;unsafe requirement&lt;/script&gt;" in html


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


def test_export_adds_escaped_legal_registry_to_existing_json_and_html(tmp_path) -> None:
    citation_id = "cit_" + "a" * 32
    analysis = AiDocumentAnalysis(
        "procurement:test",
        "Safe",
        status="partial",
        requirements=TenderRequirements(
            status=AiApplicationRequirementsStatus.PARTIAL,
            licenses=(
                AiFinding(
                    "requirements.licenses",
                    "<script>provider statement</script>",
                    None,
                    AiFindingStatus.UNVERIFIED,
                ),
            ),
        ),
        legal_risk_assessment=AiLegalRiskAssessment(
            status=AiLegalRiskStatus.PARTIAL,
            policy_version="1",
            items=(
                AiLegalRiskItem(
                    risk_id="legal_" + "b" * 32,
                    category=AiLegalRiskCategory.ELIGIBILITY_AND_AUTHORIZATIONS,
                    review_priority=AiLegalReviewPriority.ELEVATED,
                    title="<b>Проверка разрешений</b>",
                    source_refs=(AiLegalRiskSourceRef("requirements", "licenses", citation_id),),
                    recommended_action="Проверить <img src=x onerror=alert(1)>",
                ),
            ),
            warnings=("Контекст неполон",),
        ),
    )

    json_path = TenderAiAnalysisExporter().export(analysis, tmp_path / "legal.json")
    html_path = TenderAiAnalysisExporter().export(analysis, tmp_path / "legal.html")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    html = html_path.read_text(encoding="utf-8")

    assert payload == analysis.to_payload()
    assert set(payload["legal_risk_assessment"]) == {
        "status",
        "policy_version",
        "items",
        "warnings",
    }
    assert "Юридические риски" in html
    assert "Информационная оценка; не является юридическим заключением" in html
    assert "<script>" not in html
    assert "<img" not in html
    assert "&lt;b&gt;Проверка разрешений&lt;/b&gt;" in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html
    assert "file://" not in html


def test_export_adds_escaped_financial_registry_to_existing_json_and_html(tmp_path) -> None:
    citation_id = "cit_" + "a" * 32
    analysis = AiDocumentAnalysis(
        "procurement:test",
        "Safe",
        status="partial",
        requirements=TenderRequirements(
            status=AiApplicationRequirementsStatus.PARTIAL,
            bid_security=(
                AiFinding(
                    "requirements.bid_security",
                    "<script>provider statement</script>",
                    None,
                    AiFindingStatus.UNVERIFIED,
                ),
            ),
        ),
        financial_risk_assessment=AiFinancialRiskAssessment(
            status=AiFinancialRiskStatus.PARTIAL,
            policy_version="1",
            items=(
                AiFinancialRiskItem(
                    risk_id="financial_" + "b" * 32,
                    category=AiFinancialRiskCategory.SECURITY_AND_GUARANTEE_COSTS,
                    review_priority=AiFinancialReviewPriority.ELEVATED,
                    title="<b>Обеспечение и гарантии</b>",
                    source_refs=(
                        AiFinancialRiskSourceRef("requirements", "bid_security", citation_id),
                    ),
                    recommended_action="Проверить <img src=x onerror=alert(1)>",
                ),
            ),
            warnings=("Контекст неполон",),
        ),
    )

    json_path = TenderAiAnalysisExporter().export(analysis, tmp_path / "financial.json")
    html_path = TenderAiAnalysisExporter().export(analysis, tmp_path / "financial.html")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    html = html_path.read_text(encoding="utf-8")

    assert payload == analysis.to_payload()
    assert set(payload["financial_risk_assessment"]) == {
        "status",
        "policy_version",
        "items",
        "warnings",
    }
    assert "Финансовые условия" in html
    assert (
        "Информационная оценка условий документации; не является финансовым прогнозом, "
        "расчётом убытка или рекомендацией об участии."
    ) in html
    assert "<script>" not in html
    assert "<img" not in html
    assert "&lt;b&gt;Обеспечение и гарантии&lt;/b&gt;" in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html
    assert "file://" not in html


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
        prompt_version="6",
        output_schema_version="4",
        persisted_schema_version=AI_ANALYSIS_SCHEMA_VERSION,
        analyzer_version="9",
        context_version="5",
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
