"""Field provenance and trust resolution tests."""

from __future__ import annotations

from dataclasses import replace

from app.tenders.collector.deduplicator import TenderDeduplicator
from app.tenders.collector.verification import (
    FieldConflictType,
    SourceTrustLevel,
    TenderVerificationService,
    TenderVerificationStatus,
)
from app.tenders.models import TenderSource
from tests.collector_c3_helpers import make_tender


def _verify(*tenders):
    deduplicated = TenderDeduplicator().deduplicate(tenders)
    return TenderVerificationService().verify(
        deduplicated,
        observed_at="2026-07-12T12:00:00+00:00",
    ).items[0]


def test_eis_value_wins_over_aggregator_and_conflict_is_preserved() -> None:
    eis = make_tender(
        source=TenderSource.EIS,
        external_id="eis-1",
        amount="1500000.00",
    )
    aggregator = make_tender(
        source=TenderSource.CUSTOM,
        external_id="aggregator-1",
        amount="2100000.00",
        raw_metadata={
            "aggregator": True,
            "source_kind": "aggregator",
        },
    )

    result = _verify(eis, aggregator)

    assert str(result.tender.price.amount) == "1500000.00"
    selected_price = next(
        item
        for item in result.candidates
        if item.field_name == "price" and item.selected
    )
    assert selected_price.source_id == "eis"
    assert selected_price.trust_level == SourceTrustLevel.EIS
    price_conflict = next(
        item
        for item in result.conflicts
        if item.field_name == "price"
    )
    assert not price_conflict.unresolved
    assert price_conflict.conflict_type == (
        FieldConflictType.OFFICIAL_LOWER_TRUST
    )


def test_equal_priority_official_values_require_manual_resolution() -> None:
    first = make_tender(
        source=TenderSource.MOS_SUPPLIER,
        external_id="mos-1",
        amount="1500000.00",
        raw_metadata={"connection_mode": "official_api_bearer"},
    )
    second = make_tender(
        source=TenderSource.MOS_SUPPLIER,
        external_id="mos-2",
        amount="1600000.00",
        raw_metadata={"connection_mode": "official_api_bearer"},
    )

    result = _verify(first, second)

    price_conflict = next(
        item
        for item in result.conflicts
        if item.field_name == "price"
    )
    assert price_conflict.unresolved
    assert price_conflict.conflict_type == (
        FieldConflictType.OFFICIAL_OFFICIAL
    )
    assert result.status == TenderVerificationStatus.CONFLICT


def test_field_level_official_documentation_overrides_eis() -> None:
    eis = make_tender(
        source=TenderSource.EIS,
        external_id="eis-card",
        amount="1500000.00",
    )
    document_value = make_tender(
        source=TenderSource.CUSTOM,
        external_id="document-value",
        amount="1475000.00",
        raw_metadata={
            "field_provenance": {
                "price": {
                    "source_id": "official_documentation",
                    "source_kind": "official_documentation",
                    "source_url": "https://files.example.org/notice.pdf",
                    "retrieved_at": "2026-07-12T11:30:00+00:00",
                }
            }
        },
    )

    result = _verify(eis, document_value)

    assert str(result.tender.price.amount) == "1475000.00"
    selected = next(
        item
        for item in result.candidates
        if item.field_name == "price" and item.selected
    )
    assert selected.trust_level == (
        SourceTrustLevel.OFFICIAL_DOCUMENTATION
    )
    assert selected.source_id == "official_documentation"


def test_aggregator_only_is_explicitly_marked() -> None:
    aggregator = make_tender(
        source=TenderSource.CUSTOM,
        external_id="aggregator-only",
        raw_metadata={
            "aggregator": True,
            "source_kind": "aggregator",
            "application_security": "0",
            "contract_security": "0",
            "documentation_url": "https://example.org/docs",
        },
    )

    result = _verify(aggregator)

    assert result.status == TenderVerificationStatus.AGGREGATOR_ONLY
    assert all(
        item.trust_level == SourceTrustLevel.AGGREGATOR
        for item in result.selected_candidates
    )
