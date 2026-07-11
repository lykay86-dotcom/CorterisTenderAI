"""Tests for the SQLite tender registry and duplicate protection."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from app.tenders.corteris_filter import (
    CorterisTenderFilterResult,
    EvaluatedTender,
    RelevanceGrade,
    TenderDirection,
    TenderRelevance,
)
from app.tenders.corteris_search import CorterisTenderSearchResult
from app.tenders.models import (
    TenderCustomer,
    TenderMoney,
    TenderSource,
    TenderStatus,
    UnifiedTender,
)
from app.tenders.search_engine import AggregatedTenderSearchResult
from app.tenders.search_profile_runner import TenderSearchProfileRun
from app.tenders.search_profiles import create_builtin_search_profiles
from app.tenders.tender_registry import TenderRegistryRepository


def _evaluated_tender(
    *,
    procurement_number: str = "0373100000126000001",
    source: TenderSource = TenderSource.EIS,
    external_id: str = "eis-1",
    title: str = "Монтаж системы видеонаблюдения",
    score: int = 88,
    accepted: bool = True,
) -> EvaluatedTender:
    tender = UnifiedTender(
        source=source,
        external_id=external_id,
        procurement_number=procurement_number,
        title=title,
        customer=TenderCustomer(
            name="ГБУ города Москвы",
            inn="7700000000",
            region="Москва",
        ),
        source_url=f"https://example.org/{source.value}/{external_id}",
        published_at=datetime(2026, 7, 11, 9, 0),
        application_deadline=datetime(2026, 7, 18, 10, 0),
        price=TenderMoney.from_value("1500000"),
        status=TenderStatus.ACCEPTING_APPLICATIONS,
        law="44-ФЗ",
        region="Москва",
        description="Поставка и монтаж 24 IP-видеокамер.",
        tags=("видеонаблюдение", "монтаж"),
    )
    relevance = TenderRelevance(
        score=score,
        grade=(
            RelevanceGrade.HIGH
            if score >= 65
            else RelevanceGrade.MEDIUM
        ),
        directions=(TenderDirection.VIDEO_SURVEILLANCE,),
        matched_strong_terms=("видеонаблюдение",),
        matched_weak_terms=(),
        matched_action_terms=("монтаж",),
        matched_exclusion_terms=(),
        reasons=("Профильная закупка.",),
    )
    return EvaluatedTender(
        tender=tender,
        relevance=relevance,
        accepted=accepted,
        rejection_reasons=(
            () if accepted else ("Ниже порога профиля",)
        ),
    )


def _run(
    *items: EvaluatedTender,
    executed_at: str = "2026-07-11T12:00:01+00:00",
) -> TenderSearchProfileRun:
    accepted = tuple(item for item in items if item.accepted)
    rejected = tuple(item for item in items if not item.accepted)
    tenders = tuple(item.tender for item in items)
    return TenderSearchProfileRun(
        profile=create_builtin_search_profiles()[1],
        result=CorterisTenderSearchResult(
            provider_result=AggregatedTenderSearchResult(
                items=tenders,
                outcomes=(),
                raw_item_count=len(tenders),
                duplicate_count=0,
                provider_count=1,
                completed_provider_count=1,
                started_at="2026-07-11T12:00:00",
                completed_at="2026-07-11T12:00:01",
                elapsed_ms=1000,
            ),
            filter_result=CorterisTenderFilterResult(
                accepted=accepted,
                rejected=rejected,
                total_count=len(items),
                accepted_count=len(accepted),
                rejected_count=len(rejected),
                direction_counts={
                    TenderDirection.VIDEO_SURVEILLANCE: len(accepted)
                },
            ),
        ),
        executed_at=executed_at,
    )


def test_registry_initializes_empty_database(tmp_path) -> None:
    repository = TenderRegistryRepository(
        tmp_path / "tender_registry.sqlite3"
    )

    repository.initialize()

    assert repository.path.is_file()
    assert repository.count_tenders() == 0
    assert repository.list_search_runs() == ()


def test_profile_run_inserts_tender_and_search_history(tmp_path) -> None:
    repository = TenderRegistryRepository(
        tmp_path / "tender_registry.sqlite3"
    )
    run = _run(_evaluated_tender())

    summary = repository.record_profile_run(
        run,
        run_id="run-1",
    )

    assert summary.inserted_count == 1
    assert summary.updated_count == 0
    assert summary.occurrence_count == 1
    assert repository.count_tenders() == 1
    assert repository.run_item_count("run-1") == 1

    record = repository.get_by_procurement_number(
        "0373100000126000001"
    )
    assert record is not None
    assert record.title == "Монтаж системы видеонаблюдения"
    assert record.seen_count == 1
    assert record.relevance_score == 88
    assert record.last_accepted

    history = repository.list_search_runs()
    assert len(history) == 1
    assert history[0].profile_id == run.profile.id
    assert history[0].accepted_count == 1


def test_repeated_search_updates_same_row_without_duplicate(tmp_path) -> None:
    repository = TenderRegistryRepository(
        tmp_path / "tender_registry.sqlite3"
    )
    first = _run(_evaluated_tender(), executed_at="2026-07-11T12:00:00+00:00")
    second_item = _evaluated_tender(
        title="Монтаж и модернизация видеонаблюдения",
        score=94,
    )
    second = _run(
        second_item,
        executed_at="2026-07-12T12:00:00+00:00",
    )

    repository.record_profile_run(first, run_id="run-1")
    summary = repository.record_profile_run(second, run_id="run-2")

    assert summary.inserted_count == 0
    assert summary.updated_count == 1
    assert repository.count_tenders() == 1

    record = repository.get_by_procurement_number(
        "0373100000126000001"
    )
    assert record is not None
    assert record.title == "Монтаж и модернизация видеонаблюдения"
    assert record.seen_count == 2
    assert record.relevance_score == 94
    assert len(repository.list_search_runs()) == 2


def test_same_procurement_number_from_other_source_is_not_duplicated(
    tmp_path,
) -> None:
    repository = TenderRegistryRepository(
        tmp_path / "tender_registry.sqlite3"
    )
    eis = _evaluated_tender(
        source=TenderSource.EIS,
        external_id="eis-1",
    )
    rts = _evaluated_tender(
        source=TenderSource.RTS_TENDER,
        external_id="rts-99",
        title="Та же закупка на РТС-тендер",
    )

    repository.record_profile_run(_run(eis), run_id="run-eis")
    repository.record_profile_run(_run(rts), run_id="run-rts")

    assert repository.count_tenders() == 1
    record = repository.get_by_procurement_number(
        eis.tender.procurement_number
    )
    assert record is not None
    assert record.source == TenderSource.RTS_TENDER.value
    assert record.seen_count == 2


def test_registry_keeps_rejected_items_and_acceptance_filter(tmp_path) -> None:
    repository = TenderRegistryRepository(
        tmp_path / "tender_registry.sqlite3"
    )
    accepted = _evaluated_tender()
    rejected = _evaluated_tender(
        procurement_number="0373100000126000002",
        external_id="eis-2",
        title="Слабое совпадение по камере",
        score=20,
        accepted=False,
    )

    summary = repository.record_profile_run(
        _run(accepted, rejected),
        run_id="mixed-run",
    )

    assert summary.accepted_count == 1
    assert summary.rejected_count == 1
    assert repository.count_tenders() == 2
    assert repository.count_tenders(accepted_only=True) == 1
    assert len(repository.list_tenders(accepted_only=True)) == 1


def test_registry_archive_hides_record_by_default(tmp_path) -> None:
    repository = TenderRegistryRepository(
        tmp_path / "tender_registry.sqlite3"
    )
    item = _evaluated_tender()
    repository.record_profile_run(_run(item), run_id="run-1")
    record = repository.list_tenders()[0]

    assert repository.set_archived(record.registry_key, True)
    assert repository.count_tenders() == 0
    assert repository.count_tenders(include_archived=True) == 1
    assert repository.list_tenders(include_archived=True)[0].archived
