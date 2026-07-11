"""Tests for explainable tender change detection."""

from __future__ import annotations

from app.tenders.collector.change_tracker import (
    TenderChangeTracker,
    TenderChangeType,
)
from app.tenders.collector.models import TenderObservationStatus
from app.tenders.models import TenderStatus
from tests.collector_c3_helpers import make_document, make_tender


def test_detects_price_deadline_status_and_document_changes() -> None:
    old = make_tender(
        amount="1000000.00",
        deadline_day=20,
        documents=(make_document("tz"),),
    )
    new = make_tender(
        amount="1250000.00",
        deadline_day=25,
        status=TenderStatus.CANCELLED,
        documents=(
            make_document("tz"),
            make_document("contract", name="Контракт.pdf"),
        ),
    )

    result = TenderChangeTracker().compare(old, new)
    types = {change.change_type for change in result.changes}

    assert result.status == TenderObservationStatus.CHANGED
    assert TenderChangeType.PRICE_CHANGED in types
    assert TenderChangeType.DEADLINE_EXTENDED in types
    assert TenderChangeType.CANCELLED in types
    assert TenderChangeType.DOCUMENT_ADDED in types


def test_equal_business_fields_are_unchanged() -> None:
    tender = make_tender()

    result = TenderChangeTracker().compare(tender, tender)

    assert result.status == TenderObservationStatus.UNCHANGED
    assert result.changes == ()


def test_missing_previous_record_is_new() -> None:
    result = TenderChangeTracker().compare(None, make_tender())

    assert result.status == TenderObservationStatus.NEW
    assert result.changes[0].change_type == TenderChangeType.NEW
