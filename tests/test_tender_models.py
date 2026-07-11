"""Tests for unified tender domain models."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.tenders.models import (
    TenderCustomer,
    TenderDocument,
    TenderMoney,
    TenderSource,
    TenderStatus,
    UnifiedTender,
)


def test_unified_tender_exposes_stable_identity_keys() -> None:
    tender = UnifiedTender(
        source=TenderSource.EIS,
        external_id=" ABC-123 ",
        procurement_number=" 03731000001 ",
        title="Монтаж видеонаблюдения",
        customer=TenderCustomer(name="Заказчик", inn="7700000000"),
        source_url="https://zakupki.gov.ru/example",
        price=TenderMoney.from_value("1250000.50"),
        status=TenderStatus.ACCEPTING_APPLICATIONS,
    )

    assert tender.identity_key == "eis:abc-123"
    assert tender.cross_source_key == "03731000001"
    assert tender.is_open
    assert tender.price is not None
    assert tender.price.amount == Decimal("1250000.50")


def test_tender_document_and_url_validation() -> None:
    document = TenderDocument(
        id="doc-1",
        name="Техническое задание.pdf",
        url="https://example.org/tz.pdf",
        size_bytes=1024,
    )
    assert document.name.endswith(".pdf")

    with pytest.raises(ValueError):
        TenderDocument(
            id="doc-2",
            name="bad",
            url="file:///tmp/bad",
        )


def test_deadline_cannot_precede_publication() -> None:
    published = datetime(2026, 7, 12, 12, 0)

    with pytest.raises(ValueError):
        UnifiedTender(
            source=TenderSource.EIS,
            external_id="1",
            procurement_number="1",
            title="Тендер",
            customer=TenderCustomer(name="Заказчик"),
            source_url="https://example.org/1",
            published_at=published,
            application_deadline=published - timedelta(minutes=1),
        )
