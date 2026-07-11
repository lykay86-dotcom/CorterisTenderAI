"""Tests for tender registry wiring in production search runtime."""

from __future__ import annotations

from app.tenders.search_runtime import create_tender_search_runtime


def test_runtime_initializes_sqlite_tender_registry(tmp_path) -> None:
    runtime = create_tender_search_runtime(tmp_path)

    assert runtime.tender_registry is not None
    assert runtime.tender_registry.path == (
        tmp_path / "tender_registry.sqlite3"
    )
    assert runtime.tender_registry.path.is_file()
    assert runtime.runner.tender_registry is runtime.tender_registry
    assert runtime.tender_registry.count_tenders() == 0
