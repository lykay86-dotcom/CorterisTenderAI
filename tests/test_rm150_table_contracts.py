"""Expected-red specification for the Qt-free RM-150 table contract."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal
import importlib

import pytest


def _tables():
    return importlib.import_module("app.ui.tables")


def _snapshot():
    table = _tables()
    columns = (
        table.TableColumn(
            table.TableColumnId("name"),
            "Name",
            table.TableValueKind.TEXT,
            filterable=True,
        ),
        table.TableColumn(
            table.TableColumnId("amount"),
            "Amount",
            table.TableValueKind.DECIMAL,
            null_policy=table.NullPolicy.LAST,
        ),
    )
    rows = (
        table.TableRow(
            table.TableRowId("registry", "row-b"),
            table.TableRevision("revision-b"),
            (
                table.TableCell("Straße", accessible_text="Straße"),
                table.TableCell(
                    "10.20 RUB",
                    sort_value=Decimal("10.20"),
                    export_value=Decimal("10.20"),
                    accessible_text="10.20 RUB",
                ),
            ),
            action_ids=("open", "archive"),
        ),
        table.TableRow(
            table.TableRowId("registry", "row-a"),
            table.TableRevision("revision-a"),
            (
                table.TableCell("STRASSE", accessible_text="STRASSE"),
                table.TableCell(
                    "10.20 RUB",
                    sort_value=Decimal("10.20"),
                    export_value=Decimal("10.20"),
                    accessible_text="10.20 RUB",
                ),
            ),
            action_ids=("open",),
        ),
        table.TableRow(
            table.TableRowId("registry", "row-null"),
            table.TableRevision("revision-null"),
            (
                table.TableCell("Other", accessible_text="Other"),
                table.TableCell("—", sort_value=None, export_value=None, accessible_text="Missing"),
            ),
        ),
    )
    return table.TableSnapshot(
        surface_id=table.TableSurfaceId("TBL-150-020"),
        fingerprint="snapshot-1",
        state=table.TableState.READY,
        columns=columns,
        rows=rows,
    )


def test_identity_namespaces_are_exact_frozen_and_hostile_values_fail_closed() -> None:
    table = _tables()
    registry = table.TableRowId("registry", "same")
    legacy = table.TableRowId("legacy_orm", "same")

    assert registry != legacy
    assert registry.public_id == "registry:same"
    with pytest.raises(FrozenInstanceError):
        registry.value = "changed"  # type: ignore[misc]
    for value in ("", "   ", "bad\x00id", "bad\u202eid", "x" * 513):
        with pytest.raises((TypeError, ValueError)):
            table.TableRowId("registry", value)


def test_snapshot_rejects_duplicate_ids_missing_cells_and_fake_state_rows() -> None:
    table = _tables()
    snapshot = _snapshot()
    with pytest.raises(ValueError, match="duplicate"):
        table.TableSnapshot(
            snapshot.surface_id,
            "duplicate",
            table.TableState.READY,
            snapshot.columns,
            (snapshot.rows[0], snapshot.rows[0]),
        )
    with pytest.raises(ValueError, match="cell"):
        table.TableRow(
            table.TableRowId("registry", "short"),
            table.TableRevision("revision"),
            (table.TableCell("only one"),),
        ).validate_for(snapshot.columns)
    with pytest.raises(ValueError, match="EMPTY"):
        table.TableSnapshot(
            snapshot.surface_id,
            "fake-empty",
            table.TableState.EMPTY,
            snapshot.columns,
            snapshot.rows,
        )


def test_decimal_sort_is_typed_null_aware_and_uses_identity_tie_break() -> None:
    table = _tables()
    visible = table.project_snapshot(
        _snapshot(),
        sort=table.SortSpec(
            (
                table.SortKey(
                    table.TableColumnId("amount"),
                    table.SortDirection.ASCENDING,
                    table.NullPolicy.LAST,
                ),
            )
        ),
    )

    assert tuple(row.row_id.value for row in visible.rows) == ("row-a", "row-b", "row-null")
    assert visible.rows[0].cells[1].sort_value == Decimal("10.20")


def test_filter_uses_unicode_casefold_and_only_declared_columns() -> None:
    table = _tables()
    visible = table.project_snapshot(
        _snapshot(),
        text_filter=table.TextFilter("strasse"),
    )

    assert tuple(row.row_id.value for row in visible.rows) == ("row-b", "row-a")


def test_visible_snapshot_is_the_single_export_parity_value() -> None:
    table = _tables()
    visible = table.project_snapshot(
        _snapshot(),
        text_filter=table.TextFilter("strasse"),
        sort=table.SortSpec(
            (table.SortKey(table.TableColumnId("amount"), table.SortDirection.DESCENDING),)
        ),
    )
    export = table.export_projection(visible)

    assert export.source_fingerprint == visible.source_fingerprint
    assert export.visible_fingerprint == visible.visible_fingerprint
    assert export.row_ids == tuple(row.row_id for row in visible.rows)
    assert export.column_ids == tuple(column.column_id for column in visible.columns)
    assert export.values[0][1] == Decimal("10.20")


def test_selection_reconciles_by_exact_id_and_never_chooses_a_neighbor() -> None:
    table = _tables()
    snapshot = _snapshot()
    selected = table.TableSelection(snapshot.rows[1].row_id)

    assert selected.reconcile(snapshot).row_id == snapshot.rows[1].row_id
    without_selected = table.TableSnapshot(
        snapshot.surface_id,
        "snapshot-2",
        table.TableState.READY,
        snapshot.columns,
        (snapshot.rows[0], snapshot.rows[2]),
    )
    assert selected.reconcile(without_selected).row_id is None


def test_action_token_requires_exact_identity_revision_fingerprint_and_availability() -> None:
    table = _tables()
    snapshot = _snapshot()
    row = snapshot.rows[0]
    token = table.TableActionToken(
        surface_id=snapshot.surface_id,
        action_id="archive",
        row_id=row.row_id,
        row_revision=row.revision,
        snapshot_fingerprint=snapshot.fingerprint,
    )

    assert table.validate_action_token(token, snapshot).allowed
    stale = table.TableSnapshot(
        snapshot.surface_id,
        "snapshot-2",
        snapshot.state,
        snapshot.columns,
        snapshot.rows,
    )
    result = table.validate_action_token(token, stale)
    assert not result.allowed
    assert result.reason_code == "snapshot_stale"


def test_partial_state_requires_honest_message_and_keeps_real_rows() -> None:
    table = _tables()
    snapshot = _snapshot()
    partial = table.TableSnapshot(
        snapshot.surface_id,
        "partial-1",
        table.TableState.PARTIAL,
        snapshot.columns,
        snapshot.rows,
        state_message="One provider unavailable",
    )

    assert partial.rows == snapshot.rows
    with pytest.raises(ValueError, match="message"):
        table.TableSnapshot(
            snapshot.surface_id,
            "partial-2",
            table.TableState.PARTIAL,
            snapshot.columns,
            snapshot.rows,
        )
