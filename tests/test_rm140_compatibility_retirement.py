"""Expected RM-140 production/compatibility ownership contract."""

from __future__ import annotations

import inspect
import socket

from app.tenders import (
    CorterisTenderSearchService,
    TenderSearchEngine,
    TenderSearchProfileRunner,
)
from app.tenders.search_runtime import create_tender_search_runtime
from app.ui.tender_search_ui_controller import TenderSearchUiController


def test_public_legacy_imports_remain_available_for_rollback_window() -> None:
    assert callable(TenderSearchEngine)
    assert callable(CorterisTenderSearchService)
    assert callable(TenderSearchProfileRunner)


def test_production_runtime_does_not_compose_legacy_search_owners(
    tmp_path,
    monkeypatch,
) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("network is forbidden during composition")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)

    runtime = create_tender_search_runtime(tmp_path)

    assert getattr(runtime, "engine", None) is None
    assert getattr(runtime, "search_service", None) is None
    assert getattr(runtime, "runner", None) is None


def test_production_ui_routes_saved_profiles_only_to_collector_admission() -> None:
    source = inspect.getsource(TenderSearchUiController)

    assert "self.runtime.runner" not in source
    assert "_TenderSearchWorker" not in source
    run_profile = inspect.getsource(TenderSearchUiController.run_profile)
    assert "try_start_collector" in run_profile
    assert "_thread_pool.start" not in run_profile
