from datetime import datetime

from app.core.ai.schemas import (
    AI_ANALYSIS_SCHEMA_VERSION,
    AiDocumentAnalysis,
)


def test_from_payload_never_promotes_damaged_evidence_to_verified() -> None:
    analysis = AiDocumentAnalysis.from_payload(
        {
            "payload_version": AI_ANALYSIS_SCHEMA_VERSION,
            "registry_key": "procurement:test",
            "summary": "Safe",
            "status": "complete",
            "requirements": {},
            "risks": [
                {
                    "category": "risk",
                    "statement": "Claim",
                    "status": "verified",
                    "evidence": {
                        "document_id": "doc",
                        "quote": "quote",
                        "confidence": "0.9",
                    },
                }
            ],
        }
    )

    assert len(analysis.risks) == 1
    assert not analysis.risks[0].verified
    assert analysis.risks[0].evidence is None


def test_from_payload_reports_future_version_as_incompatible() -> None:
    analysis = AiDocumentAnalysis.from_payload(
        {
            "payload_version": AI_ANALYSIS_SCHEMA_VERSION + 1,
            "registry_key": "procurement:test",
            "status": "complete",
        }
    )

    assert analysis.status == "cache_incompatible"
    assert not analysis.risks


def test_payload_date_is_timezone_aware_and_unknown_status_is_safe() -> None:
    analysis = AiDocumentAnalysis.from_payload(
        {
            "registry_key": "procurement:test",
            "summary": "",
            "status": "future_status",
            "created_at": "2026-07-13T10:00:00",
        }
    )

    assert analysis.status == "invalid_response"
    assert datetime.fromisoformat(analysis.created_at).utcoffset() is not None


def test_non_object_payload_is_safe_invalid_response() -> None:
    analysis = AiDocumentAnalysis.from_payload(["not", "an", "object"])

    assert analysis.status == "invalid_response"
    assert analysis.registry_key == ""
