"""Public RM-148 financial contract.

The deterministic domain package deliberately stays free of Qt imports.  The
chart adapter is loaded lazily because it is the single optional UI boundary.
"""

from app.financial.contracts import (
    MARGIN_CONTRACT_VERSION,
    NUMERIC_CONTRACT_VERSION,
    SNAPSHOT_CONTRACT_VERSION,
    CurrencyCode,
    FinancialAnalyticsSnapshot,
    FinancialMetricId,
    FinancialMetricValue,
    FinancialUnit,
    FinancialValueState,
    MoneyAmount,
    PercentageValue,
    WorkflowFinancialFact,
)
from app.financial.decimal_codec import (
    MAX_MARGIN,
    MAX_MONEY,
    MONEY_QUANTUM,
    PERCENTAGE_QUANTUM,
    canonical_money,
    canonical_percentage,
    format_money,
    parse_money,
    quantize_money,
    quantize_percentage,
    require_money,
)
from app.financial.errors import (
    FinancialAggregationError,
    FinancialCurrencyError,
    FinancialError,
    FinancialExportError,
    FinancialImportError,
    FinancialMigrationError,
    FinancialParseError,
    FinancialPrecisionError,
    FinancialRangeError,
    FinancialSnapshotConflictError,
)
from app.financial.exporter import snapshot_to_csv_bytes, snapshot_to_json_bytes
from app.financial.margin import derive_margin
from app.financial.metrics import FinancialAnalyticsService


def __getattr__(name: str):
    if name == "FinancialChartAdapter":
        from app.financial.chart_adapter import FinancialChartAdapter

        return FinancialChartAdapter
    raise AttributeError(name)


__all__ = [
    "MARGIN_CONTRACT_VERSION",
    "MAX_MARGIN",
    "MAX_MONEY",
    "MONEY_QUANTUM",
    "NUMERIC_CONTRACT_VERSION",
    "PERCENTAGE_QUANTUM",
    "SNAPSHOT_CONTRACT_VERSION",
    "CurrencyCode",
    "FinancialAggregationError",
    "FinancialAnalyticsService",
    "FinancialAnalyticsSnapshot",
    "FinancialChartAdapter",
    "FinancialCurrencyError",
    "FinancialError",
    "FinancialExportError",
    "FinancialImportError",
    "FinancialMetricId",
    "FinancialMetricValue",
    "FinancialMigrationError",
    "FinancialParseError",
    "FinancialPrecisionError",
    "FinancialRangeError",
    "FinancialSnapshotConflictError",
    "FinancialUnit",
    "FinancialValueState",
    "MoneyAmount",
    "PercentageValue",
    "WorkflowFinancialFact",
    "canonical_money",
    "canonical_percentage",
    "derive_margin",
    "format_money",
    "parse_money",
    "quantize_money",
    "quantize_percentage",
    "require_money",
    "snapshot_to_csv_bytes",
    "snapshot_to_json_bytes",
]
