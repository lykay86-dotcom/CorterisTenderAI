"""Tests for production tender-search service composition."""

from __future__ import annotations

from app.tenders.search_runtime import create_tender_search_runtime


class NoNetworkTransport:
    def __init__(self) -> None:
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("Runtime creation must not use network")


def test_runtime_builds_production_services_without_legacy_search_owners(tmp_path) -> None:
    transport = NoNetworkTransport()

    runtime = create_tender_search_runtime(
        tmp_path / "data",
        http_transport=transport,
        max_workers=3,
        timeout_seconds=12,
    )

    assert runtime.data_directory == tmp_path / "data"
    assert runtime.repository.path == (tmp_path / "data" / "search_profiles.json")
    assert len(runtime.repository.list_profiles()) == 7
    assert runtime.registry.get("eis").descriptor.id == "eis"
    assert runtime.engine is None
    assert runtime.search_service is None
    assert runtime.runner is None
    assert runtime.ai_orchestrator is not None
    assert callable(runtime.ai_orchestrator.recheck)
    assert (
        runtime.ai_orchestrator.document_analysis_service.context_builder.document_store
        is runtime.document_store
    )
    assert transport.calls == 0
