"""Tests for multi-provider tender search execution."""

from __future__ import annotations

from time import perf_counter

from app.tenders.models import TenderSource
from app.tenders.provider_base import TenderSearchQuery
from app.tenders.provider_registry import TenderProviderRegistry
from app.tenders.search_engine import (
    ProviderSearchStatus,
    TenderSearchEngine,
)
from tests.tender_search_helpers import (
    FakeProvider,
    descriptor,
    tender,
)


def test_parallel_search_preserves_registry_order() -> None:
    slow = FakeProvider(
        descriptor=descriptor(
            "eis",
            TenderSource.EIS,
            priority=10,
        ),
        items=(
            tender(
                source=TenderSource.EIS,
                external_id="1",
                procurement_number="001",
                title="ЕИС",
            ),
        ),
        delay_seconds=0.08,
    )
    fast = FakeProvider(
        descriptor=descriptor(
            "rts_tender",
            TenderSource.RTS_TENDER,
            priority=20,
        ),
        items=(
            tender(
                source=TenderSource.RTS_TENDER,
                external_id="2",
                procurement_number="002",
                title="РТС",
            ),
        ),
        delay_seconds=0.01,
    )
    engine = TenderSearchEngine(
        TenderProviderRegistry((slow, fast)),
        max_workers=2,
        timeout_seconds=1,
    )

    started = perf_counter()
    result = engine.search(
        TenderSearchQuery(keywords=("СКУД",)),
        parallel=True,
    )
    elapsed = perf_counter() - started

    assert elapsed < 0.14
    assert [item.title for item in result.items] == [
        "ЕИС",
        "РТС",
    ]
    assert [outcome.provider_id for outcome in result.outcomes] == ["eis", "rts_tender"]
    assert all(outcome.status == ProviderSearchStatus.SUCCESS for outcome in result.outcomes)


def test_search_can_select_specific_providers() -> None:
    providers = (
        FakeProvider(
            descriptor=descriptor(
                "eis",
                TenderSource.EIS,
                priority=10,
            ),
        ),
        FakeProvider(
            descriptor=descriptor(
                "roseltorg",
                TenderSource.ROSELTORG,
                priority=20,
            ),
        ),
    )
    engine = TenderSearchEngine(TenderProviderRegistry(providers))

    result = engine.search(
        TenderSearchQuery(),
        provider_ids=("roseltorg",),
    )

    assert result.provider_count == 1
    assert result.outcomes[0].provider_id == "roseltorg"


def test_disabled_provider_is_skipped_unless_requested() -> None:
    disabled = FakeProvider(
        descriptor=descriptor(
            "commercial",
            TenderSource.COMMERCIAL,
            priority=100,
            enabled=False,
        )
    )
    engine = TenderSearchEngine(TenderProviderRegistry((disabled,)))

    normal = engine.search(TenderSearchQuery())
    explicit = engine.search(
        TenderSearchQuery(),
        provider_ids=("commercial",),
        include_disabled=True,
    )

    assert normal.provider_count == 0
    assert explicit.provider_count == 1


def test_unknown_provider_id_is_rejected() -> None:
    engine = TenderSearchEngine(TenderProviderRegistry())

    try:
        engine.search(
            TenderSearchQuery(),
            provider_ids=("missing",),
        )
    except KeyError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("Expected KeyError")
