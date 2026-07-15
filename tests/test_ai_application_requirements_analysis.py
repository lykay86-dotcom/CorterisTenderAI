from __future__ import annotations

from collections.abc import Mapping
import json

import pytest

from app.ai.provider import AIProvider, AiProviderMetadata
from app.core.ai.analyzer import TenderDocumentAiAnalyzer
from app.core.ai.schemas import (
    AiApplicationRequirementsStatus,
    AiDocument,
    AiDocumentAnalysis,
    AiDraftContractAnalysis,
    AiFindingStatus,
    AiTechnicalSpecificationAnalysis,
    _APPLICATION_REQUIREMENTS_FINDING_FIELDS,
)
from app.core.document_classification import (
    APPLICATION_REQUIREMENTS_SOURCE_KINDS,
    DocumentKind,
    classify_document_kind,
)


FINGERPRINT = "e" * 64
LOCAL_FIELDS = {"status", "document_ids", "included_document_ids", "warnings"}
EXPECTED_REQUIREMENT_FIELDS = (
    "application_composition",
    "participant_eligibility",
    "declarations_and_consents",
    "equipment",
    "certificates",
    "licenses",
    "specialists",
    "documents",
    "experience",
    "deadlines",
    "warranty",
    "bid_security",
    "contract_security",
    "bank_guarantee",
    "submission_format_and_signature",
    "national_regime_and_origin",
    "price_proposal_and_estimate",
    "grounds_for_rejection",
    "ambiguities",
    "contradictions",
    "clarification_points",
)
TS_FIELDS = tuple(
    name
    for name in AiTechnicalSpecificationAnalysis.__dataclass_fields__
    if name not in LOCAL_FIELDS
)
CONTRACT_FIELDS = tuple(
    name for name in AiDraftContractAnalysis.__dataclass_fields__ if name not in LOCAL_FIELDS
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


def _payload(**requirements: object) -> dict[str, object]:
    section = {name: [] for name in EXPECTED_REQUIREMENT_FIELDS}
    section.update(requirements)
    return {
        "summary": "Summary",
        "requirements": section,
        "technical_specification": {name: [] for name in TS_FIELDS},
        "draft_contract": {name: [] for name in CONTRACT_FIELDS},
        "risks": [],
        "suspicious_conditions": [],
        "contradictions": [],
        "missing_documents": [],
        "final_ai_conclusion": "Conclusion",
    }


def _document(
    document_id: str = "requirements-1",
    *,
    kind: DocumentKind = DocumentKind.APPLICATION_REQUIREMENTS,
    text: str = "В составе заявки требуется приложить выписку из реестра.",
) -> AiDocument:
    return AiDocument(
        document_id,
        "Требования к составу заявки.pdf",
        "local_document_store",
        "pdf",
        "2026-07-15T00:00:00+00:00",
        "verified",
        text,
        ("a" if kind in APPLICATION_REQUIREMENTS_SOURCE_KINDS else "b") * 64,
        original_character_count=len(text),
        document_kind=kind.value,
    )


def _finding(
    *,
    document_id: str = "requirements-1",
    quote: str = "В составе заявки требуется приложить выписку из реестра.",
    statement: str = "Требуется выписка из реестра",
) -> dict[str, object]:
    return {
        "statement": statement,
        "document_id": document_id,
        "quote": quote,
        "section": "",
        "page": None,
        "confidence": 0.9,
    }


def test_application_requirements_contract_has_one_scope_and_exactly_21_groups() -> None:
    assert APPLICATION_REQUIREMENTS_SOURCE_KINDS == frozenset(
        {
            DocumentKind.APPLICATION_REQUIREMENTS,
            DocumentKind.APPLICATION_FORM,
            DocumentKind.INSTRUCTIONS,
            DocumentKind.PROCUREMENT_NOTICE,
        }
    )
    assert _APPLICATION_REQUIREMENTS_FINDING_FIELDS == EXPECTED_REQUIREMENT_FIELDS


@pytest.mark.parametrize(
    ("name", "text"),
    (
        ("Требования к содержанию и составу заявки.pdf", ""),
        ("Требования к составу заявки.docx", ""),
        ("Требования к заявке.pdf", ""),
        ("Перечень документов в составе заявки.xlsx", ""),
        ("Требования к участникам и составу заявки.pdf", ""),
        ("Приложение.pdf", "Требования к содержанию и составу заявки\nУчастник предоставляет..."),
    ),
)
def test_classifier_recognizes_explicit_application_requirements(name: str, text: str) -> None:
    assert classify_document_kind(name, text) is DocumentKind.APPLICATION_REQUIREMENTS


@pytest.mark.parametrize(
    ("name", "text", "expected"),
    (
        ("Информационная карта.pdf", "Обеспечение заявки", DocumentKind.PROCUREMENT_NOTICE),
        ("Инструкция по заполнению заявки.pdf", "", DocumentKind.INSTRUCTIONS),
        ("Форма заявки.pdf", "", DocumentKind.APPLICATION_FORM),
        (
            "Техническое задание.pdf",
            "В заявке указать модель",
            DocumentKind.TECHNICAL_SPECIFICATION,
        ),
        ("Проект договора.pdf", "Заявка является приложением", DocumentKind.DRAFT_CONTRACT),
        ("Расчет НМЦК.xlsx", "Обеспечение заявки", DocumentKind.ESTIMATE),
        ("Протокол рассмотрения заявок.pdf", "Заявки рассмотрены", DocumentKind.OTHER),
        ("Заявка ООО Поставщик.pdf", "Наша заявка содержит документы", DocumentKind.OTHER),
        (
            "Приложение к договору — Техническое задание.pdf",
            "Требования к составу заявки",
            DocumentKind.TECHNICAL_SPECIFICATION,
        ),
    ),
)
def test_classifier_preserves_existing_priorities_and_rejects_bare_application_word(
    name: str,
    text: str,
    expected: DocumentKind,
) -> None:
    assert classify_document_kind(name, text) is expected


def test_complete_verified_requirements_use_one_provider_call_and_round_trip() -> None:
    provider = Provider(_payload(documents=[_finding()]))

    result = TenderDocumentAiAnalyzer(provider).analyze(
        "procurement:test", (_document(),), context_fingerprint=FINGERPRINT
    )

    assert provider.calls == 1
    assert result.requirements.status is AiApplicationRequirementsStatus.COMPLETE
    assert result.requirements.document_ids == ("requirements-1",)
    assert result.requirements.included_document_ids == ("requirements-1",)
    finding = result.requirements.documents[0]
    assert finding.status is AiFindingStatus.VERIFIED
    restored = AiDocumentAnalysis.from_payload(result.to_payload())
    assert restored.requirements.documents[0].status is AiFindingStatus.VERIFIED


def test_empty_valid_requirements_payload_can_be_complete() -> None:
    result = TenderDocumentAiAnalyzer(Provider(_payload())).analyze(
        "procurement:test", (_document(),), context_fingerprint=FINGERPRINT
    )

    assert result.requirements.status is AiApplicationRequirementsStatus.COMPLETE
    assert all(not getattr(result.requirements, name) for name in EXPECTED_REQUIREMENT_FIELDS)


def test_requirements_not_found_and_provider_failures_are_local_statuses() -> None:
    missing = TenderDocumentAiAnalyzer(Provider(_payload())).analyze(
        "procurement:test",
        (_document(kind=DocumentKind.TECHNICAL_SPECIFICATION),),
        context_fingerprint=FINGERPRINT,
    )
    disabled = TenderDocumentAiAnalyzer(Provider(_payload(), status="disabled")).analyze(
        "procurement:test", (_document(),), context_fingerprint=FINGERPRINT
    )

    assert missing.requirements.status is AiApplicationRequirementsStatus.NOT_FOUND
    assert disabled.requirements.status is AiApplicationRequirementsStatus.UNAVAILABLE
    assert disabled.requirements.document_ids == ("requirements-1",)


def test_wrong_kind_unknown_altered_and_locator_conflict_remain_unverified() -> None:
    wrong = _document("ts", kind=DocumentKind.TECHNICAL_SPECIFICATION)
    locator = _finding()
    locator["page"] = 99
    payload = _payload(
        documents=[
            _finding(document_id="ts"),
            _finding(document_id="unknown"),
            _finding(quote="Изменённая цитата"),
            locator,
        ]
    )

    result = TenderDocumentAiAnalyzer(Provider(payload)).analyze(
        "procurement:test", (_document(), wrong), context_fingerprint=FINGERPRINT
    )

    assert result.requirements.status is AiApplicationRequirementsStatus.PARTIAL
    assert len(result.requirements.documents) == 4
    assert all(
        not item.verified and item.evidence is None for item in result.requirements.documents
    )


def test_provider_owned_local_field_or_missing_group_rejects_whole_payload() -> None:
    provider_status = _payload()
    provider_status["requirements"]["status"] = "complete"
    missing = _payload()
    missing["requirements"].pop("application_composition")

    for payload in (provider_status, missing):
        result = TenderDocumentAiAnalyzer(Provider(payload)).analyze(
            "procurement:test", (_document(),), context_fingerprint=FINGERPRINT
        )
        assert result.status.value == "invalid_response"
        assert result.requirements.status is AiApplicationRequirementsStatus.UNAVAILABLE


def test_requirement_contradiction_needs_distinct_canonical_citations() -> None:
    document = _document(
        text=("Срок действия заявки составляет 30 дней. Срок действия заявки составляет 60 дней.")
    )
    first = _finding(
        quote="Срок действия заявки составляет 30 дней.",
        statement="Срок действия заявки противоречив",
    )
    second = _finding(
        quote="Срок действия заявки составляет 60 дней.",
        statement="Срок действия заявки противоречив",
    )
    one = TenderDocumentAiAnalyzer(Provider(_payload(contradictions=[first]))).analyze(
        "procurement:test", (document,), context_fingerprint=FINGERPRINT
    )
    distinct = TenderDocumentAiAnalyzer(Provider(_payload(contradictions=[first, second]))).analyze(
        "procurement:test", (document,), context_fingerprint=FINGERPRINT
    )

    assert not one.requirements.contradictions[0].verified
    assert all(item.verified for item in distinct.requirements.contradictions)


def test_legacy_v5_requirements_are_unavailable_unscoped_and_unverified() -> None:
    result = TenderDocumentAiAnalyzer(Provider(_payload(documents=[_finding()]))).analyze(
        "procurement:test", (_document(),), context_fingerprint=FINGERPRINT
    )
    legacy = result.to_payload()
    legacy["payload_version"] = 5
    legacy["requirements"] = {
        name: legacy["requirements"][name]
        for name in (
            "equipment",
            "certificates",
            "licenses",
            "specialists",
            "documents",
            "experience",
            "deadlines",
            "warranty",
            "bid_security",
            "contract_security",
            "bank_guarantee",
        )
    }

    restored = AiDocumentAnalysis.from_payload(legacy)

    assert restored.requirements.status is AiApplicationRequirementsStatus.UNAVAILABLE
    assert restored.requirements.document_ids == ()
    assert restored.requirements.included_document_ids == ()
    assert restored.requirements.warnings
    assert restored.requirements.documents[0].status is AiFindingStatus.UNVERIFIED
    assert not restored.requirements.application_composition


def test_current_corrupt_shape_and_foreign_cached_evidence_fail_closed() -> None:
    result = TenderDocumentAiAnalyzer(Provider(_payload(documents=[_finding()]))).analyze(
        "procurement:test", (_document(),), context_fingerprint=FINGERPRINT
    )
    corrupt = result.to_payload()
    corrupt["requirements"]["unexpected"] = []
    restored_corrupt = AiDocumentAnalysis.from_payload(corrupt)
    assert restored_corrupt.requirements.status is AiApplicationRequirementsStatus.UNAVAILABLE
    assert not restored_corrupt.requirements.documents

    ts_result = TenderDocumentAiAnalyzer(Provider(_payload())).analyze(
        "procurement:test",
        (_document(), _document("ts", kind=DocumentKind.TECHNICAL_SPECIFICATION)),
        context_fingerprint=FINGERPRINT,
    )
    foreign = ts_result.to_payload()
    foreign["requirements"]["documents"] = result.to_payload()["requirements"]["documents"]
    foreign["requirements"]["document_ids"] = ["ts"]
    foreign["requirements"]["included_document_ids"] = ["ts"]
    restored_foreign = AiDocumentAnalysis.from_payload(foreign)
    assert restored_foreign.requirements.documents[0].status is AiFindingStatus.UNVERIFIED
    assert restored_foreign.requirements.documents[0].evidence is None
