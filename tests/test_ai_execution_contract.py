from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
import inspect
from pathlib import Path
import sqlite3
from threading import Event, Lock

import pytest

from app.ai.provider import AIProvider, AiProviderMetadata
from app.core.ai.analyzer import TenderDocumentAiAnalysisService, TenderDocumentAiAnalyzer
from app.core.ai.execution_contract import (
    AI_EXECUTION_CONTRACT_VERSION,
    AiExecutionContract,
    current_execution_contract,
    execution_contract_from_provenance,
    execution_contract_matches,
)
from app.core.ai.orchestrator import TenderAiOrchestrator
from app.core.ai.repository import (
    AI_ANALYZER_VERSION,
    AiDocumentAnalysisRepository,
)
from app.core.ai.schemas import (
    AI_ANALYSIS_SCHEMA_VERSION,
    AiAnalysisProvenance,
    AiAnalysisStatus,
    AiDocument,
    AiDocumentAnalysis,
    AiSourceSnapshot,
)
from app.tenders.participation_decision_service import ParticipationDecisionService


_KEY = "procurement:test"
_FINGERPRINT = "a" * 64


def _contract(
    *,
    provider_id: str = "openai",
    provider_model: str = "gpt-5",
    analyzer_version: str = "12",
) -> AiExecutionContract:
    return AiExecutionContract(
        contract_version="1",
        prompt_version="6",
        provider_output_schema_version="4",
        persisted_schema_version=10,
        analyzer_version=analyzer_version,
        context_version="6",
        citation_resolver_version="1",
        provider_id=provider_id,
        provider_model=provider_model,
    )


def _provenance(
    contract: AiExecutionContract,
    fingerprint: str = _FINGERPRINT,
    *,
    analysis_id: str = "analysis",
    created_at: str = "2026-07-15T10:00:00+00:00",
    sources: tuple[AiSourceSnapshot, ...] = (),
) -> AiAnalysisProvenance:
    return AiAnalysisProvenance(
        analysis_id=analysis_id,
        context_fingerprint=fingerprint,
        created_at=created_at,
        prompt_version=contract.prompt_version,
        output_schema_version=contract.provider_output_schema_version,
        persisted_schema_version=contract.persisted_schema_version,
        analyzer_version=contract.analyzer_version,
        context_version=contract.context_version,
        citation_resolver_version=contract.citation_resolver_version,
        provider_id=contract.provider_id,
        provider_model=contract.provider_model,
        provider_response_id="",
        sources=sources,
    )


def _analysis(
    contract: AiExecutionContract,
    *,
    summary: str,
    fingerprint: str = _FINGERPRINT,
    created_at: str = "2026-07-15T10:00:00+00:00",
    status: AiAnalysisStatus | str = AiAnalysisStatus.COMPLETE,
) -> AiDocumentAnalysis:
    return AiDocumentAnalysis(
        _KEY,
        summary,
        status=status,
        created_at=created_at,
        provenance=_provenance(contract, fingerprint, created_at=created_at),
    )


def _document() -> AiDocument:
    return AiDocument(
        "doc",
        "spec.pdf",
        "local_document_store",
        "pdf",
        "2026-07-15T00:00:00+00:00",
        "verified",
        "document text",
        "b" * 64,
    )


class _Builder:
    def __init__(self, documents: tuple[AiDocument, ...] = (_document(),)) -> None:
        self.documents = documents

    def build(self, _registry_key: str) -> tuple[AiDocument, ...]:
        return self.documents


class _MetadataProvider(AIProvider):
    def __init__(self, metadata: AiProviderMetadata) -> None:
        self.current_metadata = metadata
        self.calls = 0

    @property
    def metadata(self) -> AiProviderMetadata:
        return self.current_metadata

    def analyze(self, prompt, documents, *, output_format=None):
        del prompt, documents, output_format
        self.calls += 1
        raise AssertionError("provider call was not expected")


class _RecordingAnalyzer:
    def __init__(self, provider: _MetadataProvider) -> None:
        self.provider = provider
        self.calls = 0
        self.contracts: list[AiExecutionContract] = []
        self.entered = Event()
        self.second_entered = Event()
        self.release = Event()
        self.block = False
        self.active = 0
        self.max_active = 0
        self._state_lock = Lock()

    def analyze(
        self,
        key,
        _documents,
        *,
        context_fingerprint,
        execution_contract,
    ):
        with self._state_lock:
            self.calls += 1
            call_number = self.calls
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        self.contracts.append(execution_contract)
        self.entered.set()
        if call_number == 2:
            self.second_entered.set()
        try:
            if self.block and call_number == 1:
                assert self.release.wait(3)
            return AiDocumentAnalysis(
                key,
                "Current",
                status="complete",
                provenance=_provenance(execution_contract, context_fingerprint),
            )
        finally:
            with self._state_lock:
                self.active -= 1


def test_execution_contract_is_immutable_exact_and_built_from_sanitized_metadata() -> None:
    metadata = AiProviderMetadata(provider_id="openai", model="gpt-5")

    contract = current_execution_contract(metadata)

    assert contract == _contract()
    assert contract != replace(contract, provider_model="gpt-5-mini")
    assert AI_EXECUTION_CONTRACT_VERSION == "1"
    with pytest.raises(FrozenInstanceError):
        contract.provider_model = "changed"  # type: ignore[misc]
    assert not hasattr(contract, "base_url")
    assert not hasattr(contract, "credential")


def test_execution_contract_round_trips_current_provenance_and_rejects_incomplete() -> None:
    contract = _contract()
    provenance = _provenance(contract)

    assert execution_contract_from_provenance(provenance) == contract
    assert execution_contract_matches(provenance, contract)
    assert not execution_contract_matches(provenance, replace(contract, provider_id="ollama"))
    assert execution_contract_from_provenance(None) is None


def test_repository_finds_older_exact_provider_model_below_newer_incompatible_row(tmp_path) -> None:
    repository = AiDocumentAnalysisRepository(tmp_path / "ai.sqlite3")
    expected_contract = _contract(provider_model="gpt-A")
    incompatible_contract = _contract(provider_id="ollama", provider_model="model-B")
    repository.save(
        _analysis(
            expected_contract,
            summary="Exact older",
            created_at="2026-07-15T10:00:00+00:00",
        ),
        _FINGERPRINT,
    )
    repository.save(
        _analysis(
            incompatible_contract,
            summary="Different newer",
            created_at="2026-07-15T11:00:00+00:00",
        ),
        _FINGERPRINT,
    )

    lookup = repository.reusable(_KEY, _FINGERPRINT, expected_contract)

    assert lookup.analysis is not None
    assert lookup.analysis.summary == "Exact older"
    assert lookup.skipped_rows == 1
    assert not hasattr(repository, "last_warning")


def test_repository_returns_lookup_local_warning_without_row_or_secret_leak(tmp_path) -> None:
    repository = AiDocumentAnalysisRepository(tmp_path / "ai.sqlite3")
    contract = _contract()
    repository.save(_analysis(contract, summary="Previous"), _FINGERPRINT)
    repository.initialize()
    with sqlite3.connect(repository.path) as connection:
        connection.execute(
            """
            INSERT INTO tender_ai_document_analyses (
                analysis_id, registry_key, context_fingerprint, status,
                payload_json, created_at, payload_version
            ) VALUES ('bad', ?, ?, 'complete', ?, ?, ?)
            """,
            (
                _KEY,
                _FINGERPRINT,
                '{"SECRET":"value","duplicate":1,"duplicate":2}',
                "9999-01-01T00:00:00+00:00",
                AI_ANALYSIS_SCHEMA_VERSION,
            ),
        )

    lookup = repository.reusable(_KEY, _FINGERPRINT, contract)

    assert lookup.analysis is not None and lookup.analysis.summary == "Previous"
    assert lookup.skipped_rows == 1
    rendered = " ".join(lookup.warnings)
    assert rendered
    assert "SECRET" not in rendered
    assert "duplicate" not in rendered


def test_service_cache_identity_includes_provider_and_model_and_can_return_to_prior_contract(
    tmp_path,
) -> None:
    provider = _MetadataProvider(AiProviderMetadata(provider_id="openai", model="gpt-A"))
    analyzer = _RecordingAnalyzer(provider)
    service = TenderDocumentAiAnalysisService(
        _Builder(), analyzer, AiDocumentAnalysisRepository(tmp_path / "ai.sqlite3")
    )

    first = service.analyze(_KEY)
    reused = service.analyze(_KEY)
    provider.current_metadata = AiProviderMetadata(provider_id="ollama", model="model-B")
    changed = service.analyze(_KEY)
    provider.current_metadata = AiProviderMetadata(provider_id="openai", model="gpt-A")
    returned = service.analyze(_KEY)

    assert analyzer.calls == 2
    assert reused.to_payload() == first.to_payload()
    assert changed.provenance is not None and changed.provenance.provider_id == "ollama"
    assert returned.to_payload() == first.to_payload()


def test_no_documents_has_current_empty_provenance_is_saved_once_and_never_calls_provider(
    tmp_path,
) -> None:
    provider = _MetadataProvider(AiProviderMetadata(provider_id="openai", model="gpt-5"))
    repository = AiDocumentAnalysisRepository(tmp_path / "ai.sqlite3")
    service = TenderDocumentAiAnalysisService(
        _Builder(()), TenderDocumentAiAnalyzer(provider), repository
    )

    first = service.analyze(_KEY)
    second = service.analyze(_KEY)

    assert provider.calls == 0
    assert first.status is AiAnalysisStatus.NO_DOCUMENTS
    assert first.provenance is not None
    assert first.provenance.sources == ()
    assert first.provenance.provider_response_id == ""
    assert second.to_payload() == first.to_payload()
    with sqlite3.connect(repository.path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM tender_ai_document_analyses").fetchone()[0]
    assert count == 1


def test_result_without_exact_current_provenance_is_not_saved(tmp_path) -> None:
    provider = _MetadataProvider(AiProviderMetadata(provider_id="openai", model="gpt-5"))

    class MissingProvenanceAnalyzer(_RecordingAnalyzer):
        def analyze(self, key, _documents, *, context_fingerprint, execution_contract):
            del context_fingerprint, execution_contract
            self.calls += 1
            return AiDocumentAnalysis(key, "Safe without provenance", status="complete")

    repository = AiDocumentAnalysisRepository(tmp_path / "ai.sqlite3")
    repository.initialize()
    service = TenderDocumentAiAnalysisService(
        _Builder(), MissingProvenanceAnalyzer(provider), repository
    )

    result = service.analyze(_KEY)

    assert result.provenance is None
    with sqlite3.connect(repository.path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM tender_ai_document_analyses").fetchone()[0]
    assert count == 0


_PROVIDER_ERROR_CODES = (
    "authentication_error",
    "permission_error",
    "invalid_request",
    "endpoint_not_supported",
    "request_too_large",
    "rate_limited",
    "provider_unavailable",
    "timeout",
    "network_error",
    "tls_error",
    "redirect_rejected",
    "response_too_large",
    "invalid_json",
    "invalid_response",
    "incomplete_response",
    "refused",
    "empty_output",
    "unknown-secret-code",
)


@pytest.mark.parametrize("error_code", _PROVIDER_ERROR_CODES)
def test_provider_error_codes_map_to_fixed_safe_warning_without_retry(error_code: str) -> None:
    class ErrorProvider(AIProvider):
        calls = 0

        @property
        def metadata(self) -> AiProviderMetadata:
            return AiProviderMetadata(provider_id="openai", model="gpt-5")

        def analyze(self, prompt, documents, *, output_format=None):
            del prompt, documents, output_format
            self.calls += 1
            return {
                "status": "error",
                "error_code": error_code,
                "retryable": True,
                "message": (
                    "Authorization: Bearer SECRET https://private.example/ "
                    r"C:\Users\private\tender.txt Traceback"
                ),
            }

    provider = ErrorProvider()
    analyzer = TenderDocumentAiAnalyzer(provider)
    contract = current_execution_contract(provider.metadata)

    first = analyzer.analyze(
        _KEY,
        (_document(),),
        context_fingerprint=_FINGERPRINT,
        execution_contract=contract,
    )
    second = analyzer.analyze(
        _KEY,
        (_document(),),
        context_fingerprint=_FINGERPRINT,
        execution_contract=contract,
    )

    assert provider.calls == 2
    assert first.status is AiAnalysisStatus.PROVIDER_ERROR
    assert first.warnings == second.warnings
    assert first.warnings and max(map(len, first.warnings)) <= 240
    rendered = " ".join(first.warnings)
    for forbidden in ("SECRET", "private.example", r"C:\Users\private", "Traceback"):
        assert forbidden not in rendered


def test_two_same_key_normal_runs_share_one_provider_execution_and_cleanup_lock(tmp_path) -> None:
    provider = _MetadataProvider(AiProviderMetadata(provider_id="openai", model="gpt-5"))
    analyzer = _RecordingAnalyzer(provider)
    analyzer.block = True
    service = TenderDocumentAiAnalysisService(
        _Builder(), analyzer, AiDocumentAnalysisRepository(tmp_path / "ai.sqlite3")
    )
    orchestrator = TenderAiOrchestrator(service)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(orchestrator.run, _KEY)
        assert analyzer.entered.wait(2)
        second = pool.submit(orchestrator.run, _KEY)
        assert not analyzer.second_entered.wait(0.2)
        analyzer.release.set()
        first_result = first.result(timeout=3)
        second_result = second.result(timeout=3)

    assert analyzer.calls == 1
    assert analyzer.max_active == 1
    assert (
        first_result.document_analysis.to_payload() == second_result.document_analysis.to_payload()
    )
    assert orchestrator._execution_coordinator.active_key_count == 0


def test_same_key_run_and_recheck_do_not_overlap_and_exception_releases_lock() -> None:
    class Service:
        def __init__(self) -> None:
            self.active = 0
            self.max_active = 0
            self.calls = 0
            self.entered = Event()
            self.release = Event()
            self.lock = Lock()

        def _invoke(self, key: str) -> AiDocumentAnalysis:
            with self.lock:
                self.calls += 1
                call_number = self.calls
                self.active += 1
                self.max_active = max(self.max_active, self.active)
            try:
                self.entered.set()
                if call_number == 1:
                    assert self.release.wait(3)
                    raise RuntimeError("SECRET traceback")
                return AiDocumentAnalysis(key, "Recovered", status="complete")
            finally:
                with self.lock:
                    self.active -= 1

        def analyze(self, key: str, *, force: bool = False) -> AiDocumentAnalysis:
            del force
            return self._invoke(key)

        def recheck(self, key: str):
            self._invoke(key)
            raise RuntimeError("safe boundary exercise")

    service = Service()
    orchestrator = TenderAiOrchestrator(service)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(orchestrator.run, _KEY)
        assert service.entered.wait(2)
        second = pool.submit(orchestrator.recheck, _KEY)
        service.release.set()
        first.result(timeout=3)
        second.result(timeout=3)

    recovered = orchestrator.run(_KEY)
    assert service.max_active == 1
    assert recovered.document_analysis.summary == "Recovered"
    assert orchestrator._execution_coordinator.active_key_count == 0


def test_different_registry_keys_execute_in_parallel() -> None:
    class ParallelService:
        def __init__(self) -> None:
            self.active = 0
            self.max_active = 0
            self.both_entered = Event()
            self.lock = Lock()

        def analyze(self, key: str, *, force: bool = False) -> AiDocumentAnalysis:
            del force
            with self.lock:
                self.active += 1
                self.max_active = max(self.max_active, self.active)
                if self.active == 2:
                    self.both_entered.set()
            try:
                assert self.both_entered.wait(2)
                return AiDocumentAnalysis(key, "Parallel", status="complete")
            finally:
                with self.lock:
                    self.active -= 1

    service = ParallelService()
    orchestrator = TenderAiOrchestrator(service)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(orchestrator.run, "procurement:first")
        second = pool.submit(orchestrator.run, "procurement:second")
        first.result(timeout=3)
        second.result(timeout=3)

    assert service.max_active == 2
    assert orchestrator._execution_coordinator.active_key_count == 0


def test_participation_decision_requires_explicit_current_ai_and_runtime_has_no_repository_fallback() -> (
    None
):
    constructor = inspect.signature(ParticipationDecisionService.__init__)
    evaluate = inspect.signature(ParticipationDecisionService.evaluate)
    decision_source = Path("app/tenders/participation_decision_service.py").read_text(
        encoding="utf-8"
    )
    runtime_source = Path("app/tenders/search_runtime.py").read_text(encoding="utf-8")

    assert "ai_analysis_repository" not in constructor.parameters
    assert evaluate.parameters["ai_document_analysis"].default is None
    assert "_USE_LATEST_AI_ANALYSIS" not in decision_source
    assert "ai_analysis_repository.latest" not in decision_source
    assert "ai_analysis_repository=" not in runtime_source


def test_rm125_preserves_architecture_versions_database_and_deterministic_policy() -> None:
    analyzer_source = Path("app/core/ai/analyzer.py").read_text(encoding="utf-8")
    full_analysis_source = Path("app/tenders/full_analysis.py").read_text(encoding="utf-8")
    runtime_source = Path("app/tenders/search_runtime.py").read_text(encoding="utf-8")
    orchestrator_source = Path("app/core/ai/orchestrator.py").read_text(encoding="utf-8")

    assert analyzer_source.count("self.provider.analyze(") == 1
    assert full_analysis_source.count('RUNNING_AI = "running_ai"') == 1
    assert full_analysis_source.count("FullAnalysisStage.RUNNING_AI") == 1
    assert runtime_source.count("TenderAiOrchestrator(ai_document_analysis_service)") == 1
    assert runtime_source.count("AiDocumentAnalysisRepository(") == 1
    assert "sleep(" not in orchestrator_source
    assert "retry" not in orchestrator_source.casefold()
    assert AI_ANALYZER_VERSION == "12"
    assert AI_ANALYSIS_SCHEMA_VERSION == 10
    assert (
        datetime.fromisoformat(datetime.now(timezone.utc).isoformat(timespec="seconds")).tzinfo
        is not None
    )

    policy_source = Path("app/tenders/participation_decision_policy.py").read_text(encoding="utf-8")
    score_source = Path("app/tenders/collector/participation_score.py").read_text(encoding="utf-8")
    for source in (policy_source, score_source):
        assert "AiExecutionContract" not in source
        assert "ai_recheck" not in source
