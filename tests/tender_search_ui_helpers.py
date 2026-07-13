"""Shared deterministic objects for tender-search UI tests."""

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
    TenderMoney,
    TenderSource,
    TenderStatus,
    UnifiedTender,
)
from app.tenders.search_engine import (
    AggregatedTenderSearchResult,
    ProviderSearchOutcome,
    ProviderSearchStatus,
)
from app.tenders.search_profile_runner import TenderSearchProfileRun
from app.tenders.search_profiles import create_builtin_search_profiles


def make_profile_run(
    *,
    include_tender: bool = True,
) -> TenderSearchProfileRun:
    profile = create_builtin_search_profiles()[1]

    accepted: tuple[EvaluatedTender, ...] = ()
    items: tuple[UnifiedTender, ...] = ()
    if include_tender:
        tender = UnifiedTender(
            source=TenderSource.EIS,
            external_id="eis-1",
            procurement_number="0373100000126000001",
            title="Монтаж системы видеонаблюдения",
            customer=TenderCustomer(
                name="ГБУ города Москвы",
                inn="7700000000",
                region="Москва",
            ),
            source_url=(
                "https://zakupki.gov.ru/epz/order/notice/"
                "ea20/view/common-info.html?regNumber="
                "0373100000126000001"
            ),
            published_at=datetime(2026, 7, 11, 9, 0),
            application_deadline=datetime(2026, 7, 18, 10, 0),
            price=TenderMoney.from_value("1500000"),
            status=TenderStatus.ACCEPTING_APPLICATIONS,
            law="44-ФЗ",
            region="Москва",
            description=(
                "Поставка и монтаж 24 IP-видеокамер, видеорегистратора и системы хранения."
            ),
            tags=("видеонаблюдение", "монтаж"),
        )
        relevance = TenderRelevance(
            score=88,
            grade=RelevanceGrade.HIGH,
            directions=(TenderDirection.VIDEO_SURVEILLANCE,),
            matched_strong_terms=(
                "видеонаблюдение",
                "видеорегистратор",
            ),
            matched_weak_terms=(),
            matched_action_terms=("поставка", "монтаж"),
            matched_exclusion_terms=(),
            reasons=(
                "video_surveillance: 42 балл.",
                "Есть работы/поставка по профильному направлению.",
            ),
        )
        accepted = (
            EvaluatedTender(
                tender=tender,
                relevance=relevance,
                accepted=True,
            ),
        )
        items = (tender,)

    provider_result = AggregatedTenderSearchResult(
        items=items,
        outcomes=(
            ProviderSearchOutcome(
                provider_id="eis",
                display_name="ЕИС Закупки",
                status=(
                    ProviderSearchStatus.SUCCESS if include_tender else ProviderSearchStatus.EMPTY
                ),
                elapsed_ms=250,
                item_count=len(items),
            ),
        ),
        raw_item_count=len(items),
        duplicate_count=0,
        provider_count=1,
        completed_provider_count=1,
        started_at="2026-07-11T12:00:00",
        completed_at="2026-07-11T12:00:01",
        elapsed_ms=1000,
    )
    filter_result = CorterisTenderFilterResult(
        accepted=accepted,
        rejected=(),
        total_count=len(accepted),
        accepted_count=len(accepted),
        rejected_count=0,
        direction_counts=({TenderDirection.VIDEO_SURVEILLANCE: 1} if accepted else {}),
    )
    return TenderSearchProfileRun(
        profile=profile,
        result=CorterisTenderSearchResult(
            provider_result=provider_result,
            filter_result=filter_result,
        ),
        executed_at="2026-07-11T12:00:01+00:00",
    )
