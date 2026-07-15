"""Pure, deterministic comparison of two AI analyses for the same local context."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json

from app.core.ai.execution_contract import (
    execution_contract_from_provenance,
    execution_contract_matches,
)
from app.core.ai.schemas import AiAnalysisStatus, AiDocumentAnalysis, AiFinding


AI_RECHECK_POLICY_VERSION = "1"
AI_RECHECK_DISCLAIMER = (
    "Повторная проверка оценивает воспроизводимость AI-анализа при одинаковом локальном "
    "контексте. Совпадение результатов не подтверждает фактическую, юридическую или "
    "коммерческую правильность выводов."
)

_COMPARABLE_STATUSES = frozenset({AiAnalysisStatus.COMPLETE, AiAnalysisStatus.PARTIAL})
_TECHNICAL_FIELDS = frozenset({"status", "document_ids", "included_document_ids", "warnings"})


class AiRecheckStatus(StrEnum):
    CONSISTENT = "consistent"
    CHANGED = "changed"
    BASELINE_MISSING = "baseline_missing"
    CURRENT_UNAVAILABLE = "current_unavailable"
    NOT_COMPARABLE = "not_comparable"


class AiRecheckChangeType(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


@dataclass(frozen=True, slots=True)
class AiRecheckDelta:
    change_type: AiRecheckChangeType
    scope: str
    category: str
    citation_id: str
    previous_statement: str = ""
    current_statement: str = ""

    def to_payload(self) -> dict[str, str]:
        return {
            "change_type": self.change_type.value,
            "scope": self.scope,
            "category": self.category,
            "citation_id": self.citation_id,
            "previous_statement": self.previous_statement,
            "current_statement": self.current_statement,
        }


@dataclass(frozen=True, slots=True)
class AiRecheckAssessment:
    policy_version: str
    status: AiRecheckStatus
    registry_key: str
    context_fingerprint: str = ""
    baseline_analysis_id: str = ""
    baseline_created_at: str = ""
    current_analysis_id: str = ""
    current_created_at: str = ""
    provider_id: str = ""
    provider_model: str = ""
    baseline_digest: str = ""
    current_digest: str = ""
    unchanged_count: int = 0
    added_count: int = 0
    removed_count: int = 0
    modified_count: int = 0
    summary_changed: bool = False
    final_conclusion_changed: bool = False
    missing_documents_changed: bool = False
    deltas: tuple[AiRecheckDelta, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        return {
            "policy_version": self.policy_version,
            "status": self.status.value,
            "registry_key": self.registry_key,
            "context_fingerprint": self.context_fingerprint,
            "baseline_analysis_id": self.baseline_analysis_id,
            "baseline_created_at": self.baseline_created_at,
            "current_analysis_id": self.current_analysis_id,
            "current_created_at": self.current_created_at,
            "provider_id": self.provider_id,
            "provider_model": self.provider_model,
            "baseline_digest": self.baseline_digest,
            "current_digest": self.current_digest,
            "unchanged_count": self.unchanged_count,
            "added_count": self.added_count,
            "removed_count": self.removed_count,
            "modified_count": self.modified_count,
            "summary_changed": self.summary_changed,
            "final_conclusion_changed": self.final_conclusion_changed,
            "missing_documents_changed": self.missing_documents_changed,
            "deltas": [item.to_payload() for item in self.deltas],
            "warnings": list(self.warnings),
            "disclaimer": AI_RECHECK_DISCLAIMER,
        }


@dataclass(frozen=True, slots=True)
class TenderAiRecheckResult:
    registry_key: str
    current_analysis: AiDocumentAnalysis
    assessment: AiRecheckAssessment
    started_at: str
    completed_at: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _ComparableFinding:
    scope: str
    category: str
    citation_id: str
    statement: str

    @property
    def key(self) -> tuple[str, str, str]:
        return self.scope, self.category, self.citation_id

    def to_payload(self) -> dict[str, str]:
        return {
            "scope": self.scope,
            "category": self.category,
            "citation_id": self.citation_id,
            "statement": self.statement,
        }


def compare_ai_analyses(
    baseline: AiDocumentAnalysis | None,
    current: AiDocumentAnalysis,
) -> AiRecheckAssessment:
    """Compare analyses without I/O, heuristic matching or decision side effects."""

    current_provenance = current.provenance
    common = {
        "policy_version": AI_RECHECK_POLICY_VERSION,
        "registry_key": current.registry_key,
        "context_fingerprint": (
            current_provenance.context_fingerprint if current_provenance is not None else ""
        ),
        "current_analysis_id": (
            current_provenance.analysis_id if current_provenance is not None else ""
        ),
        "current_created_at": (
            current_provenance.created_at if current_provenance is not None else current.created_at
        ),
        "provider_id": current_provenance.provider_id if current_provenance is not None else "",
        "provider_model": (
            current_provenance.provider_model if current_provenance is not None else ""
        ),
    }
    if current.status not in _COMPARABLE_STATUSES or current_provenance is None:
        return AiRecheckAssessment(
            status=AiRecheckStatus.CURRENT_UNAVAILABLE,
            warnings=("Текущий AI-анализ недоступен для повторного сравнения.",),
            **common,
        )

    current_findings = _comparable_findings(current)
    current_digest = _semantic_digest(current, current_findings)
    if baseline is None:
        return AiRecheckAssessment(
            status=AiRecheckStatus.BASELINE_MISSING,
            current_digest=current_digest,
            warnings=("Сопоставимый предыдущий AI-анализ не найден.",),
            **common,
        )

    baseline_provenance = baseline.provenance
    baseline_metadata = {
        "baseline_analysis_id": (
            baseline_provenance.analysis_id if baseline_provenance is not None else ""
        ),
        "baseline_created_at": (
            baseline_provenance.created_at
            if baseline_provenance is not None
            else baseline.created_at
        ),
    }
    if (
        baseline.status not in _COMPARABLE_STATUSES
        or baseline_provenance is None
        or not _same_comparison_contract(baseline, current)
    ):
        return AiRecheckAssessment(
            status=AiRecheckStatus.NOT_COMPARABLE,
            current_digest=current_digest,
            warnings=("AI-анализы имеют несовместимый контекст или контракт выполнения.",),
            **baseline_metadata,
            **common,
        )

    baseline_findings = _comparable_findings(baseline)
    baseline_digest = _semantic_digest(baseline, baseline_findings)
    unchanged, deltas = _compare_findings(baseline_findings, current_findings)
    summary_changed = baseline.summary != current.summary
    final_changed = baseline.final_ai_conclusion != current.final_ai_conclusion
    missing_changed = _canonical_strings(baseline.missing_documents) != _canonical_strings(
        current.missing_documents
    )
    changed = (
        baseline_digest != current_digest
        or bool(deltas)
        or summary_changed
        or final_changed
        or missing_changed
    )
    return AiRecheckAssessment(
        status=AiRecheckStatus.CHANGED if changed else AiRecheckStatus.CONSISTENT,
        baseline_digest=baseline_digest,
        current_digest=current_digest,
        unchanged_count=unchanged,
        added_count=sum(item.change_type is AiRecheckChangeType.ADDED for item in deltas),
        removed_count=sum(item.change_type is AiRecheckChangeType.REMOVED for item in deltas),
        modified_count=sum(item.change_type is AiRecheckChangeType.MODIFIED for item in deltas),
        summary_changed=summary_changed,
        final_conclusion_changed=final_changed,
        missing_documents_changed=missing_changed,
        deltas=deltas,
        **baseline_metadata,
        **common,
    )


def _same_comparison_contract(
    baseline: AiDocumentAnalysis,
    current: AiDocumentAnalysis,
) -> bool:
    left = baseline.provenance
    right = current.provenance
    if left is None or right is None:
        return False
    expected_contract = execution_contract_from_provenance(right)
    return (
        expected_contract is not None
        and baseline.registry_key == current.registry_key
        and left.context_fingerprint == right.context_fingerprint
        and execution_contract_matches(left, expected_contract)
    )


def _comparable_findings(analysis: AiDocumentAnalysis) -> tuple[_ComparableFinding, ...]:
    collections: list[tuple[str, tuple[AiFinding, ...]]] = [
        ("risks", analysis.risks),
        ("suspicious_conditions", analysis.suspicious_conditions),
        ("contradictions", analysis.contradictions),
    ]
    for scope, section in (
        ("requirements", analysis.requirements),
        ("technical_specification", analysis.technical_specification),
        ("draft_contract", analysis.draft_contract),
    ):
        for name in section.__dataclass_fields__:
            if name in _TECHNICAL_FIELDS:
                continue
            value = getattr(section, name)
            if isinstance(value, tuple) and all(isinstance(item, AiFinding) for item in value):
                collections.append((f"{scope}.{name}", value))

    result: list[_ComparableFinding] = []
    for scope, findings in collections:
        for finding in findings:
            if not analysis.is_current_verified(finding) or finding.evidence is None:
                continue
            result.append(
                _ComparableFinding(
                    scope=scope,
                    category=finding.category,
                    citation_id=finding.evidence.citation_id,
                    statement=finding.statement,
                )
            )
    return tuple(sorted(result, key=lambda item: (*item.key, item.statement)))


def _compare_findings(
    baseline: tuple[_ComparableFinding, ...],
    current: tuple[_ComparableFinding, ...],
) -> tuple[int, tuple[AiRecheckDelta, ...]]:
    baseline_groups = _group_findings(baseline)
    current_groups = _group_findings(current)
    unchanged = 0
    deltas: list[AiRecheckDelta] = []
    for key in sorted(set(baseline_groups) | set(current_groups)):
        previous = baseline_groups.get(key, ())
        present = current_groups.get(key, ())
        if len(previous) == len(present) == 1:
            if previous[0].statement == present[0].statement:
                unchanged += 1
            else:
                deltas.append(_delta(AiRecheckChangeType.MODIFIED, previous[0], present[0]))
            continue
        for item in previous:
            deltas.append(_delta(AiRecheckChangeType.REMOVED, item, None))
        for item in present:
            deltas.append(_delta(AiRecheckChangeType.ADDED, None, item))
    return unchanged, tuple(deltas)


def _group_findings(
    findings: tuple[_ComparableFinding, ...],
) -> dict[tuple[str, str, str], tuple[_ComparableFinding, ...]]:
    grouped: dict[tuple[str, str, str], list[_ComparableFinding]] = {}
    for item in findings:
        grouped.setdefault(item.key, []).append(item)
    return {key: tuple(values) for key, values in grouped.items()}


def _delta(
    change_type: AiRecheckChangeType,
    previous: _ComparableFinding | None,
    current: _ComparableFinding | None,
) -> AiRecheckDelta:
    identity = previous or current
    assert identity is not None
    return AiRecheckDelta(
        change_type=change_type,
        scope=identity.scope,
        category=identity.category,
        citation_id=identity.citation_id,
        previous_statement=previous.statement if previous is not None else "",
        current_statement=current.statement if current is not None else "",
    )


def _semantic_digest(
    analysis: AiDocumentAnalysis,
    findings: tuple[_ComparableFinding, ...],
) -> str:
    statuses = {
        "analysis": analysis.status.value,
        "requirements": analysis.requirements.status.value,
        "technical_specification": analysis.technical_specification.status.value,
        "draft_contract": analysis.draft_contract.status.value,
        "documentation_completeness": analysis.documentation_completeness_assessment.status.value,
        "legal_risk": analysis.legal_risk_assessment.status.value,
        "financial_risk": analysis.financial_risk_assessment.status.value,
        "competition": analysis.competition_assessment.status.value,
    }
    payload = {
        "summary": analysis.summary,
        "final_ai_conclusion": analysis.final_ai_conclusion,
        "missing_documents": _canonical_strings(analysis.missing_documents),
        "statuses": statuses,
        "findings": [item.to_payload() for item in findings],
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _canonical_strings(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(set(values), key=lambda value: (value.casefold(), value)))


__all__ = [
    "AI_RECHECK_DISCLAIMER",
    "AI_RECHECK_POLICY_VERSION",
    "AiRecheckAssessment",
    "AiRecheckChangeType",
    "AiRecheckDelta",
    "AiRecheckStatus",
    "TenderAiRecheckResult",
    "compare_ai_analyses",
]
