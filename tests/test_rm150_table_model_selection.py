"""Expected-red Qt model, selection and state projection tests for RM-150."""

from __future__ import annotations

from decimal import Decimal
import importlib
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTableView


def _tables():
    return importlib.import_module("app.ui.tables")


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _snapshot(*, row_ids: tuple[str, ...] = ("b", "a"), fingerprint: str = "one"):
    table = _tables()
    columns = (
        table.TableColumn(
            table.TableColumnId("amount"),
            "Amount",
            table.TableValueKind.DECIMAL,
            accessible_description="Exact amount in RUB",
        ),
    )
    return table.TableSnapshot(
        table.TableSurfaceId("TBL-150-014"),
        fingerprint,
        table.TableState.READY if row_ids else table.TableState.EMPTY,
        columns,
        tuple(
            table.TableRow(
                table.TableRowId("workflow_record", row_id),
                table.TableRevision(f"revision-{row_id}"),
                (
                    table.TableCell(
                        f"{index}.25 RUB",
                        sort_value=Decimal(f"{index}.25"),
                        export_value=Decimal(f"{index}.25"),
                        accessible_text=f"{index}.25 Russian rubles",
                    ),
                ),
                action_ids=("open",),
            )
            for index, row_id in enumerate(row_ids, start=1)
        ),
    )


def test_qt_model_exposes_common_identity_revision_column_sort_export_and_accessible_roles() -> (
    None
):
    _app()
    table = _tables()
    model = table.ImmutableTableModel(_snapshot())
    index = model.index(0, 0)

    assert index.data(table.TableRole.ROW_ID) == table.TableRowId("workflow_record", "b")
    assert index.data(table.TableRole.ROW_REVISION) == table.TableRevision("revision-b")
    assert index.data(table.TableRole.COLUMN_ID) == table.TableColumnId("amount")
    assert index.data(table.TableRole.SORT_VALUE) == Decimal("1.25")
    assert index.data(table.TableRole.EXPORT_VALUE) == Decimal("1.25")
    assert index.data(Qt.ItemDataRole.AccessibleTextRole) == "1.25 Russian rubles"
    assert model.headerData(0, Qt.Orientation.Horizontal, Qt.ItemDataRole.AccessibleTextRole) == (
        "Exact amount in RUB"
    )


def test_selection_controller_restores_exact_id_and_clears_removed_selection() -> None:
    _app()
    table = _tables()
    view = QTableView()
    model = table.ImmutableTableModel(_snapshot())
    view.setModel(model)
    controller = table.TableSelectionController(view, model)
    controller.select_row_id(table.TableRowId("workflow_record", "a"))

    model.set_snapshot(_snapshot(row_ids=("a", "b"), fingerprint="two"))
    assert controller.selected_row_id == table.TableRowId("workflow_record", "a")

    model.set_snapshot(_snapshot(row_ids=("b",), fingerprint="three"))
    assert controller.selected_row_id is None
    assert not view.selectionModel().hasSelection()


def test_state_host_renders_sibling_status_and_never_inserts_fake_rows() -> None:
    _app()
    table = _tables()
    host = table.TableStateHost(
        surface_id=table.TableSurfaceId("TBL-150-008"),
        accessible_name="Tender providers",
        accessible_description="Provider health and availability",
    )
    empty = _snapshot(row_ids=(), fingerprint="empty")
    host.set_snapshot(empty)

    assert host.model.rowCount() == 0
    assert host.state_region.isVisibleTo(host)
    assert host.state_region.accessibleName()
    assert host.table.accessibleName() == "Tender providers"
    assert host.table.accessibleDescription() == "Provider health and availability"


def test_keyboard_activation_dispatches_token_for_exact_selected_identity() -> None:
    _app()
    table = _tables()
    host = table.TableStateHost(
        surface_id=table.TableSurfaceId("TBL-150-010"),
        accessible_name="Recent tenders",
        accessible_description="Enter opens the selected tender",
        primary_action_id="open",
    )
    host.set_snapshot(_snapshot())
    tokens = []
    host.action_requested.connect(tokens.append)
    host.selection.select_row_id(table.TableRowId("workflow_record", "a"))
    host.activate_selected()

    assert len(tokens) == 1
    assert tokens[0].row_id == table.TableRowId("workflow_record", "a")
    assert tokens[0].action_id == "open"
