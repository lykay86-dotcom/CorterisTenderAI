from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from app.tenders.models import (
    TenderProcedureType,
    TenderSource,
    TenderStatus,
)
from app.tenders.providers.mos_supplier_api import (
    MosSupplierApiConfig,
    MosSupplierApiParser,
    build_mos_supplier_api_url,
    build_mos_supplier_search_payload,
)
from app.tenders.provider_base import TenderSearchQuery


FIXTURES = Path(__file__).parent / "fixtures"
SEARCH_PAYLOAD = json.loads(
    (FIXTURES / "mos_supplier_search_documented_contract.json").read_text(encoding="utf-8")
)
CARD_PAYLOAD = json.loads(
    (FIXTURES / "mos_supplier_card_documented_contract.json").read_text(encoding="utf-8")
)


def test_parser_normalizes_documented_search_contract() -> None:
    parsed = MosSupplierApiParser().parse_search(SEARCH_PAYLOAD)

    assert parsed.total == 2
    assert len(parsed.items) == 2
    tender = parsed.items[0]
    assert tender.source == TenderSource.MOS_SUPPLIER
    assert tender.external_id == "9294080"
    assert tender.procurement_number == "КС-9294080"
    assert tender.price is not None
    assert tender.price.amount == Decimal("1250000.50")
    assert tender.status == TenderStatus.ACCEPTING_APPLICATIONS
    assert tender.procedure_type == TenderProcedureType.REQUEST_FOR_QUOTATIONS
    assert tender.customer.inn == "7701234567"
    assert tender.region == "Москва"
    assert tender.classification_codes == (
        "26.40.33.110",
        "43.21.10.290",
    )
    assert tender.documents[0].name == "Техническое задание.pdf"
    assert tender.documents[0].url.endswith("id=260360731")


def test_parser_normalizes_documented_card_contract() -> None:
    tender = MosSupplierApiParser().parse_card(CARD_PAYLOAD)

    assert tender.external_id == "9294080"
    assert tender.source_url == "https://zakupki.mos.ru/auction/9294080"
    assert tender.published_at is not None
    assert tender.application_deadline is not None
    assert [item.name for item in tender.documents] == [
        "Техническое задание.pdf",
        "Проект договора.docx",
    ]
    assert all(item.url.startswith("https://zakupki.mos.ru/") for item in tender.documents)


def test_search_payload_uses_documented_name_and_price_filters() -> None:
    payload = build_mos_supplier_search_payload(
        TenderSearchQuery(
            keywords=("видеонаблюдение", "СКУД"),
            min_price=100000,
            max_price=2000000,
            extra={
                "customer_inn": "7701234567",
                "mos_api_payload": {"filter": {"status": [1, 2]}},
            },
        )
    )

    assert payload["filter"] == {
        "name": "видеонаблюдение СКУД",
        "inn": "7701234567",
        "status": [1, 2],
    }
    assert payload["startprice"] == {
        "start": [100000],
        "end": [2000000],
        "isNotNull": True,
    }


def test_search_payload_skips_ruble_filter_for_foreign_currency() -> None:
    payload = build_mos_supplier_search_payload(
        TenderSearchQuery(
            keywords=("оборудование",),
            min_price=100,
            price_currency="USD",
        )
    )

    assert "startprice" not in payload


def test_api_url_contains_encoded_json_query() -> None:
    url = build_mos_supplier_api_url(
        MosSupplierApiConfig().search_url,
        {"filter": {"name": "видеонаблюдение"}},
    )

    assert url.startswith("https://api.zakupki.mos.ru/")
    assert "%7B" in url
    assert "%D0%B2" in url
