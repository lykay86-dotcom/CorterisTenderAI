"""Versioned authenticated API contract for the Moscow Supplier Portal."""

from __future__ import annotations

from dataclasses import dataclass


MOS_SUPPLIER_API_CONTRACT_VERSION = "mos-supplier-api-v1"


@dataclass(frozen=True, slots=True)
class MosSupplierApiContract:
    """Audited limits for the currently documented single-response scope."""

    version: str = MOS_SUPPLIER_API_CONTRACT_VERSION
    max_pages_per_collection: int = 1
    max_page_size: int = 500
    max_response_bytes: int = 50 * 1024 * 1024
    server_pagination_verified: bool = False
    retention_class: str = "collector_evidence"

    def __post_init__(self) -> None:
        if self.max_pages_per_collection != 1:
            raise ValueError("Mos Supplier is limited to one documented response per collection")
        if not 1 <= self.max_page_size <= 500:
            raise ValueError("Mos Supplier page size must be between 1 and 500")
        if not 1 <= self.max_response_bytes <= 50 * 1024 * 1024:
            raise ValueError("Mos Supplier response limit must be between 1 byte and 50 MiB")
        if self.server_pagination_verified:
            raise ValueError("Mos Supplier server pagination has not been verified")


__all__ = ["MOS_SUPPLIER_API_CONTRACT_VERSION", "MosSupplierApiContract"]
