from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.database.base import json_safe
from app.services.import_service import ImportService
from app.tenders.collector.codec import (
    stable_hash,
    tender_from_payload,
    tender_to_payload,
)
from app.tenders.models import (
    TenderCustomer,
    TenderMoney,
    TenderSource,
    UnifiedTender,
)


@pytest.mark.parametrize(
    "value",
    (
        Decimal("0.1"),
        Decimal("9999999999999999.99"),
        Decimal("0.00000001"),
    ),
)
def test_shared_json_boundary_preserves_decimal_as_string(value: Decimal) -> None:
    payload = json_safe({"amount": value})

    assert payload == {"amount": str(value)}
    assert isinstance(payload["amount"], str)


def test_collector_money_round_trip_preserves_value_and_fingerprint() -> None:
    tender = UnifiedTender(
        source=TenderSource.EIS,
        external_id="exact-money",
        procurement_number="0123456789",
        title="Exact money",
        customer=TenderCustomer("Customer"),
        source_url="https://example.test/tender",
        price=TenderMoney(Decimal("9999999999999999.99")),
    )

    payload = tender_to_payload(tender)
    restored = tender_from_payload(payload)

    assert payload["price"]["amount"] == "9999999999999999.99"
    assert restored.price is not None
    assert restored.price.amount == tender.price.amount
    assert stable_hash(tender_to_payload(restored)) == stable_hash(payload)


class _Repository:
    def __init__(self) -> None:
        self.payload = None

    def create(self, **payload):
        self.payload = payload
        return SimpleNamespace(id=1)


@pytest.mark.parametrize(
    ("source", "expected"),
    (
        ("0.1", Decimal("0.1")),
        (1, Decimal("1")),
        (0.1, Decimal("0.1")),
    ),
)
def test_legacy_import_normalizes_money_without_binary_float(
    source: object,
    expected: Decimal,
) -> None:
    service = ImportService()
    repository = _Repository()
    service.repo = repository

    tender_id = service.create_tender("Tender", nmck=source)

    assert tender_id == 1
    assert repository.payload is not None
    assert repository.payload["nmck"] == expected
    assert isinstance(repository.payload["nmck"], Decimal)


def test_legacy_import_rejects_invalid_money() -> None:
    service = ImportService()
    service.repo = _Repository()

    with pytest.raises(ValueError):
        service.create_tender("Tender", nmck="NaN")


def test_database_serializer_has_no_decimal_float_conversion() -> None:
    source = Path("app/database/base.py").read_text(encoding="utf-8")

    assert "return float(value)" not in source
