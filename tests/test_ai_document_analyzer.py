from __future__ import annotations

import json

import pytest

from app.ai.provider import AIProvider
from app.core.ai.analyzer import TenderDocumentAiAnalyzer
from app.core.ai.schemas import AiDocument, AiFindingStatus


class Provider(AIProvider):
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def analyze(self, prompt: str, documents: list[str]) -> dict:
        return {"status": "ok", "text": json.dumps(self.payload)}


def _document() -> AiDocument:
    return AiDocument(
        "doc-1",
        "TZ.pdf",
        "eis",
        "technical_specification",
        "2026-07-13T00:00:00+00:00",
        "verified",
        "The delivery period is 10 days.",
    )


def test_analyzer_keeps_only_quote_backed_findings_verified() -> None:
    analyzer = TenderDocumentAiAnalyzer(
        Provider(
            {
                "summary": "Summary",
                "requirements": {
                    "deadlines": [
                        {
                            "statement": "Ten days",
                            "document_id": "doc-1",
                            "quote": "delivery period is 10 days",
                            "confidence": 0.8,
                        }
                    ]
                },
            }
        )
    )

    result = analyzer.analyze("procurement:test", (_document(),))

    finding = result.requirements.deadlines[0]
    assert finding.status == AiFindingStatus.VERIFIED
    assert finding.evidence is not None


def test_analyzer_marks_hallucinated_or_unknown_document_unverified() -> None:
    analyzer = TenderDocumentAiAnalyzer(
        Provider(
            {
                "risks": [
                    {
                        "statement": "Invented",
                        "document_id": "unknown",
                        "quote": "not present",
                        "confidence": 0.9,
                    }
                ]
            }
        )
    )

    result = analyzer.analyze("procurement:test", (_document(),))

    assert result.risks[0].status == AiFindingStatus.UNVERIFIED
    assert result.risks[0].evidence is None


def test_analyzer_handles_missing_documents_and_invalid_provider_response() -> None:
    analyzer = TenderDocumentAiAnalyzer(Provider({}))

    assert analyzer.analyze("procurement:test", ()).status == "no_documents"


def test_analyzer_handles_invalid_json_without_inventing_result() -> None:
    provider = Provider({})
    provider.analyze = lambda _prompt, _documents: {"status": "ok", "text": "not-json"}

    result = TenderDocumentAiAnalyzer(provider).analyze("procurement:test", (_document(),))

    assert result.status == "invalid_response"
    assert not result.risks


def test_analyzer_detects_quote_backed_contradictions_across_documents() -> None:
    second = AiDocument(
        "doc-2", "contract.pdf", "eis", "contract", "now", "verified", "Delivery takes 30 days."
    )
    analyzer = TenderDocumentAiAnalyzer(
        Provider(
            {
                "contradictions": [
                    {
                        "statement": "Different delivery periods",
                        "document_id": "doc-2",
                        "quote": "Delivery takes 30 days",
                        "confidence": 0.95,
                    }
                ]
            }
        )
    )

    result = analyzer.analyze("procurement:test", (_document(), second))

    assert result.contradictions[0].verified
    assert result.contradictions[0].evidence.document_id == "doc-2"


def test_analyzer_contains_provider_exception_and_disabled_state() -> None:
    provider = Provider({})
    provider.analyze = lambda *_args: (_ for _ in ()).throw(
        TimeoutError("Authorization: Bearer SECRET")
    )

    failed = TenderDocumentAiAnalyzer(provider).analyze("procurement:test", (_document(),))
    provider.analyze = lambda *_args: {"status": "disabled", "message": "off"}
    disabled = TenderDocumentAiAnalyzer(provider).analyze("procurement:test", (_document(),))

    assert failed.status == "provider_error"
    assert disabled.status == "provider_disabled"
    assert "SECRET" not in failed.summary


def test_analyzer_contains_provider_error_status() -> None:
    provider = Provider({})
    provider.analyze = lambda *_args: {
        "status": "error",
        "message": "raw provider response",
    }

    result = TenderDocumentAiAnalyzer(provider).analyze("procurement:test", (_document(),))

    assert result.status == "provider_error"
    assert "raw provider response" not in result.summary


@pytest.mark.parametrize("payload", [[], "text", 42, None])
def test_analyzer_rejects_non_object_json(payload: object) -> None:
    result = TenderDocumentAiAnalyzer(Provider(payload)).analyze("procurement:test", (_document(),))

    assert result.status == "invalid_response"
    assert not result.risks


@pytest.mark.parametrize("requirements", [None, [], "bad"])
def test_analyzer_safely_rejects_invalid_requirements_container(
    requirements: object,
) -> None:
    result = TenderDocumentAiAnalyzer(
        Provider({"summary": "usable", "requirements": requirements})
    ).analyze("procurement:test", (_document(),))

    assert result.status == "partial"
    assert result.summary == "usable"


def test_analyzer_rejects_invalid_category_and_finding_independently() -> None:
    result = TenderDocumentAiAnalyzer(
        Provider(
            {
                "requirements": {"licenses": "bad"},
                "risks": [
                    "bad finding",
                    {
                        "statement": "Confirmed deadline risk",
                        "document_id": "doc-1",
                        "quote": "delivery period is 10 days",
                        "confidence": 0.8,
                    },
                ],
            }
        )
    ).analyze("procurement:test", (_document(),))

    assert result.status == "partial"
    assert len(result.risks) == 1
    assert result.risks[0].verified


@pytest.mark.parametrize(
    "confidence",
    [-0.1, 1.1, "0.8", None, float("nan"), float("inf")],
)
def test_analyzer_never_verifies_invalid_confidence(confidence: object) -> None:
    result = TenderDocumentAiAnalyzer(
        Provider(
            {
                "risks": [
                    {
                        "statement": "Deadline",
                        "document_id": "doc-1",
                        "quote": "delivery period is 10 days",
                        "confidence": confidence,
                    }
                ]
            }
        )
    ).analyze("procurement:test", (_document(),))

    assert result.status == "partial"
    assert not result.risks[0].verified
    assert result.risks[0].evidence is None


@pytest.mark.parametrize("page", ["1", 0, -1, True, 1.5, []])
def test_analyzer_normalizes_invalid_page_without_crashing(page: object) -> None:
    result = TenderDocumentAiAnalyzer(
        Provider(
            {
                "risks": [
                    {
                        "statement": "Deadline",
                        "document_id": "doc-1",
                        "quote": "delivery period is 10 days",
                        "confidence": 0.8,
                        "page": page,
                    }
                ]
            }
        )
    ).analyze("procurement:test", (_document(),))

    assert result.status == "partial"
    assert result.risks[0].evidence is not None
    assert result.risks[0].evidence.page is None


def test_analyzer_handles_missing_statement_document_and_quote() -> None:
    result = TenderDocumentAiAnalyzer(
        Provider(
            {
                "risks": [
                    {"document_id": "doc-1", "quote": "delivery", "confidence": 0.8},
                    {"statement": "No quote", "document_id": "doc-1", "confidence": 0.8},
                    {"statement": "No document", "quote": "delivery", "confidence": 0.8},
                ]
            }
        )
    ).analyze("procurement:test", (_document(),))

    assert result.status == "partial"
    assert [item.statement for item in result.risks] == ["No quote", "No document"]
    assert all(not item.verified for item in result.risks)


def test_analyzer_limits_text_fields_and_ignores_unknown_fields() -> None:
    result = TenderDocumentAiAnalyzer(
        Provider(
            {
                "summary": "s" * 20_000,
                "unknown": {"secret": "ignored"},
                "risks": [
                    {
                        "statement": "x" * 10_000,
                        "document_id": "doc-1",
                        "quote": "q" * 10_000,
                        "confidence": 0.8,
                        "unknown": True,
                    }
                ],
            }
        )
    ).analyze("procurement:test", (_document(),))

    assert result.status == "partial"
    assert len(result.summary) == 12_000
    assert len(result.risks[0].statement) == 4_000
    assert result.risks[0].evidence is None


def test_analyzer_unknown_top_level_fields_do_not_break_valid_payload() -> None:
    result = TenderDocumentAiAnalyzer(
        Provider({"summary": "ok", "future_field": {"anything": True}})
    ).analyze("procurement:test", (_document(),))

    assert result.status == "complete"
    assert result.summary == "ok"
