"""Tests for multi-level cross-source deduplication."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

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


def test_mixed_naive_and_aware_dates_prefer_confirmed_timezone() -> None:
    first = replace(
        make_tender(external_id="one"),
        published_at=datetime(2026, 7, 10),
        application_deadline=datetime(2026, 7, 20),
    )
    confirmed_zone = timezone(timedelta(hours=3))
    second = replace(
        make_tender(source=TenderSource.CUSTOM, external_id="two"),
        published_at=datetime(2026, 7, 11, tzinfo=confirmed_zone),
        application_deadline=datetime(2026, 7, 19, tzinfo=confirmed_zone),
    )

    merged = TenderDeduplicator().deduplicate((first, second)).groups[0].item.tender

    assert merged.published_at == second.published_at
    assert merged.application_deadline == second.application_deadline


def test_supplier_portal_uses_shared_official_source_trust() -> None:
    portal = make_tender(
        source=TenderSource.MOS_SUPPLIER,
        external_id="portal",
    )
    public_card = make_tender(
        source=TenderSource.CUSTOM,
        external_id="public-card",
    )

    merged = TenderDeduplicator().deduplicate((public_card, portal)).groups[0].item.tender

    assert merged.source == TenderSource.MOS_SUPPLIER


def test_eis_remains_more_authoritative_than_supplier_portal() -> None:
    eis = make_tender(source=TenderSource.EIS, external_id="eis")
    portal = make_tender(source=TenderSource.MOS_SUPPLIER, external_id="portal")

    merged = TenderDeduplicator().deduplicate((portal, eis)).groups[0].item.tender

    assert merged.source == TenderSource.EIS
