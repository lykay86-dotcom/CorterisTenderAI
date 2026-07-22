"""Versioned public-HTML contract for the EIS reference adapter."""

from __future__ import annotations

from dataclasses import dataclass


EIS_PUBLIC_HTML_CONTRACT_VERSION = "eis-public-html-v1"


@dataclass(frozen=True, slots=True)
class EisPublicHtmlContract:
    """Audited limits for the unauthenticated EIS search surface."""

    version: str = EIS_PUBLIC_HTML_CONTRACT_VERSION
    max_pages_per_collection: int = 20
    max_page_size: int = 500
    max_response_bytes: int = 50 * 1024 * 1024
    retention_class: str = "collector_evidence"

    def __post_init__(self) -> None:
        if not 1 <= self.max_pages_per_collection <= 200:
            raise ValueError("EIS page limit must be between 1 and 200")
        if not 1 <= self.max_page_size <= 500:
            raise ValueError("EIS page size must be between 1 and 500")
        if not 1 <= self.max_response_bytes <= 50 * 1024 * 1024:
            raise ValueError("EIS response limit must be between 1 byte and 50 MiB")


__all__ = ["EIS_PUBLIC_HTML_CONTRACT_VERSION", "EisPublicHtmlContract"]
