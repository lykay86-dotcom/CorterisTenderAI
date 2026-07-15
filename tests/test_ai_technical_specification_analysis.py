from __future__ import annotations

from collections.abc import Mapping
import json

from app.ai.provider import AIProvider, AiProviderMetadata
from app.core.ai.analyzer import TenderDocumentAiAnalyzer
from app.core.ai.schemas import (
    AiDocument,
    AiDocumentAnalysis,
    AiDraftContractAnalysis,
    AiFindingStatus,
    AiTechnicalSpecificationAnalysis,
    AiTechnicalSpecificationStatus,
    _APPLICATION_REQUIREMENTS_FINDING_FIELDS,
)
from app.core.document_classification import DocumentKind, classify_document_kind


FINGERPRINT = "f" * 64
TS_FIELDS = tuple(
    name
    for name in AiTechnicalSpecificationAnalysis.__dataclass_fields__
    if name not in {"status", "document_ids", "included_document_ids", "warnings"}
)
DRAFT_FIELDS = tuple(
    name
    for name in AiDraftContractAnalysis.__dataclass_fields__
    if name not in {"status", "document_ids", "included_document_ids", "warnings"}
)


class Provider(AIProvider):
    def __init__(self, payload: object, status: str = "ok") -> None:
        self.payload = payload
        self.status = status
        self.calls = 0

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
        self.calls += 1
        if self.status != "ok":
            return {"status": self.status}
        return {"status": "ok", "text": json.dumps(self.payload), "raw_id": "response"}


def _payload(**technical: object) -> dict[str, object]:
    section = {name: [] for name in TS_FIELDS}
    section.update(technical)
    return {
        "summary": "Summary",
        "requirements": {name: [] for name in _APPLICATION_REQUIREMENTS_FINDING_FIELDS},
        "technical_specification": section,
        "draft_contract": {name: [] for name in DRAFT_FIELDS},
        "risks": [],
        "suspicious_conditions": [],
        "contradictions": [],
        "missing_documents": [],
        "final_ai_conclusion": "Conclusion",
    }


def _document(document_id: str = "ts-1", *, technical: bool = True) -> AiDocument:
    return AiDocument(
        document_id,
        "Техническое задание.pdf" if technical else "Проект договора.pdf",
        "local_document_store",
        "pdf",
        "2026-07-15T00:00:00+00:00",
        "verified",
        "Поставка включает насос производительностью 10 м3/ч.",
        ("a" if technical else "b") * 64,
        document_kind=(
            DocumentKind.TECHNICAL_SPECIFICATION.value
            if technical
            else DocumentKind.DRAFT_CONTRACT.value
        ),
    )


def _finding(document_id: str = "ts-1", statement: str = "Насос 10 м3/ч") -> dict[str, object]:
    return {
        "statement": statement,
        "document_id": document_id,
        "quote": "насос производительностью 10 м3/ч",
        "section": "",
        "page": None,
        "confidence": 0.9,
    }


def test_public_classifier_is_shared_and_avoids_contract_false_positive() -> None:
    assert (
        classify_document_kind("Техническое задание.pdf", "")
        is DocumentKind.TECHNICAL_SPECIFICATION
    )
    assert (
        classify_document_kind("appendix.pdf", "Описание объекта закупки")
        is DocumentKind.TECHNICAL_SPECIFICATION
    )
    assert (
        classify_document_kind("Проект договора.pdf", "Текст договора")
        is DocumentKind.DRAFT_CONTRACT
    )


def test_complete_verified_ts_uses_one_provider_call_and_round_trips() -> None:
    provider = Provider(_payload(scope=[_finding()]))
    result = TenderDocumentAiAnalyzer(provider).analyze(
        "procurement:test", (_document(),), context_fingerprint=FINGERPRINT
    )

    assert provider.calls == 1
    assert result.technical_specification.status is AiTechnicalSpecificationStatus.COMPLETE
    finding = result.technical_specification.scope[0]
    assert finding.status is AiFindingStatus.VERIFIED
    assert finding.evidence is not None
    restored = AiDocumentAnalysis.from_payload(result.to_payload())
    assert restored.technical_specification.scope[0].status is AiFindingStatus.VERIFIED


def test_non_ts_evidence_is_retained_unverified_and_makes_section_partial() -> None:
    result = TenderDocumentAiAnalyzer(Provider(_payload(scope=[_finding("contract")]))).analyze(
        "procurement:test",
        (_document(), _document("contract", technical=False)),
        context_fingerprint=FINGERPRINT,
    )

    assert result.technical_specification.status is AiTechnicalSpecificationStatus.PARTIAL
    assert result.technical_specification.scope[0].status is AiFindingStatus.UNVERIFIED
    assert result.technical_specification.scope[0].evidence is None


def test_missing_ts_is_not_found_and_disabled_provider_is_unavailable() -> None:
    not_found = TenderDocumentAiAnalyzer(Provider(_payload())).analyze(
        "procurement:test", (_document(technical=False),), context_fingerprint=FINGERPRINT
    )
    unavailable = TenderDocumentAiAnalyzer(Provider(_payload(), status="disabled")).analyze(
        "procurement:test", (_document(),), context_fingerprint=FINGERPRINT
    )

    assert not_found.technical_specification.status is AiTechnicalSpecificationStatus.NOT_FOUND
    assert unavailable.technical_specification.status is AiTechnicalSpecificationStatus.UNAVAILABLE


def test_malformed_nested_object_rejects_entire_provider_payload() -> None:
    payload = _payload()
    payload["technical_specification"].pop("scope")

    result = TenderDocumentAiAnalyzer(Provider(payload)).analyze(
        "procurement:test", (_document(),), context_fingerprint=FINGERPRINT
    )

    assert result.status.value == "invalid_response"


def test_single_source_contradiction_is_unverified_but_two_sources_are_verified() -> None:
    statement = "Несовместимые значения"
    one = TenderDocumentAiAnalyzer(
        Provider(_payload(contradictions=[_finding(statement=statement)]))
    ).analyze("procurement:test", (_document(),), context_fingerprint=FINGERPRINT)
    second = _document("ts-2")
    two = TenderDocumentAiAnalyzer(
        Provider(
            _payload(
                contradictions=[
                    _finding(statement=statement),
                    _finding("ts-2", statement=statement),
                ]
            )
        )
    ).analyze("procurement:test", (_document(), second), context_fingerprint=FINGERPRINT)

    assert one.technical_specification.contradictions[0].status is AiFindingStatus.UNVERIFIED
    assert all(item.verified for item in two.technical_specification.contradictions)


def test_cached_non_ts_evidence_cannot_be_promoted_into_technical_section() -> None:
    payload = _payload()
    payload["risks"] = [_finding("contract")]
    result = TenderDocumentAiAnalyzer(Provider(payload)).analyze(
        "procurement:test",
        (_document(), _document("contract", technical=False)),
        context_fingerprint=FINGERPRINT,
    )
    stored = result.to_payload()
    stored["technical_specification"]["document_ids"] = ["contract"]
    stored["technical_specification"]["scope"] = stored["risks"]

    restored = AiDocumentAnalysis.from_payload(stored)

    finding = restored.technical_specification.scope[0]
    assert finding.status is AiFindingStatus.UNVERIFIED
    assert finding.evidence is None


def test_damaged_cached_technical_shape_fails_closed() -> None:
    result = TenderDocumentAiAnalyzer(Provider(_payload(scope=[_finding()]))).analyze(
        "procurement:test", (_document(),), context_fingerprint=FINGERPRINT
    )
    stored = result.to_payload()
    stored["technical_specification"]["status"] = "provider-controlled"

    restored = AiDocumentAnalysis.from_payload(stored)

    assert restored.technical_specification.status is AiTechnicalSpecificationStatus.UNAVAILABLE
    assert not restored.technical_specification.scope
