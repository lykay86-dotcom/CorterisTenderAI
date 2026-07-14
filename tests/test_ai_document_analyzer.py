from __future__ import annotations

from collections.abc import Mapping
import json

import pytest

from app.ai.provider import AIProvider
from app.core.ai.analyzer import TenderDocumentAiAnalyzer
from app.core.ai.output_schema import build_responses_text_format
from app.core.ai.prompts import SYSTEM_PROMPT
from app.core.ai.schemas import AiDocument, AiFindingStatus, TenderRequirements


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
        return {"status": "ok", "text": text}


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
        "requirements": {name: [] for name in TenderRequirements.__dataclass_fields__},
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
        not getattr(result.requirements, name) for name in TenderRequirements.__dataclass_fields__
    )


def test_valid_structure_and_exact_quote_becomes_verified() -> None:
    payload = _valid_payload()
    payload["requirements"]["deadlines"] = [_finding()]
    provider = Provider(payload)

    result = TenderDocumentAiAnalyzer(provider).analyze(
        "procurement:test", (_document(),), context_fingerprint=CONTEXT_FINGERPRINT
    )

    assert result.status == "complete"
    finding = result.requirements.deadlines[0]
    assert finding.status == AiFindingStatus.VERIFIED
    assert finding.evidence is not None
    assert finding.evidence.context_fingerprint == CONTEXT_FINGERPRINT
    assert finding.evidence.checksum_sha256 == "a" * 64
    assert finding.evidence.character_start == _document().text.index(finding.evidence.quote)
    assert provider.calls == [
        (
            SYSTEM_PROMPT,
            ["DOCUMENT doc-1 | TZ.pdf\nThe delivery period is 10 days."],
            build_responses_text_format(),
        )
    ]


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


def test_unique_quote_ignores_provider_locator_conflict_with_safe_warning() -> None:
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
    assert result.risks[0].verified
    assert result.risks[0].evidence is not None
    assert result.risks[0].evidence.page == 2
    assert result.risks[0].evidence.section == "Страница 2"
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
