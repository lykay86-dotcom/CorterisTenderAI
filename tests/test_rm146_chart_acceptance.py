"""Hardening acceptance for RM-146 synthetic fixtures and lifecycle boundaries."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import isValid

from app.ui.charts import (
    ChartAxis,
    ChartAxisScale,
    ChartColorRole,
    ChartKind,
    ChartLineStyle,
    ChartMarker,
    ChartPoint,
    ChartSeries,
    ChartSpec,
    ChartState,
    ChartViewport,
    ChartWidget,
    export_chart_csv,
    export_chart_json,
    export_chart_png,
    export_chart_svg,
    normalize_chart,
)
from app.ui.theme.colors import DARK_PALETTE, LIGHT_PALETTE
from app.ui.viewmodels.dashboard_viewmodel import DashboardSourceEvidence


NOW = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _evidence(record_count: int) -> tuple[DashboardSourceEvidence, ...]:
    return (
        DashboardSourceEvidence(
            source_id="rm146-synthetic",
            generation=1,
            observed_at=NOW,
            record_count=record_count,
            contributor_ids=tuple(f"synthetic-{index}" for index in range(record_count)),
            demo=True,
        ),
    )


def _line_demo() -> ChartSpec:
    timestamps = tuple(NOW + timedelta(days=index) for index in range(12))
    first = tuple(
        ChartPoint(
            f"line-a-{index}",
            timestamp,
            None if index == 5 else Decimal(index) / Decimal("4"),
            label=f"A {index}",
        )
        for index, timestamp in enumerate(timestamps)
    )
    second = tuple(
        ChartPoint(
            f"line-b-{index}",
            timestamp,
            Decimal(index - 3) / Decimal("2"),
            label=f"B {index}",
        )
        for index, timestamp in enumerate(timestamps)
    )
    return ChartSpec(
        chart_id="line-demo-001",
        kind=ChartKind.LINE,
        title="LINE-DEMO-001",
        description="Synthetic offline time-series fixture",
        x_axis=ChartAxis(ChartAxisScale.TIME, title="Aware time"),
        y_axis=ChartAxis(ChartAxisScale.NUMERIC, title="Synthetic value", unit="units"),
        series=(
            ChartSeries(
                "line-a",
                "Synthetic A",
                first,
                color_role=ChartColorRole.CHART_1,
                line_style=ChartLineStyle.SOLID,
                marker=ChartMarker.CIRCLE,
            ),
            ChartSeries(
                "line-b",
                "Synthetic B",
                second,
                color_role=ChartColorRole.CHART_4,
                line_style=ChartLineStyle.DASHED,
                marker=ChartMarker.DIAMOND,
            ),
        ),
        source_evidence=_evidence(24),
    )


def _bar_demo() -> ChartSpec:
    categories = ("Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta")
    first_values = ("3", "0", "-2", "5", "1.25", "4")
    second_values = ("-1", "2", "3", "0", "-0.5", "6")
    return ChartSpec(
        chart_id="bar-demo-001",
        kind=ChartKind.BAR,
        title="BAR-DEMO-001",
        x_axis=ChartAxis(ChartAxisScale.CATEGORY, title="Synthetic category"),
        y_axis=ChartAxis(ChartAxisScale.NUMERIC, title="Synthetic value", unit="items"),
        series=(
            ChartSeries(
                "bar-a",
                "Synthetic bars A",
                tuple(
                    ChartPoint(f"bar-a-{index}", category, Decimal(value))
                    for index, (category, value) in enumerate(zip(categories, first_values))
                ),
                color_role=ChartColorRole.CHART_2,
                marker=ChartMarker.SQUARE,
            ),
            ChartSeries(
                "bar-b",
                "Synthetic bars B",
                tuple(
                    ChartPoint(f"bar-b-{index}", category, Decimal(value))
                    for index, (category, value) in enumerate(zip(categories, second_values))
                ),
                color_role=ChartColorRole.CHART_5,
                marker=ChartMarker.TRIANGLE,
            ),
        ),
        source_evidence=_evidence(12),
    )


def test_reference_fixtures_are_exact_repeatable_and_backend_neutral() -> None:
    first = _line_demo()
    second = _line_demo()
    bar = _bar_demo()

    assert first == second
    assert len(first.series) == 2
    assert tuple(len(series.points) for series in first.series) == (12, 12)
    assert sum(point.y is None for series in first.series for point in series.points) == 1
    assert len(bar.series) == 2
    assert tuple(len(series.points) for series in bar.series) == (6, 6)
    assert any(point.y == 0 for series in bar.series for point in series.points)
    assert any(
        point.y is not None and point.y < 0 for series in bar.series for point in series.points
    )

    first_plan = normalize_chart(first, ChartViewport(800, 450), DARK_PALETTE)
    second_plan = normalize_chart(second, ChartViewport(800, 450), DARK_PALETTE)
    assert first_plan == second_plan
    assert export_chart_json(first) == export_chart_json(second)
    assert export_chart_csv(first) == export_chart_csv(second)


def test_security_fixture_rejects_controls_and_bidi_and_escapes_tooltip_html() -> None:
    with pytest.raises(ValueError, match="control or bidi"):
        ChartPoint("control", "Safe\nunsafe", Decimal("1"))
    with pytest.raises(ValueError, match="control or bidi"):
        ChartPoint("bidi", "safe\u202eevil", Decimal("1"))

    app = _app()
    spec = _bar_demo()
    html_series = ChartSeries(
        "safe-series",
        "<b>synthetic</b>",
        (ChartPoint("safe-point", "https://example.invalid/?token=synthetic", Decimal("1")),),
    )
    safe_spec = ChartSpec(
        chart_id="security-fixture",
        kind=ChartKind.BAR,
        title=spec.title,
        x_axis=spec.x_axis,
        y_axis=spec.y_axis,
        series=(html_series,),
        source_evidence=_evidence(1),
    )
    widget = ChartWidget(safe_spec, palette=DARK_PALETTE)
    widget.resize(640, 360)
    widget.show()
    app.processEvents()
    mark = widget.canvas.render_plan.marks[0]
    QTest.mouseMove(widget.canvas, mark.hit_rect.center().to_point())

    assert widget.selection is None
    assert "<b>synthetic</b>" in widget.canvas.tooltip_text
    assert "&lt;b&gt;synthetic&lt;/b&gt;" in widget.canvas.toolTip()

    widget.close()
    widget.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    assert not isValid(widget)


def test_all_state_fixtures_preserve_caller_state_and_visible_text() -> None:
    states = (
        ChartState.LOADING,
        ChartState.EMPTY,
        ChartState.PARTIAL,
        ChartState.STALE,
        ChartState.ERROR,
        ChartState.UNAVAILABLE,
    )
    messages = []
    for state in states:
        base = _bar_demo()
        spec = ChartSpec(
            chart_id=f"fixture-{state.value}",
            kind=base.kind,
            title=base.title,
            x_axis=base.x_axis,
            y_axis=base.y_axis,
            series=base.series if state in (ChartState.PARTIAL, ChartState.STALE) else (),
            state=state,
            source_evidence=base.source_evidence,
            state_detail="Synthetic state detail",
        )
        plan = normalize_chart(spec, ChartViewport(640, 360), LIGHT_PALETTE)
        assert plan.state is state
        assert "Synthetic state detail" in plan.state_message
        messages.append(plan.state_message)
    assert len(set(messages)) == len(states)


def test_huge_exact_decimal_remains_exportable_but_is_not_unsafe_geometry() -> None:
    spec = ChartSpec(
        chart_id="huge-decimal",
        kind=ChartKind.LINE,
        title="Huge exact value",
        x_axis=ChartAxis(ChartAxisScale.NUMERIC),
        y_axis=ChartAxis(ChartAxisScale.NUMERIC),
        series=(
            ChartSeries(
                "huge",
                "Huge",
                (ChartPoint("huge-point", Decimal("1"), Decimal("1e10000")),),
            ),
        ),
    )

    assert b'"1E+10000"' in export_chart_json(spec)
    with pytest.raises(ValueError, match="renderable coordinate range"):
        normalize_chart(spec, ChartViewport(640, 360), DARK_PALETTE)


def test_dpi_exports_have_checked_physical_size_and_stable_logical_svg() -> None:
    _app()
    spec = _line_demo()
    for scale in (1.0, 1.25, 1.5, 2.0, 4.0):
        viewport = ChartViewport(640, 360, scale)
        png = export_chart_png(spec, viewport, DARK_PALETTE)
        image = QImage.fromData(png, "PNG")
        svg = export_chart_svg(spec, viewport, DARK_PALETTE)

        assert image.width() == round(640 * scale)
        assert image.height() == round(360 * scale)
        assert b'viewBox="0 0 640 360"' in svg


def test_twenty_update_theme_resize_cycles_do_not_add_widget_children() -> None:
    app = _app()
    widget = ChartWidget(_line_demo(), palette=DARK_PALETTE)
    widget.resize(800, 520)
    widget.show()
    app.processEvents()
    initial_children = len(widget.findChildren(QWidget))

    for index in range(20):
        widget.set_chart(_line_demo() if index % 2 == 0 else _bar_demo())
        widget.set_palette(DARK_PALETTE if index % 2 == 0 else LIGHT_PALETTE)
        widget.resize(800 + (index % 3) * 20, 520 + (index % 2) * 20)
        app.processEvents()

    assert len(widget.findChildren(QWidget)) == initial_children
    assert widget.canvas.render_plan.total_points in (12, 24)
    assert widget.canvas.focusPolicy() is Qt.FocusPolicy.StrongFocus

    widget.close()
    widget.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    assert not isValid(widget)
