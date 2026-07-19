"""Expected-red tests for RM-146 export, text, and interaction contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import importlib
import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.ui.theme.colors import DARK_PALETTE
from app.ui.viewmodels.dashboard_viewmodel import DashboardSourceEvidence


def _charts():
    return importlib.import_module("app.ui.charts")


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _spec(*, missing: bool = True):
    chart = _charts()
    evidence = DashboardSourceEvidence(
        source_id="synthetic",
        generation=3,
        observed_at=datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc),
        record_count=3,
        contributor_ids=("a", "b", "c"),
    )
    return chart.ChartSpec(
        chart_id="export-line",
        kind=chart.ChartKind.LINE,
        title="Export line",
        description="<b>plain text only</b>",
        x_axis=chart.ChartAxis(chart.ChartAxisScale.NUMERIC, title="X"),
        y_axis=chart.ChartAxis(chart.ChartAxisScale.NUMERIC, title="Value", unit="RUB"),
        series=(
            chart.ChartSeries(
                series_id="series-a",
                label="=Unsafe series",
                color_role=chart.ChartColorRole.CHART_1,
                marker=chart.ChartMarker.CIRCLE,
                points=(
                    chart.ChartPoint("a", Decimal("1"), Decimal("1.2500"), label="A"),
                    chart.ChartPoint(
                        "b",
                        Decimal("2"),
                        None if missing else Decimal("2"),
                        label="B",
                    ),
                    chart.ChartPoint("c", Decimal("3"), Decimal("3.500"), label="C"),
                ),
            ),
        ),
        state=chart.ChartState.READY,
        source_evidence=(evidence,),
    )


def test_json_export_is_exact_ordered_and_byte_deterministic() -> None:
    chart = _charts()
    first = chart.export_chart_json(_spec())
    second = chart.export_chart_json(_spec())

    assert first == second
    assert first.endswith(b"\n")
    payload = json.loads(first)
    assert payload["contract_version"] == "corteris-chart-v1"
    assert payload["series"][0]["points"][0]["y"] == "1.2500"
    assert payload["series"][0]["points"][1]["y"] is None
    assert payload["source_evidence"][0]["observed_at"].endswith("+00:00")


def test_csv_export_preserves_rows_missing_and_neutralizes_formula_text() -> None:
    chart = _charts()
    data = chart.export_chart_csv(_spec()).decode("utf-8")
    lines = data.splitlines()

    assert lines[0].startswith("contract_version,chart_id,chart_state,series_id")
    assert len(lines) == 4
    assert "'=Unsafe series" in lines[1]
    assert ",1.2500,false,RUB" in lines[1]
    assert ",,true,RUB" in lines[2]


def test_visual_exports_use_one_bounded_semantic_plan() -> None:
    chart = _charts()
    viewport = chart.ChartViewport(640, 360, device_scale=1.5)
    png = chart.export_chart_png(_spec(), viewport, DARK_PALETTE)
    svg = chart.export_chart_svg(_spec(), viewport, DARK_PALETTE)

    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert b"<svg" in svg
    assert b"http://" not in svg
    assert b"https://" not in svg
    assert b"<script" not in svg.lower()

    with pytest.raises(ValueError, match="pixel budget"):
        chart.export_chart_png(
            _spec(),
            chart.ChartViewport(4096, 4096, device_scale=4),
            DARK_PALETTE,
        )


def test_table_model_is_complete_exact_and_source_ordered() -> None:
    chart = _charts()
    model = chart.ChartTableModel(_spec())

    assert model.rowCount(QModelIndex()) == 3
    assert model.columnCount(QModelIndex()) >= 6
    rows = [model.row_record(row) for row in range(3)]
    assert tuple(row.point_id for row in rows) == ("a", "b", "c")
    assert rows[0].y == Decimal("1.2500")
    assert rows[1].y is None
    assert model.data(model.index(1, model.Y_COLUMN), Qt.ItemDataRole.DisplayRole) == "Missing"


def test_widget_accessibility_table_and_keyboard_selection_share_stable_ids() -> None:
    chart = _charts()
    app = _app()
    widget = chart.ChartWidget(_spec(), palette=DARK_PALETTE)
    widget.resize(800, 520)
    widget.show()
    widget.canvas.setFocus()
    app.processEvents()
    changes = []
    confirmations = []
    widget.selection_changed.connect(changes.append)
    widget.selection_confirmed.connect(confirmations.append)

    QTest.keyClick(widget.canvas, Qt.Key.Key_Home)
    QTest.keyClick(widget.canvas, Qt.Key.Key_Right)
    assert widget.selection.point_id == "c"
    assert changes[-1].cause is chart.ChartSelectionCause.KEYBOARD

    QTest.keyClick(widget.canvas, Qt.Key.Key_Return)
    assert confirmations[-1].point_id == "c"
    assert "3.500" in widget.canvas.tooltip_text

    QTest.keyClick(widget.canvas, Qt.Key.Key_F2)
    app.processEvents()
    assert widget.table.isVisible()
    assert widget.table.hasFocus()
    assert widget.canvas.accessibleName().startswith("Export line")
    assert "F2" in widget.canvas.accessibleDescription()

    widget.close()
    widget.deleteLater()
    app.processEvents()


def test_mouse_and_keyboard_resolve_the_same_typed_selection() -> None:
    chart = _charts()
    app = _app()
    widget = chart.ChartWidget(_spec(missing=False), palette=DARK_PALETTE)
    widget.resize(800, 520)
    widget.show()
    app.processEvents()

    mark = next(item for item in widget.canvas.render_plan.marks if item.point_id == "a")
    QTest.mouseClick(
        widget.canvas,
        Qt.MouseButton.LeftButton,
        pos=mark.hit_rect.center().to_point(),
    )
    mouse_selection = widget.selection

    widget.clear_selection()
    widget.canvas.setFocus()
    QTest.keyClick(widget.canvas, Qt.Key.Key_Home)
    keyboard_selection = widget.selection

    assert mouse_selection.series_id == keyboard_selection.series_id == "series-a"
    assert mouse_selection.point_id == keyboard_selection.point_id == "a"
    assert mouse_selection.cause is chart.ChartSelectionCause.MOUSE
    assert keyboard_selection.cause is chart.ChartSelectionCause.KEYBOARD

    widget.close()
    widget.deleteLater()
    app.processEvents()


def test_selection_retains_by_id_on_resize_and_clears_when_id_disappears() -> None:
    chart = _charts()
    app = _app()
    widget = chart.ChartWidget(_spec(missing=False), palette=DARK_PALETTE)
    widget.resize(800, 520)
    widget.show()
    widget.canvas.setFocus()
    app.processEvents()

    QTest.keyClick(widget.canvas, Qt.Key.Key_End)
    assert widget.selection.point_id == "c"
    before = widget.canvas.render_plan.geometry_projection()
    widget.resize(1024, 640)
    app.processEvents()
    assert widget.selection.point_id == "c"
    assert widget.canvas.render_plan.geometry_projection() != before

    reduced = _spec(missing=False)
    only_first = reduced.series[0].points[:1]
    reduced_series = chart.ChartSeries(
        "series-a",
        "=Unsafe series",
        only_first,
        color_role=chart.ChartColorRole.CHART_1,
        marker=chart.ChartMarker.CIRCLE,
    )
    widget.set_chart(
        chart.ChartSpec(
            chart_id=reduced.chart_id,
            kind=reduced.kind,
            title=reduced.title,
            x_axis=reduced.x_axis,
            y_axis=reduced.y_axis,
            series=(reduced_series,),
            state=reduced.state,
            source_evidence=reduced.source_evidence,
        )
    )
    assert widget.selection is None

    widget.close()
    widget.deleteLater()
    app.processEvents()
