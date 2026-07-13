"""Field provenance and trust resolution tests."""

from __future__ import annotations


from app.tenders.collector.deduplicator import TenderDeduplicator
from app.tenders.collector.verification import (
    FieldConflictType,
    SourceTrustLevel,
    TenderVerificationService,
    TenderVerificationStatus,
)
from app.tenders.models import TenderSource, TenderStatus
from tests.collector_c3_helpers import make_tender


def _verify(*tenders):
    deduplicated = TenderDeduplicator().deduplicate(tenders)
    return (
        TenderVerificationService()
        .verify(
            deduplicated,
            observed_at="2026-07-12T12:00:00+00:00",
        )
        .items[0]
    )


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
        item for item in result.candidates if item.field_name == "price" and item.selected
    )
    assert selected_price.source_id == "eis"
    assert selected_price.trust_level == SourceTrustLevel.EIS
    price_conflict = next(item for item in result.conflicts if item.field_name == "price")
    assert not price_conflict.unresolved
    assert price_conflict.conflict_type == (FieldConflictType.OFFICIAL_LOWER_TRUST)


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

    price_conflict = next(item for item in result.conflicts if item.field_name == "price")
    assert price_conflict.unresolved
    assert price_conflict.conflict_type == (FieldConflictType.OFFICIAL_OFFICIAL)
    assert result.status == TenderVerificationStatus.CONFLICT


def test_deadline_conflict_keeps_eis_over_aggregator() -> None:
    eis = make_tender(
        source=TenderSource.EIS,
        external_id="eis-deadline",
        deadline_day=20,
    )
    aggregator = make_tender(
        source=TenderSource.CUSTOM,
        external_id="aggregator-deadline",
        deadline_day=25,
        raw_metadata={
            "aggregator": True,
            "source_kind": "aggregator",
        },
    )

    result = _verify(eis, aggregator)
    conflict = next(item for item in result.conflicts if item.field_name == "application_deadline")
    selected = next(
        item
        for item in result.candidates
        if item.field_name == "application_deadline" and item.selected
    )

    assert result.tender.application_deadline == eis.application_deadline
    assert selected.source_id == "eis"
    assert not conflict.unresolved
    assert conflict.conflict_type == (FieldConflictType.OFFICIAL_LOWER_TRUST)


def test_status_conflict_between_official_sources_is_unresolved() -> None:
    accepting = make_tender(
        source=TenderSource.MOS_SUPPLIER,
        external_id="mos-status-1",
        status=TenderStatus.ACCEPTING_APPLICATIONS,
        raw_metadata={
            "connection_mode": "official_api_bearer",
            "retrieved_at": "2026-07-12T10:00:00+00:00",
        },
    )
    cancelled = make_tender(
        source=TenderSource.MOS_SUPPLIER,
        external_id="mos-status-2",
        status=TenderStatus.CANCELLED,
        raw_metadata={
            "connection_mode": "official_api_bearer",
            "retrieved_at": "2026-07-12T11:00:00+00:00",
        },
    )

    result = _verify(accepting, cancelled)
    conflict = next(item for item in result.conflicts if item.field_name == "status")

    assert result.tender.status == TenderStatus.CANCELLED
    assert conflict.unresolved
    assert conflict.conflict_type == FieldConflictType.OFFICIAL_OFFICIAL
    assert result.status == TenderVerificationStatus.CONFLICT


def test_latest_official_variant_is_selected_at_equal_priority() -> None:
    older = make_tender(
        source=TenderSource.EIS,
        external_id="eis-older",
        amount="1500000.00",
        raw_metadata={
            "retrieved_at": "2026-07-12T09:00:00+00:00",
        },
    )
    newer = make_tender(
        source=TenderSource.EIS,
        external_id="eis-newer",
        amount="1600000.00",
        raw_metadata={
            "retrieved_at": "2026-07-12T12:00:00+00:00",
        },
    )

    result = _verify(older, newer)
    selected = next(
        item for item in result.candidates if item.field_name == "price" and item.selected
    )

    assert str(result.tender.price.amount) == "1600000.00"
    assert selected.retrieved_at == "2026-07-12T12:00:00+00:00"
    assert any(item.field_name == "price" and item.unresolved for item in result.conflicts)


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
        item for item in result.candidates if item.field_name == "price" and item.selected
    )
    assert selected.trust_level == (SourceTrustLevel.OFFICIAL_DOCUMENTATION)
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
        item.trust_level == SourceTrustLevel.AGGREGATOR for item in result.selected_candidates
    )
