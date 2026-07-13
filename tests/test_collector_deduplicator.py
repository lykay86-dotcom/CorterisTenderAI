"""Tests for multi-level cross-source deduplication."""

from __future__ import annotations

from app.tenders.collector.deduplicator import TenderDeduplicator
from app.tenders.collector.models import DeduplicationMatchLevel
from app.tenders.models import TenderSource
from tests.collector_c3_helpers import make_document, make_tender


def test_merges_same_eis_number_from_two_sources() -> None:
    first = make_tender(
        source=TenderSource.EIS,
        external_id="eis-1",
        documents=(make_document("tz"),),
        raw_metadata={"eis_number": "0373100000126000001"},
    )
    second = make_tender(
        source=TenderSource.CUSTOM,
        external_id="platform-55",
        procurement_number="platform-55",
        documents=(
            make_document(
                "contract",
                name="Проект контракта.pdf",
            ),
        ),
        raw_metadata={"eis_number": "0373100000126000001"},
    )

    result = TenderDeduplicator().deduplicate((first, second))

    assert result.raw_count == 2
    assert result.merged_count == 1
    assert result.duplicate_count == 1
    group = result.groups[0]
    assert DeduplicationMatchLevel.EIS_NUMBER in group.match_levels
    assert len(group.item.tender.documents) == 2
    assert group.item.tender.raw_metadata["collector_merged_count"] == 2
    assert len(group.item.tender.raw_metadata["collector_sources"]) == 2


def test_composite_match_merges_platform_records_without_shared_number() -> None:
    first = make_tender(
        source=TenderSource.CUSTOM,
        external_id="mos-1",
        procurement_number="mos-1",
    )
    second = make_tender(
        source=TenderSource.COMMERCIAL,
        external_id="b2b-9",
        procurement_number="b2b-9",
    )

    result = TenderDeduplicator().deduplicate((first, second))

    assert result.merged_count == 1
    assert DeduplicationMatchLevel.COMPOSITE in (result.groups[0].match_levels)


def test_distinct_tenders_remain_separate() -> None:
    first = make_tender(external_id="one")
    second = make_tender(
        external_id="two",
        procurement_number="0373100000126000002",
        title="Строительство автомобильной дороги",
        amount="800000000.00",
    )

    result = TenderDeduplicator().deduplicate((first, second))

    assert result.merged_count == 2
    assert result.duplicate_count == 0
