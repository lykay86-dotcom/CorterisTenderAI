from __future__ import annotations

from datetime import datetime

import pytest

from app.core.ai.orchestrator import TenderAiOrchestrator
from app.core.ai.recheck import AiRecheckStatus, TenderAiRecheckResult, compare_ai_analyses
from app.core.ai.schemas import (
    AiDocumentAnalysis,
    AiEvidence,
    AiEvidenceVerificationMethod,
    AiFinding,
    AiFindingStatus,
)


def _verified_evidence(quote: str, confidence: float) -> AiEvidence:
    return AiEvidence(
        citation_id="cit_" + "a" * 32,
        document_id="doc",
        quote=quote,
        character_start=0,
        character_end=len(quote),
        section="",
        page=None,
        confidence=confidence,
        verification_method=AiEvidenceVerificationMethod.EXACT_QUOTE,
        checksum_sha256="b" * 64,
        source_ref="doc_" + "c" * 32,
        context_fingerprint="d" * 64,
    )


class RecordingService:
    def __init__(self, result: AiDocumentAnalysis) -> None:
        self.result = result
        self.calls: list[tuple[str, bool]] = []

    def analyze(self, registry_key: str, *, force: bool = False) -> AiDocumentAnalysis:
        self.calls.append((registry_key, force))
        return self.result


class ExplodingService:
    def analyze(self, _registry_key: str, *, force: bool = False) -> AiDocumentAnalysis:
        del force
        raise TimeoutError(
            "Authorization: Bearer SECRET\n"
            "Traceback (most recent call last)\n"
            r"C:\Users\private\tender.txt"
        )

    def recheck(self, _registry_key: str) -> TenderAiRecheckResult:
        raise TimeoutError(
            "Authorization: Bearer SECRET\n"
            "Traceback (most recent call last)\n"
            r"C:\Users\private\tender.txt"
        )


def _analysis(status: str = "complete", *, warnings: tuple[str, ...] = ()):
    return AiDocumentAnalysis(
        "procurement:test",
        "Safe current result",
        status=status,
        warnings=warnings,
    )


def test_successful_task_service_is_called_once_and_result_is_unchanged() -> None:
    current = _analysis()
    service = RecordingService(current)

    result = TenderAiOrchestrator(service).run("  procurement:test  ")

    assert service.calls == [("procurement:test", False)]
    assert result.document_analysis is current
    assert result.warnings == ()
    assert result.degraded is False


def test_force_is_forwarded_without_changing_semantics() -> None:
    service = RecordingService(_analysis())

    TenderAiOrchestrator(service).run("procurement:test", force=True)

    assert service.calls == [("procurement:test", True)]


@pytest.mark.parametrize("registry_key", ["", " ", "\t\n"])
def test_empty_registry_key_is_rejected(registry_key: str) -> None:
    with pytest.raises(ValueError, match="registry_key"):
        TenderAiOrchestrator(RecordingService(_analysis())).run(registry_key)


@pytest.mark.parametrize(
    "status",
    [
        "partial",
        "provider_disabled",
        "provider_error",
        "invalid_response",
        "cache_incompatible",
        "no_documents",
    ],
)
def test_safe_non_complete_statuses_do_not_raise_and_are_degraded(status: str) -> None:
    result = TenderAiOrchestrator(RecordingService(_analysis(status))).run("procurement:test")

    assert result.document_analysis.status == status
    assert result.degraded is True
    assert result.warnings


def test_partial_warnings_are_preserved_and_deduplicated_in_order() -> None:
    result = TenderAiOrchestrator(
        RecordingService(_analysis("partial", warnings=("Repeated", "Repeated", "Second")))
    ).run("procurement:test")

    assert result.warnings == ("AI-анализ выполнен частично.", "Repeated", "Second")


def test_invalid_response_does_not_create_findings() -> None:
    result = TenderAiOrchestrator(RecordingService(_analysis("invalid_response"))).run(
        "procurement:test"
    )

    analysis = result.document_analysis
    assert analysis.risks == ()
    assert analysis.suspicious_conditions == ()
    assert analysis.contradictions == ()


def test_unexpected_exception_becomes_safe_current_provider_error() -> None:
    result = TenderAiOrchestrator(ExplodingService()).run("procurement:test")
    rendered = " ".join((result.document_analysis.summary, *result.warnings))

    assert result.document_analysis.status == "provider_error"
    assert result.document_analysis.registry_key == "procurement:test"
    assert "SECRET" not in rendered
    assert "Traceback" not in rendered
    assert r"C:\Users\private" not in rendered


def test_timestamps_are_timezone_aware_iso_8601() -> None:
    result = TenderAiOrchestrator(RecordingService(_analysis())).run("procurement:test")

    started = datetime.fromisoformat(result.started_at)
    completed = datetime.fromisoformat(result.completed_at)
    assert started.tzinfo is not None
    assert completed.tzinfo is not None
    assert completed >= started


def test_current_failure_is_returned_instead_of_stale_result() -> None:
    current = _analysis("provider_error")
    service = RecordingService(current)
    service.repository = object()  # Orchestrator must not inspect a repository.

    result = TenderAiOrchestrator(service).run("procurement:test")

    assert result.document_analysis is current
    assert service.calls == [("procurement:test", False)]


def test_orchestrator_does_not_change_findings_or_create_decision_fields() -> None:
    finding = AiFinding(
        "risk",
        "Verified statement",
        _verified_evidence("exact quote", 0.9),
        AiFindingStatus.VERIFIED,
    )
    current = AiDocumentAnalysis(
        "procurement:test",
        "Safe current result",
        risks=(finding,),
        status="complete",
    )

    result = TenderAiOrchestrator(RecordingService(current)).run("procurement:test")

    assert result.document_analysis.risks is current.risks
    assert result.document_analysis.risks[0] is finding
    assert not hasattr(result, "score")
    assert not hasattr(result, "recommendation")


def test_recheck_is_delegated_once_without_repository_access() -> None:
    current = _analysis("provider_error")
    expected = TenderAiRecheckResult(
        registry_key="procurement:test",
        current_analysis=current,
        assessment=compare_ai_analyses(None, current),
        started_at="2026-07-15T10:00:00+00:00",
        completed_at="2026-07-15T10:00:01+00:00",
        warnings=(),
    )

    class Service(RecordingService):
        repository = object()
        recheck_calls: list[str] = []

        def recheck(self, registry_key: str) -> TenderAiRecheckResult:
            self.recheck_calls.append(registry_key)
            return expected

    service = Service(current)

    result = TenderAiOrchestrator(service).recheck("  procurement:test  ")

    assert result is expected
    assert service.recheck_calls == ["procurement:test"]
    assert service.calls == []


def test_recheck_unexpected_exception_is_safe_current_unavailable() -> None:
    result = TenderAiOrchestrator(ExplodingService()).recheck("procurement:test")
    rendered = " ".join(
        (
            result.current_analysis.summary,
            *result.current_analysis.warnings,
            *result.assessment.warnings,
            *result.warnings,
        )
    )

    assert result.assessment.status is AiRecheckStatus.CURRENT_UNAVAILABLE
    assert result.current_analysis.status == "provider_error"
    assert "SECRET" not in rendered
    assert "Traceback" not in rendered
    assert r"C:\Users\private" not in rendered
