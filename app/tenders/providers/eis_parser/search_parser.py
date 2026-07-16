"""Structural validation and diagnostics for EIS search pages."""

from __future__ import annotations

from app.tenders.providers.eis_parser.errors import EisParserStructureChangedError
from app.tenders.providers.eis_parser.models import EisPageType, EisParseDiagnostics
from app.tenders.providers.eis_parser.page_detection import detect_page_type


SEARCH_PARSER_VERSION = "eis-search-v3"


def build_search_diagnostics(
    html: str,
    *,
    cards_detected: int,
    cards_parsed: int,
    total: int | None,
    missing_title_count: int,
    missing_customer_count: int,
    missing_price_count: int,
    unknown_law_count: int,
    warnings: tuple[str, ...],
) -> EisParseDiagnostics:
    page_type = detect_page_type(html)
    failed = max(0, cards_detected - cards_parsed)
    success_rate = cards_parsed / cards_detected if cards_detected else 1.0
    diagnostics = EisParseDiagnostics(
        page_type=page_type,
        parser_version=SEARCH_PARSER_VERSION,
        cards_detected=cards_detected,
        cards_parsed=cards_parsed,
        cards_failed=failed,
        parse_success_rate=success_rate,
        missing_title_count=missing_title_count,
        missing_customer_count=missing_customer_count,
        missing_price_count=missing_price_count,
        unknown_law_count=unknown_law_count,
        warnings=warnings,
    )
    if page_type in {EisPageType.MAINTENANCE, EisPageType.ERROR, EisPageType.UNKNOWN}:
        raise EisParserStructureChangedError(
            f"Unrecognized or unavailable EIS search page: {page_type.value}"
        )
    if total is not None and total > 0 and cards_detected == 0:
        raise EisParserStructureChangedError("EIS reports results but no search cards were found")
    if cards_detected and cards_parsed == 0:
        raise EisParserStructureChangedError("EIS search cards were found but none were parsed")
    if cards_detected >= 3 and success_rate < 0.70:
        raise EisParserStructureChangedError(
            f"EIS search parse success rate is below 0.70: {success_rate:.2f}"
        )
    if cards_detected == 0 and page_type != EisPageType.SEARCH_EMPTY:
        raise EisParserStructureChangedError("EIS search result container is missing")
    return diagnostics


__all__ = ["SEARCH_PARSER_VERSION", "build_search_diagnostics"]
