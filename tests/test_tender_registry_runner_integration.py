"""Tests for automatic persistence by TenderSearchProfileRunner."""

from __future__ import annotations

from datetime import date

from app.tenders.search_profile_repository import (
    TenderSearchProfileRepository,
)
from app.tenders.search_profile_runner import TenderSearchProfileRunner
from app.tenders.tender_registry import TenderRegistryRepository
from tests.test_tender_registry import _evaluated_tender, _run


class FakeSearchService:
    def __init__(self, result) -> None:
        self.result = result
        self.calls = []

    def search(self, query, **kwargs):
        self.calls.append((query, kwargs))
        return self.result


class FailingRegistry:
    def record_profile_run(self, run):
        raise OSError("disk unavailable")


def test_runner_automatically_persists_successful_search(tmp_path) -> None:
    profiles = TenderSearchProfileRepository(
        tmp_path / "search_profiles.json"
    )
    profiles.initialize()
    sample = _run(_evaluated_tender())
    service = FakeSearchService(sample.result)
    registry = TenderRegistryRepository(
        tmp_path / "tender_registry.sqlite3"
    )
    runner = TenderSearchProfileRunner(
        profiles,
        service,
        registry,
    )

    result = runner.run(
        sample.profile.id,
        today=date(2026, 7, 12),
        parallel=False,
    )

    assert result.profile.id == sample.profile.id
    assert registry.count_tenders() == 1
    assert len(registry.list_search_runs()) == 1
    summary = runner.last_save_summary(sample.profile.id)
    assert summary is not None
    assert summary.occurrence_count == 1
    assert runner.last_persistence_error(sample.profile.id) == ""


def test_optional_persistence_failure_does_not_hide_search_results(
    tmp_path,
) -> None:
    profiles = TenderSearchProfileRepository(
        tmp_path / "search_profiles.json"
    )
    profiles.initialize()
    sample = _run()
    runner = TenderSearchProfileRunner(
        profiles,
        FakeSearchService(sample.result),
        FailingRegistry(),
    )

    result = runner.run(sample.profile.id)

    assert result.result is sample.result
    assert "disk unavailable" in runner.last_persistence_error(
        sample.profile.id
    )


def test_required_persistence_failure_is_raised(tmp_path) -> None:
    profiles = TenderSearchProfileRepository(
        tmp_path / "search_profiles.json"
    )
    profiles.initialize()
    sample = _run()
    runner = TenderSearchProfileRunner(
        profiles,
        FakeSearchService(sample.result),
        FailingRegistry(),
        persistence_required=True,
    )

    try:
        runner.run(sample.profile.id)
    except OSError as exc:
        assert "disk unavailable" in str(exc)
    else:
        raise AssertionError("Expected OSError")
