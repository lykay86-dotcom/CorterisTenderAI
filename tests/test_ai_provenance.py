from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime
import json

import pytest

from app.core.ai.schemas import (
    AI_ANALYSIS_SCHEMA_VERSION,
    AiAnalysisProvenance,
    AiDocumentAnalysis,
    AiEvidence,
    AiFinding,
    AiFindingStatus,
    AiSourceSnapshot,
)


FINGERPRINT = "d" * 64
CHECKSUM = "b" * 64


def _source(**changes: object) -> AiSourceSnapshot:
    values: dict[str, object] = {
        "document_id": "doc",
        "display_name": r"C:\Users\SecretUser\Documents\tender.pdf",
        "document_type": "pdf",
        "checksum_sha256": CHECKSUM,
        "verification_status": "extracted",
        "received_at": "2026-07-14T10:00:00+03:00",
        "truncated": True,
        "included_character_count": 100,
        "original_character_count": 150,
    }
    values.update(changes)
    return AiSourceSnapshot(**values)  # type: ignore[arg-type]


def _provenance(**changes: object) -> AiAnalysisProvenance:
    values: dict[str, object] = {
        "analysis_id": "analysis_123",
        "context_fingerprint": FINGERPRINT,
        "created_at": "2026-07-14T10:01:00+03:00",
        "prompt_version": "3",
        "output_schema_version": "1",
        "persisted_schema_version": AI_ANALYSIS_SCHEMA_VERSION,
        "analyzer_version": "4",
        "context_version": "2",
        "citation_resolver_version": "1",
        "provider_id": "openai",
        "provider_model": "gpt-5",
        "provider_response_id": "resp_" + "a" * 64,
        "sources": (_source(),),
    }
    values.update(changes)
    return AiAnalysisProvenance(**values)  # type: ignore[arg-type]


def _evidence(**changes: object) -> AiEvidence:
    from app.core.ai.citations import resolve_citation
    from app.core.ai.schemas import AiDocument

    document = AiDocument(
        document_id="doc",
        name="tender.pdf",
        source="local_document_store",
        document_type="pdf",
        received_at="2026-07-14T10:00:00+03:00",
        verification_status="extracted",
        text="quote",
        checksum_sha256=CHECKSUM,
        original_character_count=5,
    )
    evidence = resolve_citation(
        document_id="doc",
        quote="quote",
        section="",
        page=None,
        confidence=0.8,
        documents=(document,),
        context_fingerprint=FINGERPRINT,
    ).evidence
    assert evidence is not None
    return replace(evidence, **changes)


def _analysis(
    *, provenance: AiAnalysisProvenance | None = None, evidence: AiEvidence | None = None
) -> AiDocumentAnalysis:
    canonical = evidence or _evidence()
    return AiDocumentAnalysis(
        "procurement:test",
        "Safe",
        risks=(AiFinding("risk", "Claim", canonical, AiFindingStatus.VERIFIED),),
        status="complete",
        provenance=provenance or _provenance(),
    )


def test_provenance_is_immutable_timezone_aware_and_contains_only_safe_sources() -> None:
    provenance = _provenance(provider_response_id="r" * 500)

    assert datetime.fromisoformat(provenance.created_at).utcoffset() is not None
    assert provenance.sources[0].display_name == "tender.pdf"
    assert provenance.provider_response_id == ""
    serialized = json.dumps(provenance.to_payload(), ensure_ascii=False)
    assert r"C:\Users\SecretUser" not in serialized
    assert "document body" not in serialized
    with pytest.raises(FrozenInstanceError):
        provenance.provider_id = "changed"  # type: ignore[misc]


def test_source_received_at_is_normalized_or_explicitly_unknown() -> None:
    assert _source(received_at="2026-07-14T10:00:00").received_at == "unknown"
    assert _source(received_at="not-a-date").received_at == "unknown"
    assert _source(received_at="").received_at == "unknown"


@pytest.mark.parametrize(
    "private_path",
    [
        r"C:\Users\SecretUser\Documents\tender.pdf",
        "C:private.txt",
        r"\\server\private\tender.pdf",
        "/home/secret/tender.pdf",
        "file:///C:/private/tender.pdf",
    ],
)
def test_source_snapshot_rejects_path_like_document_ids(private_path: str) -> None:
    with pytest.raises(ValueError):
        _source(document_id=private_path)


def test_source_snapshot_never_serializes_unsafe_type_or_status_values() -> None:
    source = _source(
        document_type=r"C:\Users\SecretUser\private",
        verification_status="extracted\nC:\\Users\\SecretUser",
    )

    assert source.document_type == "unknown"
    assert source.verification_status == "unknown"
    serialized = json.dumps(source.to_payload(), ensure_ascii=False)
    assert r"C:\Users\SecretUser" not in serialized


@pytest.mark.parametrize(
    ("field", "unsafe_value"),
    [
        ("display_name", "Authorization Bearer topsecret.txt"),
        ("display_name", "<script>topsecret</script>.pdf"),
        ("verification_status", "Traceback token=topsecret"),
        ("verification_status", "token=topsecret"),
    ],
)
def test_unsafe_source_metadata_cannot_restore_verified_findings(
    field: str,
    unsafe_value: str,
) -> None:
    payload = _analysis().to_payload()
    payload["provenance"]["sources"][0][field] = unsafe_value
    payload["source_registry"][0][field] = unsafe_value

    restored = AiDocumentAnalysis.from_payload(payload)
    serialized = json.dumps(restored.to_payload(), ensure_ascii=False).casefold()

    assert restored.provenance is None
    assert restored.risks[0].status is AiFindingStatus.UNVERIFIED
    assert restored.risks[0].evidence is None
    assert "topsecret" not in serialized
    assert "traceback" not in serialized


def test_source_snapshot_sanitizes_unsafe_source_metadata_at_construction() -> None:
    source = _source(
        display_name="Authorization Bearer topsecret.txt",
        verification_status="Traceback token=topsecret",
    )

    assert source.display_name == "unknown"
    assert source.verification_status == "unknown"
    serialized = json.dumps(source.to_payload(), ensure_ascii=False).casefold()
    assert "topsecret" not in serialized
    assert "traceback" not in serialized


def test_source_snapshot_preserves_production_safe_filename_characters() -> None:
    display_name = "TZ [rev.2] & appendices #1! client's.pdf"

    source = _source(display_name=display_name)

    assert source.display_name == display_name


def test_version_3_payload_round_trip_requires_ordered_source_registry_parity() -> None:
    analysis = _analysis()

    payload = analysis.to_payload()
    restored = AiDocumentAnalysis.from_payload(payload)

    assert payload["payload_version"] == 3
    assert payload["source_registry"] == payload["provenance"]["sources"]
    assert restored.provenance == analysis.provenance
    assert restored.risks[0].status is AiFindingStatus.VERIFIED

    payload["source_registry"] = list(reversed(payload["source_registry"])) + [
        _source(document_id="other", checksum_sha256="e" * 64).to_payload()
    ]
    damaged = AiDocumentAnalysis.from_payload(payload)
    assert damaged.provenance is None
    assert damaged.risks[0].status is AiFindingStatus.UNVERIFIED
    assert damaged.risks[0].evidence is None


def test_legacy_payload_findings_are_always_unverified() -> None:
    payload = _analysis().to_payload()
    payload["payload_version"] = 2
    payload.pop("provenance")
    payload.pop("source_registry")

    restored = AiDocumentAnalysis.from_payload(payload)

    assert restored.risks[0].status is AiFindingStatus.UNVERIFIED
    assert restored.risks[0].evidence is None


@pytest.mark.parametrize("damaged_key", ["provenance", "source_registry"])
def test_missing_version_3_provenance_or_registry_cannot_restore_verified(
    damaged_key: str,
) -> None:
    payload = _analysis().to_payload()
    payload.pop(damaged_key)

    restored = AiDocumentAnalysis.from_payload(payload)

    assert restored.provenance is None
    assert restored.risks[0].status is AiFindingStatus.UNVERIFIED
    assert restored.risks[0].evidence is None


def test_future_payload_is_incompatible_and_contains_no_findings() -> None:
    payload = _analysis().to_payload()
    payload["payload_version"] = AI_ANALYSIS_SCHEMA_VERSION + 1

    restored = AiDocumentAnalysis.from_payload(payload)

    assert restored.status == "cache_incompatible"
    assert restored.provenance is None
    assert not restored.risks


@pytest.mark.parametrize("payload_version", [3.9, "3", True, None, [], {}])
def test_non_integer_payload_versions_are_incompatible(payload_version: object) -> None:
    payload = _analysis().to_payload()
    payload["payload_version"] = payload_version

    restored = AiDocumentAnalysis.from_payload(payload)

    assert restored.status == "cache_incompatible"
    assert restored.provenance is None
    assert not restored.risks


@pytest.mark.parametrize(
    ("version_field", "tampered_value"),
    [
        ("prompt_version", "2"),
        ("output_schema_version", "999"),
        ("persisted_schema_version", 2),
        ("analyzer_version", "3"),
        ("context_version", "999"),
        ("citation_resolver_version", "999"),
    ],
)
def test_tampered_semantic_versions_cannot_restore_verified_findings(
    version_field: str,
    tampered_value: object,
) -> None:
    payload = _analysis().to_payload()
    payload["provenance"][version_field] = tampered_value
    payload["source_registry"] = payload["provenance"]["sources"]

    restored = AiDocumentAnalysis.from_payload(payload)

    assert restored.provenance is None
    assert restored.risks[0].status is AiFindingStatus.UNVERIFIED
    assert restored.risks[0].evidence is None


@pytest.mark.parametrize(
    ("field", "unsafe_value"),
    [
        ("provider_id", "Authorization: Bearer topsecret"),
        ("provider_id", r"C:\Users\SecretUser\provider"),
        ("provider_model", "model?token=topsecret"),
        ("provider_model", "https://provider.example/model"),
        ("provider_response_id", "Traceback token=topsecret"),
    ],
)
def test_unsafe_provider_provenance_cannot_restore_verified_findings(
    field: str,
    unsafe_value: str,
) -> None:
    payload = _analysis().to_payload()
    payload["provenance"][field] = unsafe_value

    restored = AiDocumentAnalysis.from_payload(payload)
    serialized = json.dumps(restored.to_payload(), ensure_ascii=False)

    assert restored.provenance is None
    assert restored.risks[0].status is AiFindingStatus.UNVERIFIED
    assert restored.risks[0].evidence is None
    assert "topsecret" not in serialized
    assert "SecretUser" not in serialized


@pytest.mark.parametrize(
    "changes",
    [
        {"prompt_version": "2"},
        {"output_schema_version": "999"},
        {"persisted_schema_version": 2},
        {"analyzer_version": "3"},
        {"context_version": "999"},
        {"citation_resolver_version": "999"},
    ],
)
def test_current_verification_rejects_non_current_semantic_versions(
    changes: dict[str, object],
) -> None:
    analysis = _analysis(provenance=_provenance(**changes))

    assert not analysis.is_current_verified(analysis.risks[0])


@pytest.mark.parametrize(
    ("provenance", "evidence"),
    [
        (_provenance(context_fingerprint="e" * 64), _evidence()),
        (_provenance(), _evidence(checksum_sha256="e" * 64)),
        (_provenance(), _evidence(citation_id="cit_" + "a" * 32)),
        (_provenance(), _evidence(source_ref="doc_" + "a" * 32)),
        (
            _provenance(sources=(_source(document_id="other"),)),
            _evidence(),
        ),
    ],
)
def test_current_verification_rejects_provenance_and_source_mismatches(
    provenance: AiAnalysisProvenance,
    evidence: AiEvidence,
) -> None:
    analysis = _analysis(provenance=provenance, evidence=evidence)

    assert not analysis.is_current_verified(analysis.risks[0])


def test_source_counts_are_non_negative_and_included_count_is_bounded() -> None:
    with pytest.raises(ValueError):
        _source(included_character_count=151)
    with pytest.raises(ValueError):
        _source(original_character_count=-1)
