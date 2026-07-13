"""Tests for executing saved tender-search profiles."""

from __future__ import annotations

from datetime import date

import pytest

from app.tenders.corteris_filter import TenderDirection
from app.tenders.search_profile_repository import (
    TenderSearchProfileRepository,
)
from app.tenders.search_profile_runner import (
    TenderSearchProfileRunner,
)
from app.tenders.search_profiles import TenderSearchProfile


class FakeSearchResult:
    pass


class FakeSearchService:
    def __init__(self) -> None:
        self.calls = []

    def search(self, query, **kwargs):
        self.calls.append((query, kwargs))
        return FakeSearchResult()


def test_runner_resolves_profile_and_forwards_settings(
    tmp_path,
) -> None:
    repository = TenderSearchProfileRepository(tmp_path / "search_profiles.json")
    repository.initialize()
    repository.save(
        TenderSearchProfile(
            id="barriers-msk",
            name="Шлагбаумы Москва",
            keywords=("шлагбаум",),
            directions=(TenderDirection.BARRIERS,),
            regions=("Москва",),
            minimum_score=35,
            lookback_days=7,
            provider_ids=("eis",),
        )
    )
    service = FakeSearchService()
    runner = TenderSearchProfileRunner(
        repository,
        service,
    )

    run = runner.run(
        "barriers-msk",
        today=date(2026, 7, 13),
        page=3,
        parallel=False,
    )

    assert run.profile.id == "barriers-msk"
    assert isinstance(run.result, FakeSearchResult)
    query, kwargs = service.calls[0]
    assert query.date_from == date(2026, 7, 6)
    assert query.page == 3
    assert kwargs["provider_ids"] == ("eis",)
    assert kwargs["parallel"] is False
    assert kwargs["filter_options"].required_directions == (TenderDirection.BARRIERS,)


def test_runner_rejects_disabled_profile(tmp_path) -> None:
    repository = TenderSearchProfileRepository(tmp_path / "search_profiles.json")
    repository.initialize()
    repository.set_enabled("ops", False)
    runner = TenderSearchProfileRunner(
        repository,
        FakeSearchService(),
    )

    with pytest.raises(ValueError):
        runner.run("ops")
