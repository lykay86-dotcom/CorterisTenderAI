"""Representative RM-150 bindings not covered by the common model tests."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.core.workflow_backup import WorkflowBackupService
from app.core.workflow_backup_catalog import WorkflowBackupCatalogService
from app.financial import FinancialMetricId
from app.repositories.business_metrics import (
    BusinessMetricsRepository,
    BusinessRecordKind,
    BusinessStatus,
)
from app.tenders.tender_registry import TenderRegistryRepository
from app.ui.business_workflow.backup_center_dialog import WorkflowBackupCenterDialog
from app.ui.pages.tender_analytics_page import TenderAnalyticsPage
from app.ui.tables import TableRole, TableRowId, TableState
from app.ui.tender_registry_dialog import TenderRegistryDialog
from tests.rm147_analytics_helpers import aggregate, make_record
from tests.test_rm127_tender_workspace_contract import _page
from tests.test_tender_registry import _evaluated_tender, _run


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_registry_common_identity_survives_filter_hiding_without_neighbor(tmp_path) -> None:
    _app()
    repository = TenderRegistryRepository(tmp_path / "registry.sqlite3")
    repository.record_profile_run(
        _run(
            _evaluated_tender(procurement_number="150-1", external_id="eis-150-1"),
            _evaluated_tender(procurement_number="150-2", external_id="eis-150-2"),
        ),
        run_id="rm150",
    )
    dialog = TenderRegistryDialog(repository)
    target = next(record for record in dialog.records if record.procurement_number == "150-2")
    assert dialog.select_registry_key(target.registry_key)
    item = dialog.table.item(dialog.table.currentRow(), 0)
    assert item.data(TableRole.ROW_ID) == TableRowId("registry", target.registry_key)

    repository.set_archived(target.registry_key, True)
    dialog.refresh_records()

    assert dialog.selected_record() is None
    archive_index = dialog.state_combo.findData("archived")
    dialog.state_combo.setCurrentIndex(archive_index)
    dialog.refresh_records()
    assert dialog.selected_record() is not None
    assert dialog.selected_record().registry_key == target.registry_key


def test_backup_action_token_fails_closed_after_file_revision_changes(tmp_path) -> None:
    _app()
    repository = BusinessMetricsRepository(tmp_path / "workflow.json")
    service = WorkflowBackupService()
    directory = tmp_path / "backups"
    path = directory / "rm150.ctbackup"
    service.create_backup(
        repository,
        path,
        created_at=datetime(2026, 7, 20, 12, 0),
    )
    dialog = WorkflowBackupCenterDialog(
        repository=repository,
        backup_service=service,
        catalog_service=WorkflowBackupCatalogService(service),
        directories=(directory,),
    )
    entry = dialog.selected_entry
    assert entry is not None
    token = dialog._action_token(entry, "restore")
    path.write_bytes(path.read_bytes() + b"stale")

    assert dialog._revalidate_action(token) is None


def test_analytics_tables_expose_exact_snapshot_roles_and_values(tmp_path) -> None:
    _app()
    page = TenderAnalyticsPage()
    analytics = aggregate((make_record("a"), make_record("b", status="completed")))
    page.set_snapshot(analytics)
    text_item = page.text_table.item(0, 0)

    assert text_item.data(TableRole.ROW_ID).namespace == "analytics_point"
    assert text_item.data(TableRole.ROW_REVISION).value == analytics.fingerprint
    assert text_item.data(TableRole.STATE) in {TableState.READY, TableState.PARTIAL}

    repository = BusinessMetricsRepository(tmp_path / "financial.json")
    repository.save_record(
        kind=BusinessRecordKind.PROPOSAL,
        tender_id="T-150",
        title="Exact",
        status=BusinessStatus.READY,
        total=Decimal("150.25"),
        profit=Decimal("10.05"),
    )
    financial = repository.financial_snapshot(
        generated_at=datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
    )
    page.set_financial_snapshot(financial)
    metric_row = next(
        row
        for row, metric in enumerate(financial.metrics)
        if metric.metric_id is FinancialMetricId.POTENTIAL_PROFIT
    )
    exact_item = page.financial_table.item(metric_row, 1)

    assert exact_item.data(TableRole.EXPORT_VALUE) == Decimal("10.05")
    assert exact_item.data(TableRole.ROW_REVISION).value == financial.fingerprint


def test_editable_workspace_rows_keep_identity_across_recalculation(monkeypatch) -> None:
    _app()
    page = _page(monkeypatch)
    page.add_estimate_row("camera", qty=Decimal("2"), cost=Decimal("150.25"))
    before = page.estimate_table.item(0, 0).data(TableRole.ROW_ID)

    page.recalculate_estimate()

    assert before.namespace == "estimate_line"
    assert page.estimate_table.item(0, 6).data(TableRole.ROW_ID) == before
    assert page.estimate_table.item(0, 3).data(TableRole.SORT_VALUE) == Decimal("150.25")
    assert page.estimate_table.accessibleName()
    assert page.catalog_table.accessibleDescription()
