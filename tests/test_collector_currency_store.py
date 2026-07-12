"""Tests for CBR XML import and persisted exchange-rate history."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.tenders.collector.currency_store import (
    CBR_DAILY_RATES_URL,
    CbrDailyRatesImporter,
    CbrRatesParseError,
    ExchangeRateRepository,
    parse_cbr_daily_xml,
)
from app.tenders.http_client import HttpResponse
from app.tenders.models import TenderMoney


CBR_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<ValCurs Date="11.07.2026" name="Foreign Currency Market">
  <Valute ID="R01235">
    <NumCode>840</NumCode><CharCode>USD</CharCode>
    <Nominal>1</Nominal><Name>US Dollar</Name><Value>78,1234</Value>
  </Valute>
  <Valute ID="R01820">
    <NumCode>392</NumCode><CharCode>JPY</CharCode>
    <Nominal>100</Nominal><Name>Yen</Name><Value>50,0000</Value>
  </Valute>
</ValCurs>
"""


def _quotes():
    return parse_cbr_daily_xml(
        CBR_XML,
        retrieved_at="2026-07-12T06:00:00+00:00",
        source_url=CBR_DAILY_RATES_URL,
    )


def test_cbr_parser_accounts_for_nominal() -> None:
    quotes = _quotes()

    assert len(quotes) == 2
    assert quotes[0].base_currency == "USD"
    assert quotes[0].rate == Decimal("78.1234")
    assert quotes[1].base_currency == "JPY"
    assert quotes[1].rate == Decimal("0.5000")
    assert quotes[1].effective_date == date(2026, 7, 11)
    assert quotes[1].source == "Банк России"


def test_cbr_parser_rejects_unsafe_or_invalid_documents() -> None:
    with pytest.raises(CbrRatesParseError):
        parse_cbr_daily_xml(
            b"<!DOCTYPE x [<!ENTITY y SYSTEM 'file:///etc/passwd'>]><x/>",
            retrieved_at="2026-07-12T06:00:00+00:00",
        )

    duplicate = CBR_XML.replace(b"JPY", b"USD")
    with pytest.raises(CbrRatesParseError):
        parse_cbr_daily_xml(
            duplicate,
            retrieved_at="2026-07-12T06:00:00+00:00",
        )


def test_repository_persists_history_idempotently(tmp_path) -> None:
    repository = ExchangeRateRepository(tmp_path / "registry.sqlite3")
    quotes = _quotes()

    assert repository.save_quotes(quotes) == 2
    assert repository.save_quotes(quotes) == 0

    stored = repository.list_quotes(base_currency="USD")
    assert stored == (quotes[0],)
    book = repository.load_book(effective_to=date(2026, 7, 12))
    conversion = book.convert(
        TenderMoney.from_value("10", currency="USD"),
        "RUB",
        as_of=date(2026, 7, 12),
    )
    assert conversion.converted.amount == Decimal("781.23")


def test_importer_fetches_explicit_date_and_saves_quotes(tmp_path) -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.params: dict[str, str] | None = None

        async def get(self, url, **kwargs):
            self.params = kwargs.get("params")
            return HttpResponse(
                url=url + "?date_req=12/07/2026",
                status_code=200,
                headers={"content-type": "application/xml"},
                body=CBR_XML,
            )

    async def scenario() -> None:
        client = FakeClient()
        repository = ExchangeRateRepository(tmp_path / "registry.sqlite3")
        importer = CbrDailyRatesImporter(client, repository)

        result = await importer.import_date(
            date(2026, 7, 12),
            retrieved_at=datetime(2026, 7, 12, 9, tzinfo=timezone.utc),
        )

        assert client.params == {"date_req": "12/07/2026"}
        assert result.effective_date == date(2026, 7, 11)
        assert result.quote_count == 2
        assert result.inserted_count == 2
        assert len(repository.list_quotes()) == 2

    asyncio.run(scenario())
