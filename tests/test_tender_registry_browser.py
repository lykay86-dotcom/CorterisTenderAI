"""Tests for registry browsing, filtering, sorting and occurrences."""

from __future__ import annotations

from app.tenders.tender_registry import (
    TenderRegistryQuery,
    TenderRegistryRepository,
    TenderRegistrySort,
)
from tests.test_tender_registry import _evaluated_tender, _run


def test_registry_search_matches_russian_text_case_insensitively(
    tmp_path,
) -> None:
    repository = TenderRegistryRepository(
        tmp_path / "tender_registry.sqlite3"
    )
    repository.record_profile_run(
        _run(_evaluated_tender()),
        run_id="run-1",
    )

    records = repository.search_tenders(
        TenderRegistryQuery(text="ВИДЕОНАБЛЮДЕНИЯ")
    )

    assert len(records) == 1
    assert records[0].procurement_number == (
        "0373100000126000001"
    )


def test_registry_query_filters_score_acceptance_and_archive(
    tmp_path,
) -> None:
    repository = TenderRegistryRepository(
        tmp_path / "tender_registry.sqlite3"
    )
    accepted = _evaluated_tender(score=88)
    rejected = _evaluated_tender(
        procurement_number="0373100000126000002",
        external_id="eis-2",
        title="Поставка камеры",
        score=20,
        accepted=False,
    )
    repository.record_profile_run(
        _run(accepted, rejected),
        run_id="run-1",
    )

    high = repository.search_tenders(
        TenderRegistryQuery(
            accepted_only=True,
            minimum_score=65,
        )
    )
    assert len(high) == 1
    assert high[0].last_accepted

    repository.set_archived(high[0].registry_key, True)

    assert repository.search_tenders(
        TenderRegistryQuery(accepted_only=True)
    ) == ()
    archived = repository.search_tenders(
        TenderRegistryQuery(
            archived_only=True,
            include_archived=True,
        )
    )
    assert len(archived) == 1
    assert archived[0].archived


def test_registry_sort_and_count_use_same_query(tmp_path) -> None:
    repository = TenderRegistryRepository(
        tmp_path / "tender_registry.sqlite3"
    )
    first = _evaluated_tender(
        procurement_number="0373100000126000001",
        external_id="eis-1",
        title="Бета видеонаблюдение",
        score=70,
    )
    second = _evaluated_tender(
        procurement_number="0373100000126000002",
        external_id="eis-2",
        title="Альфа видеонаблюдение",
        score=90,
    )
    repository.record_profile_run(
        _run(first, second),
        run_id="run-1",
    )

    query = TenderRegistryQuery(
        text="видеонаблюдение",
        sort=TenderRegistrySort.TITLE_ASC,
    )
    records = repository.search_tenders(query)

    assert repository.count_search_results(query) == 2
    assert [record.title for record in records] == [
        "Альфа видеонаблюдение",
        "Бета видеонаблюдение",
    ]


def test_registry_occurrences_show_profile_history(tmp_path) -> None:
    repository = TenderRegistryRepository(
        tmp_path / "tender_registry.sqlite3"
    )
    repository.record_profile_run(
        _run(
            _evaluated_tender(score=75),
            executed_at="2026-07-11T12:00:00+00:00",
        ),
        run_id="run-1",
    )
    repository.record_profile_run(
        _run(
            _evaluated_tender(score=92),
            executed_at="2026-07-12T12:00:00+00:00",
        ),
        run_id="run-2",
    )
    record = repository.list_tenders()[0]

    occurrences = repository.list_tender_occurrences(
        record.registry_key
    )

    assert [item.run_id for item in occurrences] == [
        "run-2",
        "run-1",
    ]
    assert occurrences[0].relevance_score == 92
    assert occurrences[0].accepted
    assert occurrences[0].directions == (
        "video_surveillance",
    )


def test_registry_statistics_include_runs_and_archive(tmp_path) -> None:
    repository = TenderRegistryRepository(
        tmp_path / "tender_registry.sqlite3"
    )
    accepted = _evaluated_tender()
    rejected = _evaluated_tender(
        procurement_number="0373100000126000002",
        external_id="eis-2",
        score=20,
        accepted=False,
    )
    repository.record_profile_run(
        _run(accepted, rejected),
        run_id="run-1",
    )
    record = repository.get_by_procurement_number(
        accepted.tender.procurement_number
    )
    assert record is not None
    repository.set_archived(record.registry_key, True)

    statistics = repository.statistics()

    assert statistics.total_count == 2
    assert statistics.active_count == 1
    assert statistics.archived_count == 1
    assert statistics.accepted_count == 1
    assert statistics.search_run_count == 1
