"""Tests for the real public EIS provider with injected HTTP transport."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from app.tenders.http_client import HttpResponse
from app.tenders.models import TenderStatus
from app.tenders.provider_base import (
    ProviderHealthStatus,
    TenderSearchQuery,
)
from app.tenders.providers.eis import EisTenderProvider


FIXTURES = Path(__file__).parent / "fixtures"
SEARCH_HTML = (FIXTURES / "eis_search_results.html").read_bytes()
DOCUMENTS_HTML = (FIXTURES / "eis_documents.html").read_bytes()
NOTICE_44_HTML = (FIXTURES / "eis" / "notice_44_current.html").read_bytes()


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get(self, url, *, headers=None, timeout_seconds=20.0):
        self.calls.append(url)
        if "documents.html" in url:
            body = DOCUMENTS_HTML
        elif "common-info.html" in url:
            body = NOTICE_44_HTML
        elif "home.html" in url:
            body = "Единая информационная система в сфере закупок".encode()
        else:
            body = SEARCH_HTML
        return HttpResponse(
            url=url,
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8"},
            body=body,
        )


def test_search_builds_official_public_query_and_filters_results() -> None:
    transport = FakeTransport()
    provider = EisTenderProvider(transport=transport)

    result = provider.search(
        TenderSearchQuery(
            keywords=("видеонаблюдение", "СКУД"),
            excluded_keywords=("продукты",),
            regions=("Москва",),
            laws=("44-ФЗ",),
            date_from=date(2026, 7, 1),
            date_to=date(2026, 7, 31),
            min_price=1_000_000,
            max_price=2_000_000,
            page=2,
            page_size=25,
        )
    )

    assert len(result.items) == 1
    assert result.items[0].status == TenderStatus.ACCEPTING_APPLICATIONS
    assert result.page == 2
    assert result.page_size == 25
    assert any("округлён" in warning for warning in result.warnings)

    parsed = urlparse(transport.calls[0])
    params = parse_qs(parsed.query)
    assert parsed.netloc == "zakupki.gov.ru"
    assert parsed.path.endswith("/extendedsearch/results.html")
    assert params["searchString"] == ["видеонаблюдение СКУД"]
    assert params["pageNumber"] == ["2"]
    assert params["recordsPerPage"] == ["_50"]
    assert params["fz44"] == ["on"]
    assert "fz223" not in params
    assert params["publishDateFrom"] == ["01.07.2026"]


def test_get_tender_and_documents_use_public_pages() -> None:
    transport = FakeTransport()
    provider = EisTenderProvider(transport=transport)

    tender = provider.get_tender("0373100000126000001")
    documents = provider.list_documents("0373100000126000001")

    assert tender.procurement_number == "0373100000126000001"
    assert tender.customer.inn == "7701234567"
    assert len(documents) == 2
    assert any("documents.html" in url for url in transport.calls)


def test_health_check_reports_available_public_eis() -> None:
    provider = EisTenderProvider(transport=FakeTransport())

    health = provider.check_health()

    assert health.status == ProviderHealthStatus.AVAILABLE
    assert health.latency_ms is not None
    assert provider.descriptor.implementation_status == "public_html"
    assert provider.descriptor.capabilities.public_api is False
