from __future__ import annotations

from collections.abc import Mapping
import json

from app.ai.provider import AIProvider, AiProviderMetadata
from app.core.ai.analyzer import TenderDocumentAiAnalyzer
from app.core.ai.schemas import (
    AiDocument,
    AiDocumentAnalysis,
    AiDraftContractAnalysis,
    AiDraftContractStatus,
    AiFindingStatus,
    AiTechnicalSpecificationAnalysis,
    TenderRequirements,
)
from app.core.document_classification import DocumentKind


FINGERPRINT = "d" * 64
LOCAL_FIELDS = {"status", "document_ids", "included_document_ids", "warnings"}
DRAFT_FIELDS = tuple(
    name for name in AiDraftContractAnalysis.__dataclass_fields__ if name not in LOCAL_FIELDS
)
TS_FIELDS = tuple(
    name
    for name in AiTechnicalSpecificationAnalysis.__dataclass_fields__
    if name not in LOCAL_FIELDS
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


def _payload(**draft_contract: object) -> dict[str, object]:
    section = {name: [] for name in DRAFT_FIELDS}
    section.update(draft_contract)
    return {
        "summary": "Summary",
        "requirements": {name: [] for name in TenderRequirements.__dataclass_fields__},
        "technical_specification": {name: [] for name in TS_FIELDS},
        "draft_contract": section,
        "risks": [],
        "suspicious_conditions": [],
        "contradictions": [],
        "missing_documents": [],
        "final_ai_conclusion": "Conclusion",
    }


def _document(
    document_id: str = "contract-1",
    *,
    kind: DocumentKind = DocumentKind.DRAFT_CONTRACT,
    text: str = "Оплата производится в течение 10 дней. Оплата производится в течение 30 дней.",
) -> AiDocument:
    return AiDocument(
        document_id,
        "Проект договора.pdf" if kind is DocumentKind.DRAFT_CONTRACT else "Извещение.pdf",
        "local_document_store",
        "pdf",
        "2026-07-15T00:00:00+00:00",
        "verified",
        text,
        ("a" if kind is DocumentKind.DRAFT_CONTRACT else "b") * 64,
        original_character_count=len(text),
        document_kind=kind.value,
    )


def _finding(
    *,
    document_id: str = "contract-1",
    quote: str = "Оплата производится в течение 10 дней.",
    statement: str = "Срок оплаты отличается",
) -> dict[str, object]:
    return {
        "statement": statement,
        "document_id": document_id,
        "quote": quote,
        "section": "",
        "page": None,
        "confidence": 0.9,
    }


def test_complete_verified_contract_uses_one_provider_call_and_round_trips() -> None:
    provider = Provider(_payload(payment_terms=[_finding()]))

    result = TenderDocumentAiAnalyzer(provider).analyze(
        "procurement:test", (_document(),), context_fingerprint=FINGERPRINT
    )

    assert provider.calls == 1
    assert result.draft_contract.status is AiDraftContractStatus.COMPLETE
    assert result.draft_contract.document_ids == ("contract-1",)
    finding = result.draft_contract.payment_terms[0]
    assert finding.status is AiFindingStatus.VERIFIED
    assert finding.evidence is not None
    restored = AiDocumentAnalysis.from_payload(result.to_payload())
    assert restored.draft_contract.payment_terms[0].status is AiFindingStatus.VERIFIED


def test_non_contract_unknown_and_altered_evidence_remain_unverified() -> None:
    payload = _payload(
        payment_terms=[
            _finding(document_id="notice"),
            _finding(document_id="unknown"),
            _finding(quote="Изменённая цитата"),
        ]
    )
    result = TenderDocumentAiAnalyzer(Provider(payload)).analyze(
        "procurement:test",
        (_document(), _document("notice", kind=DocumentKind.PROCUREMENT_NOTICE)),
        context_fingerprint=FINGERPRINT,
    )

    assert result.draft_contract.status is AiDraftContractStatus.PARTIAL
    assert len(result.draft_contract.payment_terms) == 3
    assert all(
        not item.verified and item.evidence is None for item in result.draft_contract.payment_terms
    )


def test_contract_locator_conflict_is_unverified_and_partial() -> None:
    finding = _finding()
    finding["page"] = 99
    finding["section"] = "Несовпадающий раздел"

    result = TenderDocumentAiAnalyzer(Provider(_payload(payment_terms=[finding]))).analyze(
        "procurement:test", (_document(),), context_fingerprint=FINGERPRINT
    )

    assert result.draft_contract.status is AiDraftContractStatus.PARTIAL
    assert not result.draft_contract.payment_terms[0].verified
    assert result.draft_contract.payment_terms[0].evidence is None


def test_contract_not_found_and_provider_failures_are_local_statuses() -> None:
    missing = TenderDocumentAiAnalyzer(Provider(_payload())).analyze(
        "procurement:test",
        (_document(kind=DocumentKind.PROCUREMENT_NOTICE),),
        context_fingerprint=FINGERPRINT,
    )
    disabled = TenderDocumentAiAnalyzer(Provider(_payload(), status="disabled")).analyze(
        "procurement:test", (_document(),), context_fingerprint=FINGERPRINT
    )

    assert missing.draft_contract.status is AiDraftContractStatus.NOT_FOUND
    assert disabled.draft_contract.status is AiDraftContractStatus.UNAVAILABLE


def test_malformed_or_provider_controlled_contract_object_rejects_whole_payload() -> None:
    missing_key = _payload()
    missing_key["draft_contract"].pop("subject_and_scope")
    provider_status = _payload()
    provider_status["draft_contract"]["status"] = "complete"

    for payload in (missing_key, provider_status):
        result = TenderDocumentAiAnalyzer(Provider(payload)).analyze(
            "procurement:test", (_document(),), context_fingerprint=FINGERPRINT
        )
        assert result.status.value == "invalid_response"
        assert result.draft_contract.status is AiDraftContractStatus.UNAVAILABLE


def test_contract_contradiction_requires_two_distinct_canonical_citations() -> None:
    first = _finding()
    second = _finding(quote="Оплата производится в течение 30 дней.")
    one = TenderDocumentAiAnalyzer(Provider(_payload(contradictions=[first]))).analyze(
        "procurement:test", (_document(),), context_fingerprint=FINGERPRINT
    )
    duplicate = TenderDocumentAiAnalyzer(
        Provider(_payload(contradictions=[first, dict(first)]))
    ).analyze("procurement:test", (_document(),), context_fingerprint=FINGERPRINT)
    distinct = TenderDocumentAiAnalyzer(Provider(_payload(contradictions=[first, second]))).analyze(
        "procurement:test", (_document(),), context_fingerprint=FINGERPRINT
    )

    assert not one.draft_contract.contradictions[0].verified
    assert not any(item.verified for item in duplicate.draft_contract.contradictions)
    assert all(item.verified for item in distinct.draft_contract.contradictions)


def test_findings_from_distinct_sources_are_not_deduplicated() -> None:
    second = _document("contract-2")
    result = TenderDocumentAiAnalyzer(
        Provider(
            _payload(
                payment_terms=[
                    _finding(document_id="contract-1"),
                    _finding(document_id="contract-2"),
                ]
            )
        )
    ).analyze("procurement:test", (_document(), second), context_fingerprint=FINGERPRINT)

    assert len(result.draft_contract.payment_terms) == 2
    assert {
        item.evidence.document_id for item in result.draft_contract.payment_terms if item.evidence
    } == {
        "contract-1",
        "contract-2",
    }


def test_cached_generic_or_ts_evidence_cannot_be_promoted_to_contract() -> None:
    payload = _payload()
    payload["risks"] = [_finding(document_id="notice")]
    result = TenderDocumentAiAnalyzer(Provider(payload)).analyze(
        "procurement:test",
        (_document(), _document("notice", kind=DocumentKind.PROCUREMENT_NOTICE)),
        context_fingerprint=FINGERPRINT,
    )
    stored = result.to_payload()
    stored["draft_contract"]["document_ids"] = ["notice"]
    stored["draft_contract"]["payment_terms"] = stored["risks"]

    restored = AiDocumentAnalysis.from_payload(stored)

    finding = restored.draft_contract.payment_terms[0]
    assert finding.status is AiFindingStatus.UNVERIFIED
    assert finding.evidence is None


def test_corrupt_cached_contract_shape_fails_closed() -> None:
    result = TenderDocumentAiAnalyzer(Provider(_payload(payment_terms=[_finding()]))).analyze(
        "procurement:test", (_document(),), context_fingerprint=FINGERPRINT
    )
    stored = result.to_payload()
    stored["draft_contract"]["unexpected"] = []

    restored = AiDocumentAnalysis.from_payload(stored)

    assert restored.draft_contract.status is AiDraftContractStatus.UNAVAILABLE
    assert not restored.draft_contract.payment_terms


def test_legacy_payload_reads_with_unavailable_empty_contract_section() -> None:
    result = TenderDocumentAiAnalyzer(Provider(_payload(payment_terms=[_finding()]))).analyze(
        "procurement:test", (_document(),), context_fingerprint=FINGERPRINT
    )
    legacy = result.to_payload()
    legacy["payload_version"] = 4
    legacy.pop("draft_contract")

    restored = AiDocumentAnalysis.from_payload(legacy)

    assert restored.payload_version == 4
    assert restored.draft_contract.status is AiDraftContractStatus.UNAVAILABLE
    assert not restored.draft_contract.payment_terms


def test_cached_ts_evidence_cannot_be_promoted_to_contract() -> None:
    ts = _document(
        "ts",
        kind=DocumentKind.TECHNICAL_SPECIFICATION,
        text="Поставка включает насос.",
    )
    payload = _payload()
    payload["technical_specification"]["scope"] = [
        _finding(document_id="ts", quote="Поставка включает насос.")
    ]
    result = TenderDocumentAiAnalyzer(Provider(payload)).analyze(
        "procurement:test", (_document(), ts), context_fingerprint=FINGERPRINT
    )
    stored = result.to_payload()
    stored["draft_contract"]["subject_and_scope"] = stored["technical_specification"]["scope"]

    restored = AiDocumentAnalysis.from_payload(stored)

    finding = restored.draft_contract.subject_and_scope[0]
    assert finding.status is AiFindingStatus.UNVERIFIED
    assert finding.evidence is None
