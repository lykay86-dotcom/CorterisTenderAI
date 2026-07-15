from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime
import hashlib
import json

import pytest

from app.ai.provider import AIProvider, AiProviderMetadata
from app.core.ai.analyzer import TenderDocumentAiAnalyzer
from app.core.ai.citations import CITATION_RESOLVER_VERSION
from app.core.ai.document_context import AI_CONTEXT_VERSION
from app.core.ai.output_schema import AI_PROVIDER_OUTPUT_SCHEMA_VERSION
from app.core.ai.output_schema import build_responses_text_format
from app.core.ai.prompts import AI_PROMPT_VERSION, SYSTEM_PROMPT
from app.core.ai.repository import AI_ANALYZER_VERSION
from app.core.ai.repository import context_fingerprint as build_context_fingerprint
from app.core.ai.schemas import (
    AI_ANALYSIS_SCHEMA_VERSION,
    AiCompetitionCategory,
    AiCompetitionReviewPriority,
    AiCompetitionStatus,
    AiDocument,
    AiDraftContractAnalysis,
    AiFinancialReviewPriority,
    AiFinancialRiskCategory,
    AiFinancialRiskStatus,
    AiFindingStatus,
    AiLegalReviewPriority,
    AiLegalRiskCategory,
    AiLegalRiskStatus,
    AiTechnicalSpecificationAnalysis,
    _APPLICATION_REQUIREMENTS_FINDING_FIELDS,
)


CONTEXT_FINGERPRINT = "f" * 64


class Provider(AIProvider):
    def __init__(
        self,
        payload: object,
        *,
        raw: bool = False,
        provider_status: str = "ok",
    ) -> None:
        self.payload = payload
        self.raw = raw
        self.provider_status = provider_status
        self.calls: list[tuple[str, list[str], Mapping[str, object] | None]] = []

    @property
    def metadata(self) -> AiProviderMetadata:
        return AiProviderMetadata("test-provider", "test-model")

    def analyze(
        self,
        prompt: str,
        documents: list[str],
        *,
        output_format: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        self.calls.append((prompt, documents, output_format))
        if self.provider_status != "ok":
            return {"status": self.provider_status, "message": "private provider response"}
        text = str(self.payload) if self.raw else json.dumps(self.payload, ensure_ascii=False)
        return {"status": "ok", "text": text, "raw_id": " response-123 "}


def _document() -> AiDocument:
    return AiDocument(
        "doc-1",
        "TZ.pdf",
        "eis",
        "technical_specification",
        "2026-07-13T00:00:00+00:00",
        "verified",
        "The delivery period is 10 days.",
        "a" * 64,
    )


def _finding(**overrides: object) -> dict[str, object]:
    return {
        "statement": "Ten days",
        "document_id": "doc-1",
        "quote": "delivery period is 10 days",
        "section": "",
        "page": None,
        "confidence": 0.8,
        **overrides,
    }


def _valid_payload(**overrides: object) -> dict[str, object]:
    return {
        "summary": "Summary",
        "requirements": {name: [] for name in _APPLICATION_REQUIREMENTS_FINDING_FIELDS},
        "technical_specification": {
            name: []
            for name in AiTechnicalSpecificationAnalysis.__dataclass_fields__
            if name not in {"status", "document_ids", "included_document_ids", "warnings"}
        },
        "draft_contract": {
            name: []
            for name in AiDraftContractAnalysis.__dataclass_fields__
            if name not in {"status", "document_ids", "included_document_ids", "warnings"}
        },
        "risks": [],
        "suspicious_conditions": [],
        "contradictions": [],
        "missing_documents": [],
        "final_ai_conclusion": "Conclusion",
        **overrides,
    }


def _assert_no_findings(result) -> None:
    assert not result.risks
    assert not result.suspicious_conditions
    assert not result.contradictions
    assert not result.missing_documents
    assert all(
        not getattr(result.requirements, name) for name in _APPLICATION_REQUIREMENTS_FINDING_FIELDS
    )


def test_valid_structure_and_exact_quote_becomes_verified() -> None:
    payload = _valid_payload()
    payload["requirements"]["deadlines"] = [_finding()]
    provider = Provider(payload)

    document = replace(
        _document(),
        name="Requirements.pdf",
        document_kind="application_requirements",
    )
    result = TenderDocumentAiAnalyzer(provider).analyze(
        "procurement:test", (document,), context_fingerprint=CONTEXT_FINGERPRINT
    )

    assert result.status == "complete"
    finding = result.requirements.deadlines[0]
    assert finding.status == AiFindingStatus.VERIFIED
    assert finding.evidence is not None
    assert finding.evidence.context_fingerprint == CONTEXT_FINGERPRINT
    assert finding.evidence.checksum_sha256 == "a" * 64
    assert finding.evidence.character_start == document.text.index(finding.evidence.quote)
    assert result.legal_risk_assessment.status is AiLegalRiskStatus.PARTIAL
    assert len(result.legal_risk_assessment.items) == 1
    assert result.legal_risk_assessment.items[0].category is (
        AiLegalRiskCategory.APPLICATION_COMPOSITION_AND_DECLARATIONS
    )
    assert result.legal_risk_assessment.items[0].review_priority is (AiLegalReviewPriority.ROUTINE)
    assert provider.calls == [
        (
            SYSTEM_PROMPT,
            [
                "DOCUMENT doc-1 | Requirements.pdf | KIND application_requirements\n"
                "The delivery period is 10 days."
            ],
            build_responses_text_format(),
        )
    ]


def test_verified_specialized_finding_builds_local_financial_assessment() -> None:
    payload = _valid_payload()
    payload["requirements"]["bid_security"] = [_finding(statement="Bid security")]
    provider = Provider(payload)
    document = replace(
        _document(),
        name="Requirements.pdf",
        document_kind="application_requirements",
    )

    result = TenderDocumentAiAnalyzer(provider).analyze(
        "procurement:test", (document,), context_fingerprint=CONTEXT_FINGERPRINT
    )

    financial = result.financial_risk_assessment
    assert financial.status is AiFinancialRiskStatus.PARTIAL
    assert len(financial.items) == 1
    assert financial.items[0].category is (AiFinancialRiskCategory.SECURITY_AND_GUARANTEE_COSTS)
    assert financial.items[0].review_priority is AiFinancialReviewPriority.ELEVATED
    assert provider.calls == [
        (
            SYSTEM_PROMPT,
            [
                "DOCUMENT doc-1 | Requirements.pdf | KIND application_requirements\n"
                "The delivery period is 10 days."
            ],
            build_responses_text_format(),
        )
    ]


def test_verified_specialized_finding_builds_local_competition_assessment() -> None:
    payload = _valid_payload()
    payload["requirements"]["bid_security"] = [_finding(statement="Bid security")]
    provider = Provider(payload)
    document = replace(
        _document(),
        name="Requirements.pdf",
        document_kind="application_requirements",
    )

    result = TenderDocumentAiAnalyzer(provider).analyze(
        "procurement:test", (document,), context_fingerprint=CONTEXT_FINGERPRINT
    )

    competition = result.competition_assessment
    assert competition.status is AiCompetitionStatus.PARTIAL
    assert len(competition.items) == 1
    assert competition.items[0].category is AiCompetitionCategory.SECURITY_AND_FINANCIAL_ACCESS
    assert competition.items[0].review_priority is AiCompetitionReviewPriority.ELEVATED
    assert result.legal_risk_assessment.items
    assert result.financial_risk_assessment.items
    assert len(provider.calls) == 1


def test_successful_response_builds_current_provenance_from_exact_documents() -> None:
    document = _document()
    payload = _valid_payload(risks=[_finding()])

    result = TenderDocumentAiAnalyzer(Provider(payload)).analyze(
        "procurement:test", (document,), context_fingerprint=CONTEXT_FINGERPRINT
    )

    provenance = result.provenance
    assert provenance is not None
    assert provenance.context_fingerprint == CONTEXT_FINGERPRINT
    assert datetime.fromisoformat(provenance.created_at).utcoffset() is not None
    assert provenance.prompt_version == AI_PROMPT_VERSION == "6"
    assert provenance.output_schema_version == AI_PROVIDER_OUTPUT_SCHEMA_VERSION == "4"
    assert provenance.persisted_schema_version == AI_ANALYSIS_SCHEMA_VERSION == 10
    assert provenance.analyzer_version == AI_ANALYZER_VERSION == "12"
    assert provenance.context_version == AI_CONTEXT_VERSION == "6"
    assert provenance.citation_resolver_version == CITATION_RESOLVER_VERSION == "1"
    assert provenance.provider_id == "test-provider"
    assert provenance.provider_model == "test-model"
    assert provenance.provider_response_id == (
        "resp_" + hashlib.sha256(b"response-123").hexdigest()
    )
    assert [source.to_payload() for source in provenance.sources] == [
        {
            "document_id": document.document_id,
            "display_name": document.name,
            "document_type": document.document_type,
            "checksum_sha256": document.checksum_sha256,
            "verification_status": document.verification_status,
            "received_at": document.received_at,
            "truncated": document.truncated,
            "included_character_count": len(document.text),
            "original_character_count": len(document.text),
            "document_kind": document.document_kind,
        }
    ]
    assert result.is_current_verified(result.risks[0])


def test_hostile_raw_id_mapping_degrades_inside_provenance_boundary() -> None:
    class HostileResponse(dict[str, object]):
        def get(self, key, default=None):
            if key == "raw_id":
                raise RuntimeError("Authorization: Bearer SECRET")
            return super().get(key, default)

    class HostileResponseProvider(Provider):
        def analyze(self, *args, **kwargs) -> dict[str, object]:
            return HostileResponse(super().analyze(*args, **kwargs))

    result = TenderDocumentAiAnalyzer(
        HostileResponseProvider(_valid_payload(risks=[_finding()]))
    ).analyze("procurement:test", (_document(),), context_fingerprint=CONTEXT_FINGERPRINT)

    assert result.status == "partial"
    assert result.provenance is None
    assert result.risks[0].status is AiFindingStatus.UNVERIFIED
    assert result.risks[0].evidence is None
    assert result.warnings == ("Provenance metadata could not be recorded safely.",)
    assert "SECRET" not in repr(result)


@pytest.mark.parametrize(
    ("failing_key", "expected_status"),
    [
        ("status", "provider_error"),
        ("text", "invalid_response"),
    ],
)
def test_hostile_provider_response_access_fails_closed_without_findings(
    failing_key: str,
    expected_status: str,
) -> None:
    class HostileResponse(dict[str, object]):
        def get(self, key, default=None):
            if key == failing_key:
                raise RuntimeError("Authorization: Bearer RESPONSE-SECRET")
            return super().get(key, default)

    class HostileResponseProvider(Provider):
        def analyze(self, *args, **kwargs) -> dict[str, object]:
            return HostileResponse(super().analyze(*args, **kwargs))

    result = TenderDocumentAiAnalyzer(
        HostileResponseProvider(_valid_payload(risks=[_finding()]))
    ).analyze("procurement:test", (_document(),), context_fingerprint=CONTEXT_FINGERPRINT)

    assert result.status == expected_status
    assert result.warnings == ()
    _assert_no_findings(result)
    assert "RESPONSE-SECRET" not in repr(result)


def test_decoder_exception_is_invalid_response_without_findings(monkeypatch) -> None:
    def fail_decoder(_value):
        raise RuntimeError("response body SECRET")

    monkeypatch.setattr("app.core.ai.analyzer.decode_and_validate_provider_output", fail_decoder)

    result = TenderDocumentAiAnalyzer(Provider(_valid_payload(risks=[_finding()]))).analyze(
        "procurement:test", (_document(),), context_fingerprint=CONTEXT_FINGERPRINT
    )

    assert result.status == "invalid_response"
    assert result.warnings == ()
    _assert_no_findings(result)
    assert "SECRET" not in repr(result)


@pytest.mark.parametrize(
    "model",
    [
        "a/b/c/d/e",
        "fine:tuned:model:family:variant:2026:07",
    ],
)
def test_provenance_preserves_bounded_multi_segment_model_ids(model: str) -> None:
    class NamespacedModelProvider(Provider):
        @property
        def metadata(self) -> AiProviderMetadata:
            return AiProviderMetadata("openai_compatible", model)

    result = TenderDocumentAiAnalyzer(NamespacedModelProvider(_valid_payload())).analyze(
        "procurement:test", (_document(),), context_fingerprint=CONTEXT_FINGERPRINT
    )

    assert result.provenance is not None
    assert result.provenance.provider_id == "openai_compatible"
    assert result.provenance.provider_model == model


@pytest.mark.parametrize(
    ("provider_id", "model", "raw_id", "forbidden"),
    [
        (
            "Authorization:Bearer-SECRET",
            "gpt-4.1",
            "token=private?query#fragment",
            ("Authorization", "SECRET", "token=", "query", "fragment"),
        ),
        (
            "openai",
            "https://provider.example/model?token=SECRET#fragment",
            "response body with SECRET",
            ("https://", "token=", "SECRET", "fragment", "response body"),
        ),
        (
            r"C:\Users\SecretUser\provider",
            "../private/model",
            "body\nSECRET",
            ("SecretUser", "../", "body", "SECRET"),
        ),
        (
            "token=SECRET",
            "prompt body text",
            "x" * 201,
            ("token=", "SECRET", "prompt body", "x" * 64),
        ),
        (
            "openai",
            "https:credential",
            "safe-response-id",
            ("https:credential",),
        ),
        (
            "BearerSECRET",
            "gpt-4.1",
            "safe-response-id",
            ("BearerSECRET", "SECRET"),
        ),
        (
            "openai",
            "a//empty",
            "safe-response-id",
            ("a//empty",),
        ),
        (
            "openai",
            "a::empty",
            "safe-response-id",
            ("a::empty",),
        ),
    ],
)
def test_provenance_persistence_rejects_unsafe_metadata_and_hashes_raw_id(
    provider_id: str,
    model: str,
    raw_id: str,
    forbidden: tuple[str, ...],
) -> None:
    class UnsafeMetadataProvider(Provider):
        @property
        def metadata(self) -> AiProviderMetadata:
            return AiProviderMetadata(provider_id, model)

        def analyze(self, *args, **kwargs) -> dict[str, object]:
            response = super().analyze(*args, **kwargs)
            response["raw_id"] = raw_id
            return response

    result = TenderDocumentAiAnalyzer(UnsafeMetadataProvider(_valid_payload())).analyze(
        "procurement:test", (_document(),), context_fingerprint=CONTEXT_FINGERPRINT
    )

    assert result.provenance is not None
    assert result.provenance.provider_id in {"openai", "unknown"}
    assert result.provenance.provider_model in {"gpt-4.1", "unknown"}
    assert result.provenance.provider_response_id == (
        ""
        if len(raw_id) > 200 or any(ord(char) < 32 or ord(char) == 127 for char in raw_id)
        else "resp_" + hashlib.sha256(raw_id.strip().encode("utf-8")).hexdigest()
    )
    serialized = json.dumps(result.to_payload(), ensure_ascii=False)
    assert all(value not in serialized for value in forbidden)


def test_provenance_sources_are_stable_for_reversed_document_order() -> None:
    first = _document()
    second = AiDocument(
        "doc-2",
        "contract.pdf",
        "local_document_store",
        "contract",
        "2026-07-14T00:00:00+00:00",
        "verified",
        "Contract text.",
        "b" * 64,
        original_character_count=len("Contract text."),
    )
    forward_documents = (first, second)
    reversed_documents = tuple(reversed(forward_documents))
    forward_fingerprint = build_context_fingerprint(forward_documents)
    reversed_fingerprint = build_context_fingerprint(reversed_documents)

    forward = TenderDocumentAiAnalyzer(Provider(_valid_payload())).analyze(
        "procurement:test",
        forward_documents,
        context_fingerprint=forward_fingerprint,
    )
    reversed_result = TenderDocumentAiAnalyzer(Provider(_valid_payload())).analyze(
        "procurement:test",
        reversed_documents,
        context_fingerprint=reversed_fingerprint,
    )

    assert forward_fingerprint == reversed_fingerprint
    assert forward.provenance is not None
    assert reversed_result.provenance is not None
    assert forward.provenance.context_fingerprint == reversed_result.provenance.context_fingerprint
    assert forward.provenance.sources == reversed_result.provenance.sources


def test_resolver_exception_degrades_safely_without_exception_text(monkeypatch) -> None:
    def fail_resolution(**_kwargs):
        raise RuntimeError("C:/SecretUser/private.pdf")

    monkeypatch.setattr("app.core.ai.analyzer.resolve_citation", fail_resolution)

    result = TenderDocumentAiAnalyzer(Provider(_valid_payload(risks=[_finding()]))).analyze(
        "procurement:test", (_document(),), context_fingerprint=CONTEXT_FINGERPRINT
    )

    assert result.status == "partial"
    assert result.risks[0].status is AiFindingStatus.UNVERIFIED
    assert result.risks[0].evidence is None
    assert "Citation evidence could not be resolved safely." in result.warnings
    assert "SecretUser" not in " ".join(result.warnings)


def test_provenance_exception_degrades_safely_without_exception_text() -> None:
    class BrokenMetadataProvider(Provider):
        @property
        def metadata(self) -> AiProviderMetadata:
            raise RuntimeError("Authorization: Bearer SECRET")

    result = TenderDocumentAiAnalyzer(
        BrokenMetadataProvider(_valid_payload(risks=[_finding()]))
    ).analyze("procurement:test", (_document(),), context_fingerprint=CONTEXT_FINGERPRINT)

    assert result.status == "invalid_response"
    assert result.provenance is None
    assert result.risks == ()
    rendered = " ".join(result.warnings)
    assert rendered == "Не удалось определить безопасный контракт AI-анализа."
    assert "SECRET" not in rendered


@pytest.mark.parametrize(
    "finding",
    [
        _finding(document_id="unknown"),
        _finding(quote="delivery period is 30 days"),
        _finding(quote=""),
    ],
)
def test_valid_structure_with_unprovable_evidence_is_partial_and_unverified(finding) -> None:
    payload = _valid_payload(risks=[finding])

    result = TenderDocumentAiAnalyzer(Provider(payload)).analyze(
        "procurement:test", (_document(),), context_fingerprint=CONTEXT_FINGERPRINT
    )

    assert result.status == "partial"
    assert len(result.risks) == 1
    assert result.risks[0].status == AiFindingStatus.UNVERIFIED
    assert result.risks[0].evidence is None


@pytest.mark.parametrize(
    "quote",
    [
        "  delivery period is 10 days",
        "delivery period is 10 days ",
        "delivery period is 10 days\n",
    ],
)
def test_whitespace_changed_quote_remains_unverified(quote: str) -> None:
    payload = _valid_payload(risks=[_finding(quote=quote)])

    result = TenderDocumentAiAnalyzer(Provider(payload)).analyze(
        "procurement:test", (_document(),), context_fingerprint=CONTEXT_FINGERPRINT
    )

    assert result.status == "partial"
    assert result.risks[0].status is AiFindingStatus.UNVERIFIED
    assert result.risks[0].evidence is None


def test_valid_structure_keeps_quote_backed_contradiction_across_documents() -> None:
    second = AiDocument(
        "doc-2",
        "contract.pdf",
        "eis",
        "contract",
        "2026-07-13T00:00:00+00:00",
        "verified",
        "===== Страница 3 =====\nDelivery takes 30 days.",
        "b" * 64,
    )
    payload = _valid_payload(
        contradictions=[
            _finding(
                statement="Different delivery periods",
                document_id="doc-2",
                quote="Delivery takes 30 days",
                page=3,
                confidence=0.95,
            )
        ]
    )

    result = TenderDocumentAiAnalyzer(Provider(payload)).analyze(
        "procurement:test",
        (_document(), second),
        context_fingerprint=CONTEXT_FINGERPRINT,
    )

    assert result.status == "complete"
    assert result.contradictions[0].verified
    assert result.contradictions[0].evidence is not None
    assert result.contradictions[0].evidence.document_id == "doc-2"
    assert result.contradictions[0].evidence.page == 3


def test_unique_quote_with_provider_locator_conflict_is_unverified() -> None:
    document = AiDocument(
        "doc-1",
        "TZ.pdf",
        "eis",
        "technical_specification",
        "2026-07-13T00:00:00+00:00",
        "verified",
        "===== Страница 2 =====\nThe delivery period is 10 days.",
        "a" * 64,
    )
    payload = _valid_payload(risks=[_finding(page=99, section="Provider section")])

    result = TenderDocumentAiAnalyzer(Provider(payload)).analyze(
        "procurement:test", (document,), context_fingerprint=CONTEXT_FINGERPRINT
    )

    assert result.status == "partial"
    assert not result.risks[0].verified
    assert result.risks[0].evidence is None
    assert result.warnings == ("Часть ответа AI отклонена защитной проверкой.",)


def test_no_documents_preserves_deterministic_fallback_without_provider_call() -> None:
    provider = Provider(_valid_payload())

    result = TenderDocumentAiAnalyzer(provider).analyze(
        "procurement:test", (), context_fingerprint=CONTEXT_FINGERPRINT
    )

    assert result.status == "no_documents"
    assert provider.calls == []


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        "```json\n{}\n```",
        "prefix {}",
        "{} suffix",
        "[]",
        "null",
        '{"summary":"a","summary":"b"}',
        '{"value":NaN}',
    ],
)
def test_malformed_or_wrapped_json_is_rejected_without_findings(payload: str) -> None:
    result = TenderDocumentAiAnalyzer(Provider(payload, raw=True)).analyze(
        "procurement:test", (_document(),), context_fingerprint=CONTEXT_FINGERPRINT
    )

    assert result.status == "invalid_response"
    _assert_no_findings(result)


def _extra_root(payload: dict[str, object]) -> None:
    payload["unknown"] = {"private": True}


def _missing_root(payload: dict[str, object]) -> None:
    payload.pop("final_ai_conclusion")


def _wrong_root_type(payload: dict[str, object]) -> None:
    payload["risks"] = "risk"


def _missing_requirement(payload: dict[str, object]) -> None:
    payload["requirements"].pop("equipment")


def _missing_finding_field(payload: dict[str, object]) -> None:
    finding = _finding()
    finding.pop("section")
    payload["risks"] = [finding]


def _extra_finding_field(payload: dict[str, object]) -> None:
    payload["risks"] = [_finding(verified=True)]


def _wrong_finding_type(payload: dict[str, object]) -> None:
    payload["risks"] = [_finding(confidence="0.8")]


@pytest.mark.parametrize(
    "mutate",
    [
        _extra_root,
        _missing_root,
        _wrong_root_type,
        _missing_requirement,
        _missing_finding_field,
        _extra_finding_field,
        _wrong_finding_type,
    ],
)
def test_structural_schema_error_rejects_entire_payload(mutate) -> None:
    payload = _valid_payload(risks=[_finding(statement="Otherwise valid")])
    mutate(payload)

    result = TenderDocumentAiAnalyzer(Provider(payload)).analyze(
        "procurement:test", (_document(),), context_fingerprint=CONTEXT_FINGERPRINT
    )

    assert result.status == "invalid_response"
    _assert_no_findings(result)


def test_provider_exception_disabled_and_error_behaviour_remain_safe() -> None:
    class FailingProvider(Provider):
        def analyze(self, *args, **kwargs) -> dict[str, object]:
            raise TimeoutError("Authorization: Bearer SECRET")

    failed = TenderDocumentAiAnalyzer(FailingProvider(_valid_payload())).analyze(
        "procurement:test", (_document(),), context_fingerprint=CONTEXT_FINGERPRINT
    )
    disabled = TenderDocumentAiAnalyzer(
        Provider(_valid_payload(), provider_status="disabled")
    ).analyze("procurement:test", (_document(),), context_fingerprint=CONTEXT_FINGERPRINT)
    provider_error = TenderDocumentAiAnalyzer(
        Provider(_valid_payload(), provider_status="error")
    ).analyze("procurement:test", (_document(),), context_fingerprint=CONTEXT_FINGERPRINT)

    assert failed.status == "provider_error"
    assert disabled.status == "provider_disabled"
    assert provider_error.status == "provider_error"
    assert "SECRET" not in failed.summary
    assert "private provider response" not in provider_error.summary
    _assert_no_findings(failed)
    _assert_no_findings(disabled)
    _assert_no_findings(provider_error)
