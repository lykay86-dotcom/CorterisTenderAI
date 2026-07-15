from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.tenders.collector.codec import tender_from_payload, tender_to_payload
from app.tenders.models import TenderCustomer, TenderSource, UnifiedTender, is_timezone_aware
from app.tenders.providers.eis import (
    EisAccessBlockedError,
    EisHtmlParser,
    EisParserStructureChangedError,
)
from app.tenders.providers.eis_parser.detail_router import (
    detect_law,
    merge_tender_details,
    parse_detail,
    resolve_detail_url,
)
from app.tenders.providers.eis_parser.errors import (
    EisParserValidationError,
    EisUnsafeUrlError,
)
from app.tenders.providers.eis_parser.models import EisLawType, EisPageType
from app.tenders.providers.eis_parser.notice_223_parser import parse_notice_223
from app.tenders.providers.eis_parser.notice_44_parser import parse_notice_44
from app.tenders.providers.eis_parser.page_detection import detect_page_type
from app.tenders.providers.eis_parser.snapshots import EisSnapshotWriter
from app.tenders.providers.eis_parser.search_parser import build_search_diagnostics
from app.tenders.providers.eis_parser.validation import validate_eis_url


FIXTURES = Path(__file__).parent / "fixtures" / "eis"
BASE_URL = "https://zakupki.gov.ru/"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("fixture", "law"),
    (("search_44_current.html", "44-ФЗ"), ("search_223_current.html", "223-ФЗ")),
)
def test_search_parser_has_versioned_diagnostics_and_aware_dates(
    fixture: str,
    law: str,
) -> None:
    parsed = EisHtmlParser(base_url=BASE_URL).parse_search(_fixture(fixture))

    assert len(parsed.items) == 1
    assert parsed.items[0].law == law
    assert parsed.diagnostics is not None
    assert parsed.diagnostics.parser_version == "eis-search-v3"
    assert EisHtmlParser.documents_parser_version == "eis-documents-v2"
    assert parsed.diagnostics.cards_detected == 1
    assert parsed.diagnostics.parse_success_rate == 1.0
    if parsed.items[0].published_at is not None:
        assert is_timezone_aware(parsed.items[0].published_at)


def test_search_parser_supports_mixed_and_explicit_empty_pages() -> None:
    parser = EisHtmlParser(base_url=BASE_URL)
    mixed = parser.parse_search(_fixture("search_mixed_current.html"))
    empty = parser.parse_search(_fixture("search_empty.html"))

    assert [item.law for item in mixed.items] == ["44-ФЗ", "223-ФЗ"]
    assert empty.items == ()
    assert empty.diagnostics is not None
    assert empty.diagnostics.page_type == EisPageType.SEARCH_EMPTY


def test_search_diagnostics_enforces_success_rate_threshold() -> None:
    with pytest.raises(EisParserStructureChangedError):
        build_search_diagnostics(
            _fixture("search_mixed_current.html"),
            cards_detected=4,
            cards_parsed=2,
            total=4,
            missing_title_count=1,
            missing_customer_count=1,
            missing_price_count=0,
            unknown_law_count=0,
            warnings=("two cards failed",),
        )


@pytest.mark.parametrize(
    "fixture",
    ("search_structure_changed.html", "maintenance.html", "malformed.html"),
)
def test_search_parser_fails_closed_on_structural_drift(fixture: str) -> None:
    with pytest.raises(EisParserStructureChangedError):
        EisHtmlParser(base_url=BASE_URL).parse_search(_fixture(fixture))


@pytest.mark.parametrize("fixture", ("captcha.html", "access_denied.html"))
def test_search_parser_reports_access_protection(fixture: str) -> None:
    with pytest.raises(EisAccessBlockedError):
        EisHtmlParser(base_url=BASE_URL).parse_search(_fixture(fixture))


def test_law_detection_uses_search_then_url_then_html() -> None:
    assert detect_law(search_law="44-ФЗ", url="", html="") == EisLawType.FZ_44
    assert (
        detect_law(url="https://zakupki.gov.ru/epz/order/notice/notice223/common-info.html")
        == EisLawType.FZ_223
    )
    assert detect_law(html=_fixture("notice_44_current.html")) == EisLawType.FZ_44
    assert detect_law() == EisLawType.UNKNOWN


def test_notice_44_parser_preserves_decimal_identity_and_timezone() -> None:
    details = parse_notice_44(
        _fixture("notice_44_current.html"),
        source_url=(
            "https://zakupki.gov.ru/epz/order/notice/ea20/view/"
            "common-info.html?regNumber=0373100000126000001"
        ),
    )

    assert details.customer_inn == "7701234567"
    assert details.customer_kpp == "770101001"
    assert details.organization_code == "03731000001"
    assert details.price == Decimal("1250000.50")
    assert details.bid_security == Decimal("12500.01")
    assert details.advance_percent == Decimal("15.5")
    assert details.published_at is not None and is_timezone_aware(details.published_at)
    assert details.okpd2_codes == ("26.40.33.190",)
    assert details.ktru_codes == ("26.40.33.190-00000001",)
    assert details.parser_version == "eis-notice-44-v1"


def test_notice_223_parser_preserves_large_decimal_and_lots() -> None:
    details = parse_notice_223(
        _fixture("notice_223_current.html"),
        source_url=(
            "https://zakupki.gov.ru/epz/order/notice/notice223/"
            "common-info.html?regNumber=32616073849"
        ),
    )

    assert details.price == Decimal("9007199254740993.09")
    assert details.organization_code == "ORG-223-01"
    assert details.lots == (
        {"name": "Серверы"},
        {"name": "системы хранения данных"},
    )
    assert details.parser_version == "eis-notice-223-v1"


def test_detail_parser_fails_closed_when_customer_is_missing() -> None:
    html = """
    <html><body data-eis-law="44-FZ">
      <div data-field="Номер закупки">0373100000126000009</div>
      <div data-field="Наименование закупки">Поставка</div>
    </body></html>
    """
    with pytest.raises(EisParserValidationError, match="customer.name"):
        parse_detail(
            html,
            source_url="https://zakupki.gov.ru/notice",
            law=EisLawType.FZ_44,
        )


def test_unknown_law_never_selects_random_detail_adapter() -> None:
    with pytest.raises(EisParserStructureChangedError, match="unknown"):
        parse_detail(
            "<html><body>public page</body></html>",
            source_url="https://zakupki.gov.ru/notice",
            law=EisLawType.UNKNOWN,
        )


@pytest.mark.parametrize(
    ("fixture", "law"),
    (
        ("notice_44_missing_optional_fields.html", EisLawType.FZ_44),
        ("notice_223_missing_optional_fields.html", EisLawType.FZ_223),
    ),
)
def test_optional_detail_fields_remain_none(fixture: str, law: EisLawType) -> None:
    details = parse_detail(
        _fixture(fixture),
        source_url="https://zakupki.gov.ru/notice",
        law=law,
    )
    assert details.customer_inn is None
    assert details.bid_security is None
    assert details.requirements == ()


@pytest.mark.parametrize(
    "url",
    (
        "file:///etc/passwd",
        "http://localhost/test",
        "http://127.0.0.1/test",
        "https://10.0.0.1/test",
        "https://example.com/test",
        "https://user:secret@zakupki.gov.ru/test",
    ),
)
def test_url_validation_rejects_non_eis_targets(url: str) -> None:
    with pytest.raises(EisUnsafeUrlError):
        validate_eis_url(url)


def test_router_merges_details_without_database_schema_change() -> None:
    search_item = UnifiedTender(
        source=TenderSource.EIS,
        external_id="0373100000126000001",
        procurement_number="0373100000126000001",
        title="Краткое название",
        customer=TenderCustomer(name="ГБУ «Безопасный город»"),
        source_url=resolve_detail_url(
            external_id="0373100000126000001",
            law=EisLawType.FZ_44,
        ),
    )
    details = parse_notice_44(_fixture("notice_44_current.html"), source_url=search_item.source_url)
    merged = merge_tender_details(search_item, details)

    assert merged.customer.inn == "7701234567"
    assert merged.price is not None and merged.price.amount == Decimal("1250000.50")
    assert merged.raw_metadata["parser_version"] == "eis-notice-44-v1"
    assert "field_provenance" in merged.raw_metadata

    restored = tender_from_payload(tender_to_payload(merged))
    assert restored.customer.inn == "7701234567"
    assert restored.price is not None
    assert restored.price.amount == Decimal("1250000.50")
    assert restored.raw_metadata["parser_version"] == "eis-notice-44-v1"


def test_page_detection_distinguishes_operational_failures() -> None:
    assert detect_page_type(_fixture("captcha.html")) == EisPageType.CAPTCHA
    assert detect_page_type(_fixture("access_denied.html")) == EisPageType.ACCESS_DENIED
    assert detect_page_type(_fixture("maintenance.html")) == EisPageType.MAINTENANCE


def test_snapshot_writer_is_opt_in_and_metadata_is_allowlisted(tmp_path: Path) -> None:
    assert EisSnapshotWriter(None).save_html("search", "<html></html>") is None
    writer = EisSnapshotWriter(tmp_path)
    html_path = writer.save_html("notice_44", "<html>public body</html>")
    metadata_path = writer.save_metadata(
        "notice_44",
        {
            "url": "https://zakupki.gov.ru/test",
            "parser_version": "eis-notice-44-v1",
            "Authorization": "Bearer forbidden",
            "cookies": "forbidden",
        },
    )

    assert html_path is not None and html_path.exists()
    assert metadata_path is not None and metadata_path.exists()
    rendered = metadata_path.read_text(encoding="utf-8")
    assert "Authorization" not in rendered
    assert "Bearer forbidden" not in rendered
    assert "cookies" not in rendered
