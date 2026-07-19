"""One-snapshot parity across RM-148 workflow financial surfaces."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json

from PySide6.QtWidgets import QApplication

from app.financial import FinancialMetricId, snapshot_to_csv_bytes, snapshot_to_json_bytes
from app.repositories.business_metrics import (
    BusinessMetricsRepository,
    BusinessRecordKind,
    BusinessStatus,
)
from app.ui.business_workflow.model import WorkflowTableModel
from app.ui.pages.tender_analytics_page import TenderAnalyticsPage
from app.ui.viewmodels.dashboard_viewmodel import DashboardKpiUnit, _format_raw_value


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_one_snapshot_has_exact_table_kpi_chart_and_export_value(tmp_path) -> None:
    _app()
    repository = BusinessMetricsRepository(tmp_path / "workflow.json")
    record = repository.save_record(
        kind=BusinessRecordKind.PROPOSAL,
        tender_id="T-148",
        title="Exact",
        status=BusinessStatus.READY,
        total=Decimal("1.50"),
        profit=Decimal("0.25"),
    )
    snapshot = repository.financial_snapshot(
        generated_at=datetime(2026, 7, 19, 9, tzinfo=timezone.utc)
    )
    profit = snapshot.metric(FinancialMetricId.POTENTIAL_PROFIT)

    page = TenderAnalyticsPage()
    page.set_financial_snapshot(snapshot)
    chart = page._financial_charts[FinancialMetricId.POTENTIAL_PROFIT.value].canvas.spec
    json_payload = json.loads(snapshot_to_json_bytes(snapshot))
    json_metric = next(item for item in json_payload["metrics"] if item["metric_id"] == "fa-02")

    assert WorkflowTableModel._money(record.profit) == "0.25 ₽"
    assert _format_raw_value(profit.exact_value, DashboardKpiUnit.RUB) == "0.25 ₽"
    assert chart.series[0].points[0].y == Decimal("0.25")
    assert page.financial_table.item(1, 1).text() == "0.25"
    assert json_metric["value"] == "0.25"
    assert b"fa-02,workflow-potential-profit-v1,0.25,RUB,money" in snapshot_to_csv_bytes(snapshot)
    assert profit.contributor_ids == (record.id,)
    assert snapshot.fingerprint in snapshot_to_json_bytes(snapshot).decode("utf-8")
