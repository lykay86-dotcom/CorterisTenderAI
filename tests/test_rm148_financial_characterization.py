"""RM-148 financial-boundary characterization and regression guards."""

from __future__ import annotations

from decimal import Decimal
import json
from zipfile import ZipFile

from openpyxl import load_workbook
from PySide6.QtWidgets import QApplication
import pytest

from app.core.workflow_database_health import (
    WorkflowDatabaseHealthService,
    WorkflowDatabaseHealthStatus,
)
from app.reporting.workflow_excel import WorkflowExcelExporter
from app.repositories.business_metrics import (
    BusinessMetricsRepository,
    BusinessRecordKind,
    BusinessStatus,
)
from app.ui.business_workflow.dialogs import BusinessRecordDialog
from app.ui.business_workflow.model import WorkflowTableModel
from app.ui.viewmodels.dashboard_viewmodel import DashboardKpiUnit, _format_raw_value


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_v3_repository_preserves_decimal_as_fixed_point_strings(tmp_path) -> None:
    """The v2 float baseline is replaced by exact v3 persistence."""
    path = tmp_path / "business_workflow.json"
    repository = BusinessMetricsRepository(path)

    record = repository.save_record(
        kind=BusinessRecordKind.PROPOSAL,
        tender_id="AUDIT",
        title="Audit",
        status=BusinessStatus.READY,
        total=Decimal("0.10"),
        profit=Decimal("0.01"),
        margin_percent=Decimal("10.00"),
    )
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert repository.SCHEMA_VERSION == 3
    assert record.total == Decimal("0.10")
    assert record.profit == Decimal("0.01")
    assert record.margin_percent == Decimal("10.00")
    assert payload["records"][0]["total"] == "0.10"
    assert payload["records"][0]["currency"] == "RUB"


def test_invalid_repository_number_is_rejected() -> None:
    """Invalid input can no longer become an available zero."""
    with pytest.raises(ValueError):
        BusinessMetricsRepository._number("not-a-number")


def test_ui_financial_precision_uses_one_fixed_point_projection() -> None:
    """Table and dashboard projections preserve the approved two-decimal scale."""
    _app()
    money_spin = BusinessRecordDialog._money_spin()

    assert money_spin.decimals() == 2
    assert WorkflowTableModel._money(Decimal("1.50")) == "1.50 ₽"
    assert _format_raw_value(Decimal("1.50"), DashboardKpiUnit.RUB) == "1.50 ₽"


def test_health_rejects_nonfinite_financial_text(tmp_path) -> None:
    """RM-148 health diagnostics fail closed on non-finite financial values."""
    repository = BusinessMetricsRepository(tmp_path / "business_workflow.json")
    repository.path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "records": [
                    {
                        "id": "legacy",
                        "kind": "proposal",
                        "tender_id": "T-1",
                        "title": "Legacy",
                        "status": "ready",
                        "total": "NaN",
                        "profit": 0,
                        "margin_percent": 0,
                    }
                ],
                "events": [],
            }
        ),
        encoding="utf-8",
    )

    report = WorkflowDatabaseHealthService().inspect(repository)

    assert report.status is WorkflowDatabaseHealthStatus.INVALID
    assert any(issue.code == "record_total_invalid" for issue in report.issues)


def test_xlsx_keeps_numeric_projection_and_exact_fixed_point_metadata(tmp_path) -> None:
    repository = BusinessMetricsRepository(tmp_path / "source.json")
    record = repository.save_record(
        kind=BusinessRecordKind.PROPOSAL,
        tender_id="AUDIT",
        title="Audit",
        status=BusinessStatus.READY,
        total=Decimal("0.10"),
        profit=Decimal("0.01"),
        margin_percent=Decimal("10.00"),
    )
    target = tmp_path / "workflow.xlsx"
    WorkflowExcelExporter().export(target, records=[record])

    workbook = load_workbook(target)
    registry = workbook.worksheets[1]
    with ZipFile(target) as archive:
        xml = archive.read("xl/worksheets/sheet2.xml").decode("utf-8")

    assert registry["F2"].value == 0.1
    assert isinstance(registry["F2"].value, float)
    assert '<c r="F2" s="12" t="n"><v>0.1</v></c>' in xml
    assert workbook["FinancialExact"]["B2"].value == "0.10"
    assert workbook["FinancialExact"]["C2"].value == "0.01"
    assert workbook["FinancialExact"]["E2"].value == "RUB"
    assert workbook["FinancialExact"].sheet_state == "hidden"
