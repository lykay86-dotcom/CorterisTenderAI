"""Typed EIS parser failures used by sync and async facades."""

from app.tenders.provider_base import TenderProviderError


class EisParserStructureChangedError(TenderProviderError):
    """Raised when a public EIS page no longer satisfies its known contract."""


class EisParserValidationError(TenderProviderError):
    """Raised when parsed detail data misses a mandatory fact."""


class EisUnsafeUrlError(TenderProviderError):
    """Raised before a request to a URL outside the public EIS allowlist."""


__all__ = [
    "EisParserStructureChangedError",
    "EisParserValidationError",
    "EisUnsafeUrlError",
]
