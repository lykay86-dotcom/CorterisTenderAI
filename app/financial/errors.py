"""Typed failures for the RM-148 financial contract."""


class FinancialError(ValueError):
    """Base deterministic financial-contract failure."""


class FinancialParseError(FinancialError):
    pass


class FinancialPrecisionError(FinancialError):
    pass


class FinancialRangeError(FinancialError):
    pass


class FinancialCurrencyError(FinancialError):
    pass


class FinancialAggregationError(FinancialError):
    pass


class FinancialMigrationError(FinancialError):
    pass


class FinancialExportError(FinancialError):
    pass


class FinancialImportError(FinancialError):
    pass


class FinancialSnapshotConflictError(FinancialError):
    pass


__all__ = [
    "FinancialAggregationError",
    "FinancialCurrencyError",
    "FinancialError",
    "FinancialExportError",
    "FinancialImportError",
    "FinancialMigrationError",
    "FinancialParseError",
    "FinancialPrecisionError",
    "FinancialRangeError",
    "FinancialSnapshotConflictError",
]
