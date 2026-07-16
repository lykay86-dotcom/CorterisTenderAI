"""Deterministic EIS law detection, detail routing and domain merge."""

from __future__ import annotations

from dataclasses import replace
import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from app.tenders.models import TenderCustomer, TenderMoney, UnifiedTender
from app.tenders.providers.eis_parser.errors import EisParserStructureChangedError
from app.tenders.providers.eis_parser.models import EisLawType, EisTenderDetails
from app.tenders.providers.eis_parser.notice_223_parser import parse_notice_223
from app.tenders.providers.eis_parser.notice_44_parser import parse_notice_44
from app.tenders.providers.eis_parser.page_detection import detect_page_type
from app.tenders.providers.eis_parser.validation import validate_eis_url


def parse_law(value: str | EisLawType | None) -> EisLawType:
    if isinstance(value, EisLawType):
        return value
    folded = str(value or "").casefold().replace("ё", "е")
    if re.search(r"(?<!\d)44\s*[- ]?фз(?!\d)", folded) or folded == "44-fz":
        return EisLawType.FZ_44
    if re.search(r"(?<!\d)223\s*[- ]?фз(?!\d)", folded) or folded == "223-fz":
        return EisLawType.FZ_223
    return EisLawType.UNKNOWN


def detect_law(*, search_law: str = "", url: str = "", html: str = "") -> EisLawType:
    law = parse_law(search_law)
    if law != EisLawType.UNKNOWN:
        return law
    folded_url = url.casefold()
    if "/notice223/" in folded_url or "fz223" in folded_url:
        return EisLawType.FZ_223
    if "/ea20/" in folded_url or "/order/notice/" in folded_url:
        return EisLawType.FZ_44
    query = parse_qs(urlparse(url).query)
    law = parse_law(" ".join(query.get("law", ()) + query.get("fz", ())))
    if law != EisLawType.UNKNOWN:
        return law
    page_type = detect_page_type(html)
    if page_type.value == "notice_44":
        return EisLawType.FZ_44
    if page_type.value == "notice_223":
        return EisLawType.FZ_223
    return EisLawType.UNKNOWN


def resolve_detail_url(
    *,
    external_id: str,
    source_url: str = "",
    law: EisLawType = EisLawType.UNKNOWN,
    base_url: str = "https://zakupki.gov.ru/",
) -> str:
    normalized = external_id.strip()
    if not normalized:
        raise ValueError("external_id must not be empty")
    if source_url:
        return validate_eis_url(source_url, base_url=base_url)
    if law == EisLawType.UNKNOWN:
        raise EisParserStructureChangedError("EIS law is unknown; detail URL cannot be resolved")
    path = (
        "/epz/order/notice/notice223/common-info.html"
        if law == EisLawType.FZ_223
        else "/epz/order/notice/ea20/view/common-info.html"
    )
    parsed = urlparse(base_url)
    return validate_eis_url(
        urlunparse(parsed._replace(path=path, query=urlencode({"regNumber": normalized}))),
        base_url=base_url,
    )


def parse_detail(
    html: str,
    *,
    source_url: str,
    law: EisLawType,
) -> EisTenderDetails:
    detected = detect_law(search_law=law, url=source_url, html=html)
    if detected == EisLawType.FZ_44:
        return parse_notice_44(html, source_url=source_url)
    if detected == EisLawType.FZ_223:
        return parse_notice_223(html, source_url=source_url)
    raise EisParserStructureChangedError("EIS detail law is unknown; no adapter selected")


def merge_tender_details(search_item: UnifiedTender, details: EisTenderDetails) -> UnifiedTender:
    metadata = dict(search_item.raw_metadata)
    metadata["eis_details"] = details.to_metadata()
    metadata["parser_version"] = details.parser_version
    provenance = dict(metadata.get("field_provenance") or {})
    for field_name in (
        "title",
        "customer",
        "price",
        "published_at",
        "application_deadline",
        "law",
        "classification_codes",
    ):
        provenance[field_name] = {
            "source": "eis",
            "source_kind": "official_eis",
            "parser_version": details.parser_version,
            "source_url": details.source_url,
        }
    metadata["field_provenance"] = provenance
    customer = TenderCustomer(
        name=details.customer_name,
        inn=details.customer_inn or search_item.customer.inn,
        kpp=details.customer_kpp or search_item.customer.kpp,
        region=details.region or search_item.customer.region,
        address=details.customer_address or search_item.customer.address,
    )
    classification_codes = tuple(
        dict.fromkeys(
            (*search_item.classification_codes, *details.okpd2_codes, *details.ktru_codes)
        )
    )
    price = search_item.price
    if details.price is not None:
        price = TenderMoney(details.price, currency=details.currency)
    return replace(
        search_item,
        procurement_number=details.procurement_number,
        external_id=details.procurement_number,
        title=details.title,
        customer=customer,
        source_url=details.source_url,
        published_at=details.published_at or search_item.published_at,
        application_deadline=(details.application_deadline or search_item.application_deadline),
        price=price,
        law=details.law.display_name,
        region=details.region or search_item.region,
        description=details.title,
        classification_codes=classification_codes,
        raw_metadata=metadata,
    )


__all__ = [
    "detect_law",
    "merge_tender_details",
    "parse_detail",
    "parse_law",
    "resolve_detail_url",
]
