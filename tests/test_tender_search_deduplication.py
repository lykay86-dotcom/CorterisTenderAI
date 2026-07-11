"""Tests for cross-source tender deduplication and merging."""

from __future__ import annotations

from app.tenders.models import (
    TenderDocument,
    TenderSource,
)
from app.tenders.provider_base import TenderSearchQuery
from app.tenders.provider_registry import TenderProviderRegistry
from app.tenders.search_engine import TenderSearchEngine
from tests.tender_search_helpers import (
    FakeProvider,
    descriptor,
    tender,
)


def test_same_procurement_number_is_merged_across_sources() -> None:
    eis_document = TenderDocument(
        id="eis-tz",
        name="ТЗ.pdf",
        url="https://eis.example.org/tz.pdf",
    )
    rts_document = TenderDocument(
        id="rts-form",
        name="Форма заявки.docx",
        url="https://rts.example.org/form.docx",
    )
    eis = FakeProvider(
        descriptor=descriptor(
            "eis",
            TenderSource.EIS,
            priority=10,
        ),
        items=(
            tender(
                source=TenderSource.EIS,
                external_id="eis-1",
                procurement_number="0373100000126000001",
                title="Монтаж системы видеонаблюдения",
                amount="1500000",
                tags=("видеонаблюдение",),
                documents=(eis_document,),
            ),
        ),
    )
    rts = FakeProvider(
        descriptor=descriptor(
            "rts_tender",
            TenderSource.RTS_TENDER,
            priority=20,
        ),
        items=(
            tender(
                source=TenderSource.RTS_TENDER,
                external_id="rts-9",
                procurement_number="0373100000126000001",
                title="Монтаж системы видеонаблюдения на объекте",
                description="Монтаж 24 камер и настройка архива.",
                region="Москва",
                tags=("монтаж",),
                documents=(rts_document,),
            ),
        ),
    )

    result = TenderSearchEngine(
        TenderProviderRegistry((eis, rts))
    ).search(TenderSearchQuery())

    assert result.raw_item_count == 2
    assert result.duplicate_count == 1
    assert len(result.items) == 1

    merged = result.items[0]
    assert merged.source == TenderSource.EIS
    assert merged.price is not None
    assert merged.region == "Москва"
    assert "24 камер" in merged.description
    assert merged.tags == ("видеонаблюдение", "монтаж")
    assert len(merged.documents) == 2
    assert merged.raw_metadata["aggregated_sources"] == (
        "eis",
        "rts_tender",
    )
    assert len(
        merged.raw_metadata["aggregated_identities"]
    ) == 2


def test_duplicate_document_url_is_not_repeated() -> None:
    document_one = TenderDocument(
        id="one",
        name="ТЗ.pdf",
        url="https://files.example.org/tz.pdf",
    )
    document_two = TenderDocument(
        id="two",
        name="Копия ТЗ.pdf",
        url="https://files.example.org/tz.pdf",
    )
    providers = (
        FakeProvider(
            descriptor=descriptor(
                "eis",
                TenderSource.EIS,
                priority=10,
            ),
            items=(
                tender(
                    source=TenderSource.EIS,
                    external_id="1",
                    procurement_number="A-1",
                    title="Тендер",
                    documents=(document_one,),
                ),
            ),
        ),
        FakeProvider(
            descriptor=descriptor(
                "roseltorg",
                TenderSource.ROSELTORG,
                priority=20,
            ),
            items=(
                tender(
                    source=TenderSource.ROSELTORG,
                    external_id="2",
                    procurement_number="A-1",
                    title="Тендер",
                    documents=(document_two,),
                ),
            ),
        ),
    )

    result = TenderSearchEngine(
        TenderProviderRegistry(providers)
    ).search(TenderSearchQuery())

    assert len(result.items[0].documents) == 1


def test_different_procurement_numbers_remain_separate() -> None:
    provider = FakeProvider(
        descriptor=descriptor(
            "eis",
            TenderSource.EIS,
            priority=10,
        ),
        items=(
            tender(
                source=TenderSource.EIS,
                external_id="1",
                procurement_number="A-1",
                title="Первый",
            ),
            tender(
                source=TenderSource.EIS,
                external_id="2",
                procurement_number="A-2",
                title="Второй",
            ),
        ),
    )

    result = TenderSearchEngine(
        TenderProviderRegistry((provider,))
    ).search(TenderSearchQuery())

    assert len(result.items) == 2
    assert result.duplicate_count == 0
