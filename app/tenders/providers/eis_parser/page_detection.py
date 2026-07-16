"""Classify public EIS pages without guessing a detail adapter."""

from __future__ import annotations

from app.tenders.providers.eis_parser.models import EisPageType


def detect_page_type(html: str) -> EisPageType:
    folded = html.casefold().replace("ё", "е")
    if "captcha" in folded or "подтвердите, что вы не робот" in folded:
        return EisPageType.CAPTCHA
    if "доступ ограничен" in folded or "access denied" in folded or "http 403" in folded:
        return EisPageType.ACCESS_DENIED
    if "технические работы" in folded or "сервис временно недоступен" in folded:
        return EisPageType.MAINTENANCE
    if "search-registry-entry-block" in folded or "registry-entry" in folded:
        return EisPageType.SEARCH
    if (
        "ничего не найдено" in folded
        or "по вашему запросу закупок не найдено" in folded
        or 'data-eis-page="search-empty"' in folded
    ):
        return EisPageType.SEARCH_EMPTY
    if "document-row" in folded or 'data-eis-page="documents"' in folded:
        return EisPageType.DOCUMENTS
    if 'data-eis-law="44-fz"' in folded or "44-фз" in folded:
        return EisPageType.NOTICE_44
    if 'data-eis-law="223-fz"' in folded or "223-фз" in folded:
        return EisPageType.NOTICE_223
    if "внутренняя ошибка" in folded or 'data-eis-page="error"' in folded:
        return EisPageType.ERROR
    return EisPageType.UNKNOWN


__all__ = ["detect_page_type"]
