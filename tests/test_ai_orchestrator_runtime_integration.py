from __future__ import annotations

from pathlib import Path

from app.ai.provider import DisabledProvider
from app.core.ai.orchestrator import TenderAiOrchestrator
from app.tenders.search_runtime import create_tender_search_runtime


def test_runtime_builds_one_shared_orchestrator_and_repository(tmp_path) -> None:
    runtime = create_tender_search_runtime(tmp_path)

    orchestrator = runtime.ai_orchestrator
    assert isinstance(orchestrator, TenderAiOrchestrator)
    assert runtime.full_analysis_service is not None
    assert runtime.full_analysis_service.ai_orchestrator is orchestrator
    service = orchestrator.document_analysis_service
    assert isinstance(service.analyzer.provider, DisabledProvider)
    assert runtime.participation_decision_service is not None
    assert not hasattr(runtime.participation_decision_service, "ai_analysis_repository")


def test_production_runtime_contains_one_orchestrator_construction() -> None:
    source = Path("app/tenders/search_runtime.py").read_text(encoding="utf-8")

    assert source.count("TenderAiOrchestrator(ai_document_analysis_service)") == 1
    assert "OpenAICompatibleProvider" not in source


def test_ui_does_not_call_provider_directly() -> None:
    source = Path("app/ui/tender_full_analysis_dialog.py").read_text(encoding="utf-8")

    assert "AIProvider" not in source
    assert "provider.analyze" not in source


def test_legacy_structured_analysis_is_not_a_provider_workflow() -> None:
    source = Path("app/ai/structured_analysis.py").read_text(encoding="utf-8")

    assert "AIProvider" not in source
    assert "class TenderAIService" not in source
    assert "def analyze(" not in source
    assert 'payload.get("recommendation"' not in source
    assert 'payload.get("score"' not in source
