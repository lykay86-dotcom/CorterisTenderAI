from __future__ import annotations

from collections.abc import Mapping

import json
from dataclasses import dataclass
from pathlib import Path

from app.ai.provider import AIProvider, DisabledProvider, OpenAICompatibleProvider
from app.bootstrap import _create_ai_runtime
from app.core.ai.output_schema import build_responses_text_format
from app.core.ai.provider_selection import AiProviderId, OLLAMA_DEFAULT_BASE_URL
from app.core.ai.schemas import (
    AiDocument,
    AiDraftContractAnalysis,
    AiTechnicalSpecificationAnalysis,
    _APPLICATION_REQUIREMENTS_FINDING_FIELDS,
)
from app.core.config_manager import ConfigManager
from app.tenders.search_runtime import create_tender_search_runtime


class RecordingProvider(AIProvider):
    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail
        self.output_format: Mapping[str, object] | None = None

    def analyze(
        self,
        prompt: str,
        documents: list[str],
        *,
        output_format: Mapping[str, object] | None = None,
    ) -> dict:
        self.calls += 1
        self.output_format = output_format
        assert prompt
        assert documents
        if self.fail:
            raise TimeoutError("Authorization: Bearer do-not-leak")
        return {
            "status": "ok",
            "text": json.dumps(
                {
                    "summary": "Safe summary",
                    "requirements": {name: [] for name in _APPLICATION_REQUIREMENTS_FINDING_FIELDS},
                    "technical_specification": {
                        name: []
                        for name in AiTechnicalSpecificationAnalysis.__dataclass_fields__
                        if name
                        not in {
                            "status",
                            "document_ids",
                            "included_document_ids",
                            "warnings",
                        }
                    },
                    "draft_contract": {
                        name: []
                        for name in AiDraftContractAnalysis.__dataclass_fields__
                        if name
                        not in {
                            "status",
                            "document_ids",
                            "included_document_ids",
                            "warnings",
                        }
                    },
                    "risks": [],
                    "suspicious_conditions": [],
                    "contradictions": [],
                    "missing_documents": [],
                    "final_ai_conclusion": "Safe conclusion",
                }
            ),
        }


class Builder:
    fingerprint_parameters: dict[str, object] = {}

    def build(self, _registry_key: str) -> tuple[AiDocument, ...]:
        return (
            AiDocument(
                "doc-1",
                "specification.txt",
                "eis",
                "txt",
                "2026-07-13T00:00:00+00:00",
                "verified",
                "Tender requirement text",
                "a" * 64,
            ),
        )


@dataclass
class SecretStore:
    value: str | None = None
    loads: int = 0
    fail_on_load: bool = False

    def load(self, _name: str) -> str | None:
        self.loads += 1
        if self.fail_on_load:
            raise AssertionError("host keyring must not be read")
        return self.value

    def save(self, _name: str, value: str) -> None:
        self.value = value

    def delete(self, _name: str) -> None:
        self.value = None


def test_default_runtime_uses_disabled_without_host_keyring(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.security.secrets.load_secret",
        lambda _name: (_ for _ in ()).throw(AssertionError("host keyring read")),
    )

    runtime = create_tender_search_runtime(tmp_path)

    assert runtime.ai_orchestrator is not None
    provider = runtime.ai_orchestrator.document_analysis_service.analyzer.provider
    assert isinstance(provider, DisabledProvider)


def test_injected_provider_runs_once_through_existing_orchestrator(tmp_path) -> None:
    provider = RecordingProvider()
    runtime = create_tender_search_runtime(tmp_path, ai_provider=provider)
    assert runtime.ai_orchestrator is not None
    runtime.ai_orchestrator.document_analysis_service.context_builder = Builder()  # type: ignore[assignment]

    result = runtime.ai_orchestrator.run("procurement:test", force=True)

    assert provider.calls == 1
    assert provider.output_format == build_responses_text_format()
    assert result.document_analysis.status == "complete"
    assert runtime.ai_orchestrator.document_analysis_service.analyzer.provider is provider


def test_provider_exception_stays_current_and_safe(tmp_path) -> None:
    provider = RecordingProvider(fail=True)
    runtime = create_tender_search_runtime(tmp_path, ai_provider=provider)
    assert runtime.ai_orchestrator is not None
    runtime.ai_orchestrator.document_analysis_service.context_builder = Builder()  # type: ignore[assignment]

    result = runtime.ai_orchestrator.run("procurement:test", force=True)

    assert provider.calls == 1
    assert result.document_analysis.status == "provider_error"
    assert "do-not-leak" not in repr(result)


def test_bootstrap_disabled_does_not_read_secret_store(tmp_path) -> None:
    config = ConfigManager(tmp_path / "settings.json")
    secret = SecretStore(fail_on_load=True)

    service, runtime, resolution = _create_ai_runtime(
        tmp_path / "data",
        config,
        secret_store=secret,
    )

    assert service is not None
    assert secret.loads == 0
    assert resolution.effective_provider_id is AiProviderId.DISABLED
    assert runtime.ai_orchestrator is not None


def test_bootstrap_ollama_does_not_read_keyring_or_execute_http(tmp_path, monkeypatch) -> None:
    config = ConfigManager(tmp_path / "settings.json")
    config.update(
        {
            "ai": {
                "provider": "ollama",
                "model": "qwen3:8b",
                "base_url": OLLAMA_DEFAULT_BASE_URL,
            }
        }
    )
    secret = SecretStore(fail_on_load=True)
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("bootstrap HTTP")),
    )

    _service, runtime, resolution = _create_ai_runtime(
        tmp_path / "data",
        config,
        secret_store=secret,
    )

    assert secret.loads == 0
    assert resolution.effective_provider_id is AiProviderId.OLLAMA
    assert isinstance(resolution.provider, OpenAICompatibleProvider)
    assert runtime.ai_orchestrator is not None
    assert (
        runtime.ai_orchestrator.document_analysis_service.analyzer.provider is resolution.provider
    )


def test_unavailable_ollama_returns_current_provider_error(tmp_path, monkeypatch) -> None:
    config = ConfigManager(tmp_path / "settings.json")
    config.update(
        {
            "ai": {
                "provider": "ollama",
                "model": "qwen3:8b",
                "base_url": OLLAMA_DEFAULT_BASE_URL,
            }
        }
    )
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ConnectionError("private exception detail")
        ),
    )
    _service, runtime, _resolution = _create_ai_runtime(
        tmp_path / "data",
        config,
        secret_store=SecretStore(fail_on_load=True),
    )
    assert runtime.ai_orchestrator is not None
    runtime.ai_orchestrator.document_analysis_service.context_builder = Builder()  # type: ignore[assignment]

    result = runtime.ai_orchestrator.run("procurement:ollama-offline", force=True)

    assert result.document_analysis.status == "provider_error"
    assert "private exception detail" not in repr(result)


def test_bootstrap_resolves_selected_provider_without_network(tmp_path, monkeypatch) -> None:
    config = ConfigManager(tmp_path / "settings.json")
    config.update(
        {
            "ai": {
                "provider": "openai",
                "model": "gpt-test",
                "base_url": "https://ignored.example.test/v1",
            }
        }
    )
    secret = SecretStore("saved-key")
    network_calls: list[str] = []

    def fail_network(self, prompt: str, documents: list[str]) -> dict:
        del self, prompt, documents
        network_calls.append("called")
        raise AssertionError("network must not run during bootstrap")

    monkeypatch.setattr(OpenAICompatibleProvider, "analyze", fail_network)

    _service, runtime, resolution = _create_ai_runtime(
        tmp_path / "data",
        config,
        secret_store=secret,
    )

    assert resolution.effective_provider_id is AiProviderId.OPENAI
    assert isinstance(resolution.provider, OpenAICompatibleProvider)
    assert runtime.ai_orchestrator is not None
    assert network_calls == []


def test_runtime_keeps_one_ai_graph_and_shared_repository(tmp_path) -> None:
    runtime = create_tender_search_runtime(tmp_path, ai_provider=RecordingProvider())
    assert runtime.ai_orchestrator is not None
    assert runtime.full_analysis_service is not None
    assert runtime.participation_decision_service is not None

    service = runtime.ai_orchestrator.document_analysis_service
    assert runtime.full_analysis_service.ai_orchestrator is runtime.ai_orchestrator
    assert not hasattr(runtime.participation_decision_service, "ai_analysis_repository")
    assert service.repository is runtime.ai_orchestrator.document_analysis_service.repository


def test_only_analyzer_calls_provider_directly() -> None:
    root = Path("app")
    direct_callers = [
        path.as_posix()
        for path in root.rglob("*.py")
        if "provider.analyze(" in path.read_text(encoding="utf-8")
    ]

    assert direct_callers == ["app/core/ai/analyzer.py"]
    assert "provider.analyze" not in Path("app/core/ai/legal_risk.py").read_text(encoding="utf-8")
    assert "provider.analyze" not in Path("app/core/ai/financial_risk.py").read_text(
        encoding="utf-8"
    )
    assert "provider.analyze" not in Path("app/core/ai/competition_review.py").read_text(
        encoding="utf-8"
    )
    assert "provider.analyze" not in Path("app/tenders/full_analysis.py").read_text(
        encoding="utf-8"
    )
    assert "provider.analyze" not in Path("app/ui/main_window.py").read_text(encoding="utf-8")
