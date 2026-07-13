"""Tests for normalization of public EIS HTML pages."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.tenders.models import (
    TenderProcedureType,
    TenderStatus,
)
from app.tenders.providers.eis import (
    EisAccessBlockedError,
    EisHtmlParser,
)


FIXTURES = Path(__file__).parent / "fixtures"


def test_search_parser_normalizes_44fz_and_223fz_cards() -> None:
    html = (FIXTURES / "eis_search_results.html").read_text(encoding="utf-8")
    parsed = EisHtmlParser(base_url="https://zakupki.gov.ru/").parse_search(html)

    assert parsed.total == 2
    assert len(parsed.items) == 2

    first = parsed.items[0]
    assert first.procurement_number == "0373100000126000001"
    assert first.external_id == "0373100000126000001"
    assert first.title == "Монтаж системы видеонаблюдения и СКУД"
    assert first.customer.name == "ГБУ «Безопасный город»"
    assert first.region == "Москва"
    assert first.law == "44-ФЗ"
    assert first.status == TenderStatus.ACCEPTING_APPLICATIONS
    assert first.procedure_type == TenderProcedureType.ELECTRONIC_AUCTION
    assert first.price is not None
    assert first.price.amount == Decimal("1250000.50")
    assert first.application_deadline is not None

    second = parsed.items[1]
    assert second.law == "223-ФЗ"
    assert second.status == TenderStatus.COMPLETED
    assert second.procedure_type == TenderProcedureType.REQUEST_FOR_QUOTATIONS


def test_document_parser_returns_downloadable_files_only() -> None:
    html = (FIXTURES / "eis_documents.html").read_text(encoding="utf-8")
    documents = EisHtmlParser(base_url="https://zakupki.gov.ru/").parse_documents(html)

    assert [document.name for document in documents] == [
        "Описание объекта закупки.pdf",
        "Форма заявки.docx",
    ]
    assert documents[0].size_bytes == int(1.5 * 1024 * 1024)
    assert documents[0].mime_type == "application/pdf"
    assert documents[1].size_bytes == 256 * 1024


def test_parser_detects_access_protection_page() -> None:
    parser = EisHtmlParser(base_url="https://zakupki.gov.ru/")

    with pytest.raises(EisAccessBlockedError):
        parser.parse_search("<html>Подтвердите, что вы не робот CAPTCHA</html>")
