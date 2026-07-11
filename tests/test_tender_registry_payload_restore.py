"""Tests for restoring UnifiedTender objects from the local registry."""

from __future__ import annotations

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
    TenderDocument,
    TenderMoney,
    TenderSource,
    TenderStatus,
    UnifiedTender,
)
from app.tenders.search_engine import AggregatedTenderSearchResult
from app.tenders.search_profile_runner import TenderSearchProfileRun
from app.tenders.search_profiles import create_builtin_search_profiles
from app.tenders.tender_registry import (
    TenderRegistryRepository,
    tender_registry_key,
)


def test_registry_restores_full_tender_payload(tmp_path) -> None:
    document = TenderDocument(
        id="doc-1",
        name="Техническое задание.pdf",
        url="https://files.example.org/tz.pdf",
        mime_type="application/pdf",
        size_bytes=2048,
    )
    tender = UnifiedTender(
        source=TenderSource.EIS,
        external_id="eis-1",
        procurement_number="0373100000126000001",
        title="Монтаж видеонаблюдения",
        customer=TenderCustomer(
            name="ГБУ города Москвы",
            inn="7700000000",
            region="Москва",
        ),
        source_url="https://example.org/eis-1",
        published_at=datetime(2026, 7, 10, 9, 0),
        application_deadline=datetime(2026, 7, 20, 10, 0),
        price=TenderMoney.from_value("1500000"),
        status=TenderStatus.ACCEPTING_APPLICATIONS,
        law="44-ФЗ",
        region="Москва",
        documents=(document,),
    )
    relevance = TenderRelevance(
        score=90,
        grade=RelevanceGrade.HIGH,
        directions=(TenderDirection.VIDEO_SURVEILLANCE,),
        matched_strong_terms=("видеонаблюдение",),
        matched_weak_terms=(),
        matched_action_terms=("монтаж",),
        matched_exclusion_terms=(),
        reasons=("Профильная закупка",),
    )
    evaluated = EvaluatedTender(
        tender=tender,
        relevance=relevance,
        accepted=True,
    )
    run = TenderSearchProfileRun(
        profile=create_builtin_search_profiles()[1],
        result=CorterisTenderSearchResult(
            provider_result=AggregatedTenderSearchResult(
                items=(tender,),
                outcomes=(),
                raw_item_count=1,
                duplicate_count=0,
                provider_count=1,
                completed_provider_count=1,
                started_at="2026-07-12T12:00:00",
                completed_at="2026-07-12T12:00:01",
                elapsed_ms=1000,
            ),
            filter_result=CorterisTenderFilterResult(
                accepted=(evaluated,),
                rejected=(),
                total_count=1,
                accepted_count=1,
                rejected_count=0,
                direction_counts={
                    TenderDirection.VIDEO_SURVEILLANCE: 1
                },
            ),
        ),
        executed_at="2026-07-12T12:00:01+00:00",
    )
    repository = TenderRegistryRepository(
        tmp_path / "tender_registry.sqlite3"
    )
    repository.record_profile_run(run, run_id="run-1")

    restored = repository.get_tender(tender_registry_key(tender))

    assert restored is not None
    assert restored.procurement_number == tender.procurement_number
    assert restored.customer.inn == "7700000000"
    assert restored.price is not None
    assert restored.price.amount == tender.price.amount
    assert restored.documents == (document,)
