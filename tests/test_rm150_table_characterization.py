"""Passing characterization for the table seams inherited by RM-150."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTableWidgetItem

from app.core.workflow_backup import WorkflowBackupService
from app.core.workflow_backup_catalog import WorkflowBackupCatalogService
from app.repositories.business_metrics import (
    BusinessMetricsRepository,
    BusinessRecordKind,
    BusinessStatus,
    BusinessWorkflowRecord,
)
from app.tenders.tender_registry import TenderRegistryRepository
from app.ui.business_workflow.backup_center_dialog import WorkflowBackupCenterDialog
from app.ui.business_workflow.model import (
    WorkflowArchiveMode,
    WorkflowFilterProxyModel,
    WorkflowRole,
    WorkflowTableModel,
)
from app.ui.charts import (
    ChartAxis,
    ChartAxisScale,
    ChartColorRole,
    ChartKind,
    ChartPoint,
    ChartSeries,
    ChartSpec,
)
from app.ui.charts.table_model import ChartTableModel
from app.ui.dashboard.data_state import DataState, DataStateKind
from app.ui.dashboard.tender_feed import TenderFeed, TenderFeedModel
from app.ui.tender_provider_manager_dialog import TenderProviderManagerDialog
from app.ui.tender_registry_dialog import TenderRegistryDialog
from app.ui.tender_search_results_dialog import TenderSearchResultsDialog
from app.ui.viewmodels.dashboard_viewmodel import RecentTender
from tests.test_rm127_tender_workspace_contract import _page
from tests.test_tender_provider_manager_dialog import _states
from tests.test_tender_registry import _evaluated_tender, _run


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _workflow_record(record_id: str, *, updated_at: str, total: str) -> BusinessWorkflowRecord:
    return BusinessWorkflowRecord(
        id=record_id,
        kind=BusinessRecordKind.PROPOSAL.value,
        tender_id=f"tender-{record_id}",
        title=f"Workflow {record_id}",
        status=BusinessStatus.REVIEW.value,
        total=Decimal(total),
        profit=Decimal("1.25"),
        margin_percent=Decimal("2.50"),
        updated_at=updated_at,
    )


def test_workflow_model_preserves_exact_record_and_decimal_sort_values() -> None:
    _app()
    older = _workflow_record("record-a", updated_at="2026-07-18T12:00:00", total="10.10")
    newer = _workflow_record("record-b", updated_at="2026-07-19T12:00:00", total="2.20")
    model = WorkflowTableModel([older, newer])

    assert model.records == (newer, older)
    assert model.index(0, 0).data(WorkflowRole.RECORD) is newer
    assert model.index(0, 4).data(WorkflowRole.SORT) == Decimal("2.20")
    assert isinstance(model.index(0, 4).data(WorkflowRole.SORT), Decimal)


def test_workflow_proxy_combines_exact_id_scope_and_text_filter() -> None:
    _app()
    first = _workflow_record("record-a", updated_at="2026-07-18T12:00:00", total="10")
    second = _workflow_record("record-b", updated_at="2026-07-19T12:00:00", total="20")
    model = WorkflowTableModel([first, second])
    proxy = WorkflowFilterProxyModel()
    proxy.setSourceModel(model)
    proxy.set_archive_mode(WorkflowArchiveMode.ALL)
    proxy.set_record_scope(("record-a",))
    proxy.set_search("WORKFLOW RECORD-A")

    assert proxy.rowCount() == 1
    assert proxy.index(0, 0).data(WorkflowRole.RECORD).id == "record-a"


def test_dashboard_feed_keeps_number_role_and_explicit_non_row_states() -> None:
    _app()
    tender = RecentTender(
        number="0373100000126000150",
        title="Characterization tender",
        customer="Corteris",
        nmck="150.00",
        score=80,
        recommendation="owner supplied",
        status="critical owner supplied",
    )
    model = TenderFeedModel((tender,))

    assert model.index(0, 0).data(Qt.ItemDataRole.UserRole) == tender.number
    assert "owner supplied" in model.index(0, 0).data(Qt.ItemDataRole.ToolTipRole)

    feed = TenderFeed(())
    assert feed.data_state.kind is DataStateKind.EMPTY
    assert feed.model.rowCount() == 0
    assert feed.table.isHidden()

    feed.set_tenders((tender,))
    feed.set_data_state(DataState.partial("one provider unavailable"))
    assert feed.model.rowCount() == 1
    assert not feed.table.isHidden()
    assert not feed.state_panel.isHidden()


def test_chart_table_keeps_source_order_ids_decimal_and_accessible_text() -> None:
    spec = ChartSpec(
        chart_id="rm150-characterization",
        kind=ChartKind.BAR,
        title="Characterization",
        x_axis=ChartAxis(ChartAxisScale.CATEGORY, title="Category"),
        y_axis=ChartAxis(ChartAxisScale.NUMERIC, title="Value", unit="RUB"),
        series=(
            ChartSeries(
                series_id="series-a",
                label="Series A",
                color_role=ChartColorRole.CHART_1,
                points=(
                    ChartPoint("point-b", "B", Decimal("2.20")),
                    ChartPoint("point-a", "A", Decimal("1.10")),
                ),
            ),
        ),
    )
    model = ChartTableModel(spec)

    assert tuple(model.row_record(row).point_id for row in range(model.rowCount())) == (
        "point-b",
        "point-a",
    )
    assert model.row_record(0).y == Decimal("2.20")
    assert model.index(0, model.POINT_COLUMN).data(Qt.ItemDataRole.AccessibleTextRole) == "point-b"


def test_registry_refresh_preserves_exact_registry_key(tmp_path) -> None:
    _app()
    repository = TenderRegistryRepository(tmp_path / "registry.sqlite3")
    repository.record_profile_run(
        _run(
            _evaluated_tender(procurement_number="150-1", external_id="eis-150-1"),
            _evaluated_tender(procurement_number="150-2", external_id="eis-150-2"),
        ),
        run_id="rm150-run",
    )
    dialog = TenderRegistryDialog(repository)
    target = next(record for record in dialog.records if record.procurement_number == "150-2")

    assert dialog.select_registry_key(target.registry_key)
    dialog.refresh_records()

    assert dialog.selected_record() is not None
    assert dialog.selected_record().registry_key == target.registry_key
    assert dialog.table.item(dialog.table.currentRow(), 0).data(Qt.ItemDataRole.UserRole) == (
        target.registry_key
    )


def test_search_selection_returns_the_exact_evaluated_tender() -> None:
    _app()
    first = _evaluated_tender(procurement_number="150-1", external_id="eis-150-1")
    second = _evaluated_tender(procurement_number="150-2", external_id="eis-150-2")
    dialog = TenderSearchResultsDialog(_run(first, second))
    dialog.table.setCurrentCell(1, 0)
    dialog.table.selectRow(1)

    assert dialog.selected_evaluated() is second


def test_provider_refresh_preserves_exact_provider_id_after_reorder() -> None:
    _app()
    states = _states()
    dialog = TenderProviderManagerDialog(states)
    dialog.table.setCurrentCell(1, 0)
    dialog.table.selectRow(1)
    selected_id = dialog.selected_provider_id()

    dialog.set_states(reversed(states))

    assert dialog.selected_provider_id() == selected_id
    assert (
        dialog.table.item(dialog.table.currentRow(), 0).data(Qt.ItemDataRole.UserRole)
        == selected_id
    )


def test_backup_refresh_preserves_selected_path_while_it_exists(tmp_path) -> None:
    _app()
    repository = BusinessMetricsRepository(tmp_path / "workflow.json")
    backup_service = WorkflowBackupService()
    directory = tmp_path / "backups"
    first = directory / "first.ctbackup"
    backup_service.create_backup(
        repository,
        first,
        created_at=datetime(2026, 7, 19, 10, 0),
    )
    backup_service.create_backup(
        repository,
        directory / "second.ctbackup",
        created_at=datetime(2026, 7, 19, 11, 0),
    )
    dialog = WorkflowBackupCenterDialog(
        repository=repository,
        backup_service=backup_service,
        catalog_service=WorkflowBackupCatalogService(backup_service),
        directories=(directory,),
    )
    target_row = next(row for row, entry in enumerate(dialog.entries) if entry.path == first)
    dialog.table.setCurrentCell(target_row, 0)
    dialog.table.selectRow(target_row)

    dialog.refresh()

    assert dialog.selected_entry is not None
    assert dialog.selected_entry.path == first


def test_workspace_estimate_and_catalog_actions_keep_selected_payload(monkeypatch) -> None:
    _app()
    page = _page(monkeypatch)
    page.add_estimate_row("first", cost=Decimal("10.10"))
    page.add_estimate_row("second", cost=Decimal("20.20"))
    page.estimate_table.setCurrentCell(0, 0)
    page.estimate_table.selectRow(0)

    page.remove_estimate_row()

    assert page.estimate_table.rowCount() == 1
    assert page.estimate_table.item(0, 0).text() == "second"

    page.catalog_table.setRowCount(1)
    for column, value in enumerate(("video", "camera", "piece", "30.30", "29", "31")):
        page.catalog_table.setItem(0, column, QTableWidgetItem(value))
    page.catalog_table.setCurrentCell(0, 0)
    page.catalog_table.selectRow(0)
    page.add_from_catalog()

    assert page.estimate_table.item(1, 0).text() == "camera"
    assert page.estimate_table.item(1, 3).text() == "30.3"
