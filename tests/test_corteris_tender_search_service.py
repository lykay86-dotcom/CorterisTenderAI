"""Tests for the combined Corteris tender search service."""

from __future__ import annotations

from datetime import datetime

from app.tenders.corteris_filter import (
    TenderDirection,
    TenderFilterOptions,
)
from app.tenders.corteris_search import (
    CorterisTenderSearchService,
)
from app.tenders.models import (
    TenderCustomer,
    TenderSource,
    TenderStatus,
    UnifiedTender,
)
from app.tenders.provider_base import TenderSearchQuery
from app.tenders.search_engine import (
    AggregatedTenderSearchResult,
)


def tender(title: str, number: str) -> UnifiedTender:
    return UnifiedTender(
        source=TenderSource.EIS,
        external_id=number,
        procurement_number=number,
        title=title,
        customer=TenderCustomer(name="Заказчик"),
        source_url=f"https://example.org/{number}",
        status=TenderStatus.ACCEPTING_APPLICATIONS,
        region="Москва",
    )


class FakeSearchEngine:
    def __init__(self, items) -> None:
        self.items = tuple(items)
        self.calls = []

    def search(self, query, **kwargs):
        self.calls.append((query, kwargs))
        return AggregatedTenderSearchResult(
            items=self.items,
            outcomes=(),
            raw_item_count=len(self.items),
            duplicate_count=0,
            provider_count=1,
            completed_provider_count=1,
            started_at="2026-07-12T12:00:00",
            completed_at="2026-07-12T12:00:01",
            elapsed_ms=1000,
        )


def test_service_filters_provider_results() -> None:
    engine = FakeSearchEngine(
        (
            tender("Монтаж видеонаблюдения", "1"),
            tender("Поставка холодильной камеры", "2"),
        )
    )
    service = CorterisTenderSearchService(engine)

    result = service.search(
        TenderSearchQuery(keywords=("камера",)),
    )

    assert result.found_count == 2
    assert result.relevant_count == 1
    assert result.tenders[0].procurement_number == "1"


def test_service_forwards_provider_and_filter_options() -> None:
    engine = FakeSearchEngine(
        (
            tender("Поставка автоматического шлагбаума", "1"),
            tender("Монтаж видеонаблюдения", "2"),
        )
    )
    service = CorterisTenderSearchService(engine)

    result = service.search(
        TenderSearchQuery(keywords=("безопасность",)),
        filter_options=TenderFilterOptions(
            required_directions=(TenderDirection.BARRIERS,)
        ),
        provider_ids=("eis",),
        include_disabled=True,
        parallel=False,
    )

    assert result.relevant_count == 1
    assert result.tenders[0].procurement_number == "1"

    _, kwargs = engine.calls[0]
    assert kwargs == {
        "provider_ids": ("eis",),
        "include_disabled": True,
        "parallel": False,
    }
