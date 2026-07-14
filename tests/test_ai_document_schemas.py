from datetime import datetime

import pytest

from app.core.ai.schemas import (
    AI_ANALYSIS_SCHEMA_VERSION,
    AiDocumentAnalysis,
    AiEvidence,
    AiEvidenceVerificationMethod,
    AiFinding,
    AiFindingStatus,
)


def _canonical_evidence() -> AiEvidence:
    return AiEvidence(
        citation_id="cit_" + "a" * 32,
        document_id="doc",
        quote="quote",
        character_start=10,
        character_end=15,
        section="Terms",
        page=2,
        confidence=0.8,
        verification_method=AiEvidenceVerificationMethod.EXACT_QUOTE,
        checksum_sha256="b" * 64,
        source_ref="doc_" + "c" * 32,
        context_fingerprint="d" * 64,
    )


def test_canonical_evidence_requires_every_verification_field() -> None:
    with pytest.raises(TypeError):
        AiEvidence(  # type: ignore[call-arg]
            document_id="doc",
            quote="quote",
            section="",
            page=None,
            confidence=0.8,
        )


def test_canonical_evidence_accepts_complete_exact_quote_contract() -> None:
    evidence = _canonical_evidence()

    assert evidence.character_end == evidence.character_start + len(evidence.quote)


def test_canonical_evidence_round_trips_without_partial_verified_shape() -> None:
    evidence = _canonical_evidence()
    analysis = AiDocumentAnalysis(
        "procurement:test",
        "Safe",
        risks=(AiFinding("risk", "Claim", evidence, AiFindingStatus.VERIFIED),),
        status="complete",
    )

    payload = analysis.to_payload()
    restored = AiDocumentAnalysis.from_payload(payload)

    serialized = payload["risks"][0]["evidence"]
    assert set(serialized) == {
        "citation_id",
        "document_id",
        "quote",
        "character_start",
        "character_end",
        "section",
        "page",
        "confidence",
        "verification_method",
        "checksum_sha256",
        "source_ref",
        "context_fingerprint",
    }
    assert restored.risks[0].status is AiFindingStatus.VERIFIED
    assert restored.risks[0].evidence == evidence


def test_partial_numeric_legacy_evidence_is_safely_downgraded() -> None:
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
                        "confidence": 0.9,
                    },
                }
            ],
        }
    )

    assert analysis.risks[0].status is AiFindingStatus.UNVERIFIED
    assert analysis.risks[0].evidence is None


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
