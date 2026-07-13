"""Runtime composition test for the participation score service."""

from __future__ import annotations

from app.tenders.search_runtime import create_tender_search_runtime


def test_runtime_builds_participation_score_service(tmp_path) -> None:
    runtime = create_tender_search_runtime(tmp_path)

    assert runtime.participation_score_service is not None
    assert runtime.participation_score_service.tender_registry is (runtime.tender_registry)
