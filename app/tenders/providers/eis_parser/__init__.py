"""Internal hardening components for the public EIS provider."""

from app.tenders.providers.eis_parser.errors import (
    EisParserStructureChangedError,
    EisParserValidationError,
    EisUnsafeUrlError,
)
from app.tenders.providers.eis_parser.models import (
    EisHealthReport,
    EisLawType,
    EisPageType,
    EisParseDiagnostics,
    EisTenderDetails,
)

__all__ = [
    "EisHealthReport",
    "EisLawType",
    "EisPageType",
    "EisParseDiagnostics",
    "EisParserStructureChangedError",
    "EisParserValidationError",
    "EisTenderDetails",
    "EisUnsafeUrlError",
]
