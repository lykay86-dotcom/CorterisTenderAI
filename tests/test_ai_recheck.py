from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime
import hashlib
import json

import pytest

from app.core.ai.recheck import (
    AI_RECHECK_DISCLAIMER,
    AI_RECHECK_POLICY_VERSION,
    AiRecheckAssessment,
    AiRecheckChangeType,
    AiRecheckStatus,
    TenderAiRecheckResult,
    compare_ai_analyses,
)
from app.core.ai.schemas import (
    AI_ANALYSIS_SCHEMA_VERSION,
    AiAnalysisProvenance,
    AiDocumentAnalysis,
    AiEvidence,
    AiEvidenceVerificationMethod,
    AiFinding,
    AiFindingStatus,
    AiSourceSnapshot,
)


FINGERPRINT = "d" * 64


def _provenance(
    *,
    analysis_id: str = "analysis_baseline",
    created_at: str = "2026-07-15T10:00:00+00:00",
    response_id: str = "resp_" + "a" * 64,
    fingerprint: str = FINGERPRINT,
    provider_id: str = "openai",
    provider_model: str = "gpt-5",
    prompt_version: str = "6",
) -> AiAnalysisProvenance:
    sources = tuple(
        AiSourceSnapshot(
            document_id=f"doc-{suffix}",
            display_name=f"tender-{suffix}.pdf",
            document_type="pdf",
            checksum_sha256="b" * 64,
            verification_status="verified",
            received_at="2026-07-15T09:00:00+00:00",
            truncated=False,
            included_character_count=17,
            original_character_count=17,
        )
        for suffix in "abcd"
    )
    return AiAnalysisProvenance(
        analysis_id=analysis_id,
        context_fingerprint=fingerprint,
        created_at=created_at,
        prompt_version=prompt_version,
        output_schema_version="4",
        persisted_schema_version=AI_ANALYSIS_SCHEMA_VERSION,
        analyzer_version="11",
        context_version="6",
        citation_resolver_version="1",
        provider_id=provider_id,
        provider_model=provider_model,
        provider_response_id=response_id,
        sources=sources,
    )


def _evidence(citation_hex: str) -> AiEvidence:
    quote = "exact local quote"
    document_id = f"doc-{citation_hex}"
    source_digest = hashlib.sha256(document_id.encode("utf-8")).hexdigest()[:32]
    canonical = json.dumps(
        {
            "character_end": len(quote),
            "character_start": 0,
            "checksum_sha256": "b" * 64,
            "context_fingerprint": FINGERPRINT,
            "document_id": document_id,
            "quote": quote,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    citation_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]
    return AiEvidence(
        citation_id=f"cit_{citation_digest}",
        document_id=document_id,
        quote=quote,
        character_start=0,
        character_end=len(quote),
        section="",
        page=None,
        confidence=0.8,
        verification_method=AiEvidenceVerificationMethod.EXACT_QUOTE,
        checksum_sha256="b" * 64,
        source_ref=f"doc_{source_digest}",
        context_fingerprint=FINGERPRINT,
    )


def _finding(
    citation_hex: str,
    statement: str,
    *,
    status: AiFindingStatus = AiFindingStatus.VERIFIED,
) -> AiFinding:
    return AiFinding(
        category="risk",
        statement=statement,
        evidence=_evidence(citation_hex),
        status=status,
    )


def _analysis(
    *,
    summary: str = "Stable summary",
    final: str = "Stable conclusion",
    missing: tuple[str, ...] = ("estimate",),
    risks: tuple[AiFinding, ...] = (),
    status: str = "complete",
    provenance: AiAnalysisProvenance | None = None,
    warnings: tuple[str, ...] = (),
) -> AiDocumentAnalysis:
    return AiDocumentAnalysis(
        "procurement:test",
        summary,
        risks=risks,
        missing_documents=missing,
        final_ai_conclusion=final,
        status=status,
        provenance=provenance or _provenance(),
        warnings=warnings,
    )


def test_contract_is_immutable_and_uses_exact_public_values() -> None:
    assert AI_RECHECK_POLICY_VERSION == "1"
    assert [item.value for item in AiRecheckStatus] == [
        "consistent",
        "changed",
        "baseline_missing",
        "current_unavailable",
        "not_comparable",
    ]
    assert [item.value for item in AiRecheckChangeType] == ["added", "removed", "modified"]
    assert AI_RECHECK_DISCLAIMER == (
        "Повторная проверка оценивает воспроизводимость AI-анализа при одинаковом локальном "
        "контексте. Совпадение результатов не подтверждает фактическую, юридическую или "
        "коммерческую правильность выводов."
    )

    assessment = compare_ai_analyses(_analysis(), _analysis())
    with pytest.raises(FrozenInstanceError):
        assessment.status = AiRecheckStatus.CHANGED  # type: ignore[misc]


def test_consistent_ignores_technical_provenance_and_repository_warnings() -> None:
    baseline = _analysis(
        risks=(_finding("a", "Same verified statement"),),
        warnings=("Старая repository warning",),
    )
    current = replace(
        baseline,
        created_at="2026-07-15T11:00:00+00:00",
        warnings=("Новая repository warning",),
        provenance=_provenance(
            analysis_id="analysis_current",
            created_at="2026-07-15T11:00:00+00:00",
            response_id="resp_" + "f" * 64,
        ),
    )

    result = compare_ai_analyses(baseline, current)

    assert result.status is AiRecheckStatus.CONSISTENT
    assert result.baseline_digest == result.current_digest
    assert result.unchanged_count == 1
    assert result.added_count == result.removed_count == result.modified_count == 0
    assert result.deltas == ()
    assert result.baseline_analysis_id == "analysis_baseline"
    assert result.current_analysis_id == "analysis_current"


def test_changed_explains_exact_key_deltas_and_root_text_flags() -> None:
    baseline = _analysis(
        risks=(
            _finding("a", "Will be modified"),
            _finding("b", "Will be removed"),
            _finding("d", "Will stay"),
        )
    )
    current = _analysis(
        summary="Changed summary",
        final="Changed conclusion",
        missing=("license",),
        risks=(
            _finding("c", "Was added"),
            _finding("a", "Modified statement"),
            _finding("d", "Will stay"),
        ),
        provenance=_provenance(analysis_id="analysis_current"),
    )

    result = compare_ai_analyses(baseline, current)

    assert result.status is AiRecheckStatus.CHANGED
    assert result.summary_changed is True
    assert result.final_conclusion_changed is True
    assert result.missing_documents_changed is True
    assert (
        result.unchanged_count,
        result.added_count,
        result.removed_count,
        result.modified_count,
    ) == (
        1,
        1,
        1,
        1,
    )
    assert {(item.change_type.value, item.citation_id) for item in result.deltas} == {
        ("modified", _evidence("a").citation_id),
        ("removed", _evidence("b").citation_id),
        ("added", _evidence("c").citation_id),
    }
    modified = next(
        item for item in result.deltas if item.change_type is AiRecheckChangeType.MODIFIED
    )
    assert modified.previous_statement == "Will be modified"
    assert modified.current_statement == "Modified statement"


def test_unverified_findings_are_never_promoted_or_compared() -> None:
    baseline = _analysis(risks=(_finding("a", "Old", status=AiFindingStatus.UNVERIFIED),))
    current = _analysis(risks=(_finding("b", "New", status=AiFindingStatus.UNVERIFIED),))

    result = compare_ai_analyses(baseline, current)

    assert result.status is AiRecheckStatus.CONSISTENT
    assert result.unchanged_count == 0
    assert result.deltas == ()


def test_order_does_not_change_digest_or_delta_order() -> None:
    first = _analysis(risks=(_finding("b", "B"), _finding("a", "A")))
    second = _analysis(risks=(_finding("a", "A"), _finding("b", "B")))

    result = compare_ai_analyses(first, second)

    assert result.status is AiRecheckStatus.CONSISTENT
    assert result.baseline_digest == result.current_digest
    assert result.unchanged_count == 2


def test_missing_baseline_and_current_failure_have_distinct_statuses() -> None:
    missing = compare_ai_analyses(None, _analysis())
    unavailable = compare_ai_analyses(
        _analysis(),
        _analysis(status="provider_error", provenance=None),
    )

    assert missing.status is AiRecheckStatus.BASELINE_MISSING
    assert unavailable.status is AiRecheckStatus.CURRENT_UNAVAILABLE
    assert unavailable.current_digest == ""
    assert unavailable.deltas == ()


@pytest.mark.parametrize(
    "current",
    [
        _analysis(provenance=_provenance(fingerprint="e" * 64)),
        _analysis(provenance=_provenance(provider_id="ollama")),
        _analysis(provenance=_provenance(provider_model="other-model")),
        _analysis(provenance=_provenance(prompt_version="7")),
    ],
)
def test_mismatched_context_provider_model_or_versions_is_not_comparable(
    current: AiDocumentAnalysis,
) -> None:
    result = compare_ai_analyses(_analysis(), current)

    assert result.status is AiRecheckStatus.NOT_COMPARABLE
    assert result.deltas == ()
    assert result.warnings


def test_safe_application_envelope_has_no_decision_or_baseline_payload() -> None:
    assessment = compare_ai_analyses(_analysis(), _analysis())
    result = TenderAiRecheckResult(
        registry_key="procurement:test",
        current_analysis=_analysis(),
        assessment=assessment,
        started_at="2026-07-15T10:00:00+00:00",
        completed_at="2026-07-15T10:00:01+00:00",
        warnings=(),
    )

    assert datetime.fromisoformat(result.started_at).tzinfo is not None
    assert not hasattr(result, "baseline_analysis")
    assert not hasattr(result, "score")
    assert not hasattr(result, "recommendation")
    assert isinstance(result.assessment, AiRecheckAssessment)
