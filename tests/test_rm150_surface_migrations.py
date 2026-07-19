"""Expected-red representative surface bindings for RM-150."""

from __future__ import annotations

from decimal import Decimal
import importlib
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.repositories.business_metrics import (
    BusinessRecordKind,
    BusinessStatus,
    BusinessWorkflowRecord,
)
from app.ui.business_workflow.model import WorkflowTableModel
from app.ui.charts import ChartAxis, ChartAxisScale, ChartKind, ChartPoint, ChartSeries, ChartSpec
from app.ui.charts.table_model import ChartTableModel
from app.ui.dashboard.tender_feed import TenderFeedModel
from app.ui.tender_provider_manager_dialog import TenderProviderManagerDialog
from app.ui.tender_search_results_dialog import TenderSearchResultsDialog
from app.ui.viewmodels.dashboard_viewmodel import RecentTender
from tests.test_tender_provider_manager_dialog import _states
from tests.test_tender_registry import _evaluated_tender, _run


def _tables():
    return importlib.import_module("app.ui.tables")


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_workflow_model_exposes_exact_common_identity_and_decimal_roles() -> None:
    table = _tables()
    record = BusinessWorkflowRecord(
        id="workflow-150",
        kind=BusinessRecordKind.PROPOSAL.value,
        tender_id="tender-150",
        title="Workflow",
        status=BusinessStatus.REVIEW.value,
        total=Decimal("150.25"),
        updated_at="2026-07-20T12:00:00",
    )
    model = WorkflowTableModel([record])

    assert model.index(0, 0).data(table.TableRole.ROW_ID) == table.TableRowId(
        "workflow_record", "workflow-150"
    )
    assert model.index(0, 4).data(table.TableRole.SORT_VALUE) == Decimal("150.25")


def test_dashboard_model_exposes_stable_tender_identity_and_common_column_role() -> None:
    table = _tables()
    tender = RecentTender(
        number="150",
        title="Tender",
        customer="Customer",
        identity_kind="legacy_orm",
        identity_value="orm-150",
    )
    model = TenderFeedModel((tender,))

    assert model.index(0, 0).data(table.TableRole.ROW_ID) == table.TableRowId(
        "legacy_orm", "orm-150"
    )
    assert model.index(0, 0).data(table.TableRole.COLUMN_ID) == table.TableColumnId("number")


def test_chart_model_exposes_series_point_identity_and_exact_decimal_export_role() -> None:
    table = _tables()
    spec = ChartSpec(
        chart_id="rm150",
        kind=ChartKind.BAR,
        title="Chart",
        x_axis=ChartAxis(ChartAxisScale.CATEGORY),
        y_axis=ChartAxis(ChartAxisScale.NUMERIC),
        series=(
            ChartSeries(
                "series-a",
                "Series A",
                (ChartPoint("point-a", "A", Decimal("150.25")),),
            ),
        ),
    )
    model = ChartTableModel(spec)

    assert model.index(0, 0).data(table.TableRole.ROW_ID) == table.TableRowId(
        "chart_point", "series-a:point-a"
    )
    assert model.index(0, model.Y_COLUMN).data(table.TableRole.EXPORT_VALUE) == Decimal("150.25")


def test_search_result_stores_registry_identity_separately_from_compatibility_index() -> None:
    _app()
    table = _tables()
    evaluated = _evaluated_tender(procurement_number="150", external_id="eis-150")
    dialog = TenderSearchResultsDialog(_run(evaluated))
    item = dialog.table.item(0, 0)

    assert item.data(Qt.ItemDataRole.UserRole) == 0
    assert item.data(table.TableRole.ROW_ID) == table.TableRowId("registry", "procurement:150")
    assert dialog.selected_evaluated() is evaluated


def test_provider_rows_expose_common_identity_and_accessible_partial_error_text() -> None:
    _app()
    table = _tables()
    dialog = TenderProviderManagerDialog(_states())
    item = dialog.table.item(0, 0)

    assert item.data(table.TableRole.ROW_ID) == table.TableRowId("provider", "eis")
    assert dialog.table.accessibleName()
    assert dialog.table.accessibleDescription()
    assert dialog.table.item(0, 1).data(Qt.ItemDataRole.AccessibleTextRole)


def test_common_widget_role_values_do_not_replace_legacy_user_role_contracts() -> None:
    _app()
    table = _tables()
    dialog = TenderProviderManagerDialog(_states())
    first = dialog.table.item(0, 0)

    assert first.data(Qt.ItemDataRole.UserRole) == "eis"
    assert first.data(table.TableRole.ROW_ID) == table.TableRowId("provider", "eis")
