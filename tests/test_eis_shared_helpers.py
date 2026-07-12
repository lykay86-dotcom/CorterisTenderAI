from __future__ import annotations

from datetime import date
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

from app.tenders.models import (
    TenderCustomer,
    TenderMoney,
    TenderSource,
    UnifiedTender,
)
from app.tenders.provider_base import TenderSearchQuery
from app.tenders.providers.eis import (
    build_eis_search_url,
    eis_documents_url,
    matches_eis_query,
)


def test_shared_search_builder_keeps_sync_and_async_contract() -> None:
    url, page_size = build_eis_search_url(
        TenderSearchQuery(
            keywords=("видеонаблюдение",),
            laws=("44-ФЗ",),
            date_from=date(2026, 7, 1),
            page=2,
            page_size=25,
        )
    )

    params = parse_qs(urlparse(url).query)
    assert page_size == 50
    assert params["searchString"] == ["видеонаблюдение"]
    assert params["fz44"] == ["on"]
    assert "fz223" not in params
    assert params["publishDateFrom"] == ["01.07.2026"]


def test_shared_filter_compares_decimal_without_float_conversion() -> None:
    tender = UnifiedTender(
        source=TenderSource.EIS,
        external_id="1",
        procurement_number="1",
        title="Монтаж видеонаблюдения",
        customer=TenderCustomer(name="Заказчик"),
        source_url="https://zakupki.gov.ru/tender/1",
        price=TenderMoney(amount=Decimal("1000000.01")),
    )

    assert matches_eis_query(
        tender,
        TenderSearchQuery(min_price=1_000_000),
    )
    assert not matches_eis_query(
        tender,
        TenderSearchQuery(max_price=1_000_000),
    )


def test_search_builder_preserves_exact_decimal_boundaries() -> None:
    url, _ = build_eis_search_url(
        TenderSearchQuery(
            min_price="9007199254740993.01",
            max_price=Decimal("9007199254740993.09"),
        )
    )

    params = parse_qs(urlparse(url).query)
    assert params["priceFromGeneral"] == ["9007199254740993.01"]
    assert params["priceToGeneral"] == ["9007199254740993.09"]


def test_eis_does_not_apply_ruble_filter_to_foreign_currency() -> None:
    query = TenderSearchQuery(
        min_price="100",
        max_price="200",
        price_currency="USD",
    )
    url, _ = build_eis_search_url(query)
    params = parse_qs(urlparse(url).query)
    tender = UnifiedTender(
        source=TenderSource.EIS,
        external_id="usd-1",
        procurement_number="usd-1",
        title="Оборудование",
        customer=TenderCustomer(name="Заказчик"),
        source_url="https://zakupki.gov.ru/tender/usd-1",
        price=TenderMoney.from_value("150", currency="RUB"),
    )

    assert "priceFromGeneral" not in params
    assert "priceToGeneral" not in params
    assert not matches_eis_query(tender, query)


def test_documents_url_preserves_procurement_number() -> None:
    source = (
        "https://zakupki.gov.ru/epz/order/notice/ea20/view/"
        "common-info.html?regNumber=0373100000126000001"
    )
    rendered = eis_documents_url(source)

    assert "/documents.html" in rendered
    assert "regNumber=0373100000126000001" in rendered
