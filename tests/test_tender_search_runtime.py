"""Tests for production tender-search service composition."""

from __future__ import annotations

from app.tenders.search_runtime import create_tender_search_runtime


class NoNetworkTransport:
    def __init__(self) -> None:
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("Runtime creation must not use network")


def test_runtime_builds_repository_registry_and_runner(tmp_path) -> None:
    transport = NoNetworkTransport()

    runtime = create_tender_search_runtime(
        tmp_path / "data",
        http_transport=transport,
        max_workers=3,
        timeout_seconds=12,
    )

    assert runtime.data_directory == tmp_path / "data"
    assert runtime.repository.path == (
        tmp_path / "data" / "search_profiles.json"
    )
    assert len(runtime.repository.list_profiles()) == 7
    assert runtime.registry.get("eis").descriptor.id == "eis"
    assert runtime.engine.max_workers == 3
    assert runtime.engine.timeout_seconds == 12
    assert runtime.runner.repository is runtime.repository
    assert runtime.runner.search_service is runtime.search_service
    assert transport.calls == 0
