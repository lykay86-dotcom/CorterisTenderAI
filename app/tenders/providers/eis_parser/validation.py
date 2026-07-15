"""Fail-closed validation and URL safety for public EIS pages."""

from __future__ import annotations

import ipaddress
from urllib.parse import urljoin, urlparse, urlunparse

from app.tenders.providers.eis_parser.errors import (
    EisParserValidationError,
    EisUnsafeUrlError,
)
from app.tenders.providers.eis_parser.models import EisLawType, EisTenderDetails


ALLOWED_EIS_HOSTS = frozenset({"zakupki.gov.ru", "www.zakupki.gov.ru"})


def validate_eis_url(url: str, *, base_url: str = "https://zakupki.gov.ru/") -> str:
    absolute = urljoin(base_url, url.strip())
    parsed = urlparse(absolute)
    host = (parsed.hostname or "").casefold().rstrip(".")
    if parsed.scheme != "https" or not host:
        raise EisUnsafeUrlError("EIS URL must be an absolute HTTPS URL")
    if parsed.username or parsed.password:
        raise EisUnsafeUrlError("EIS URL must not contain credentials")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None or host not in ALLOWED_EIS_HOSTS:
        raise EisUnsafeUrlError(f"EIS URL host is not allowed: {host or '<empty>'}")
    return urlunparse(parsed._replace(fragment=""))


def validate_details(details: EisTenderDetails) -> EisTenderDetails:
    required = {
        "procurement_number": details.procurement_number,
        "title": details.title,
        "source_url": details.source_url,
        "customer.name": details.customer_name,
    }
    missing = [name for name, value in required.items() if not value.strip()]
    if details.law == EisLawType.UNKNOWN:
        missing.append("law")
    if missing:
        raise EisParserValidationError(
            "EIS detail page misses mandatory fields: " + ", ".join(missing)
        )
    validate_eis_url(details.source_url)
    return details


__all__ = ["ALLOWED_EIS_HOSTS", "validate_details", "validate_eis_url"]
