"""Expected-red tests for the RM-146 immutable chart and render-plan contract."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal
import importlib

import pytest

from app.ui.theme.colors import DARK_PALETTE, LIGHT_PALETTE
from app.ui.viewmodels.dashboard_viewmodel import DashboardSourceEvidence


def _charts():
    return importlib.import_module("app.ui.charts")


def _evidence() -> DashboardSourceEvidence:
    return DashboardSourceEvidence(
        source_id="synthetic",
        generation=7,
        observed_at=datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc),
        record_count=3,
        contributor_ids=("p-1", "p-2", "p-3"),
    )


def _line_spec():
    chart = _charts()
    return chart.ChartSpec(
        chart_id="synthetic-line",
        kind=chart.ChartKind.LINE,
        title="Synthetic line",
        description="Offline contract fixture",
        x_axis=chart.ChartAxis(chart.ChartAxisScale.NUMERIC, title="X"),
        y_axis=chart.ChartAxis(chart.ChartAxisScale.NUMERIC, title="Value", unit="units"),
        series=(
            chart.ChartSeries(
                series_id="series-a",
                label="Series A",
                color_role=chart.ChartColorRole.CHART_1,
                line_style=chart.ChartLineStyle.SOLID,
                marker=chart.ChartMarker.CIRCLE,
                points=(
                    chart.ChartPoint("p-1", Decimal("1"), Decimal("1.2500"), label="One"),
                    chart.ChartPoint("p-2", Decimal("2"), None, label="Missing"),
                    chart.ChartPoint("p-3", Decimal("3"), Decimal("2.500"), label="Three"),
                ),
            ),
        ),
        state=chart.ChartState.READY,
        source_evidence=(_evidence(),),
    )


def _bar_spec():
    chart = _charts()
    return chart.ChartSpec(
        chart_id="synthetic-bars",
        kind=chart.ChartKind.BAR,
        title="Synthetic bars",
        x_axis=chart.ChartAxis(chart.ChartAxisScale.CATEGORY, title="Category"),
        y_axis=chart.ChartAxis(chart.ChartAxisScale.NUMERIC, title="Count", unit="items"),
        series=(
            chart.ChartSeries(
                series_id="series-bars",
                label="Bars",
                color_role=chart.ChartColorRole.CHART_2,
                marker=chart.ChartMarker.SQUARE,
                points=(
                    chart.ChartPoint("a", "Alpha", Decimal("2")),
                    chart.ChartPoint("b", "Beta", Decimal("0")),
                ),
            ),
        ),
        state=chart.ChartState.READY,
        source_evidence=(_evidence(),),
    )


def test_public_contract_is_frozen_versioned_and_reuses_rm145_evidence() -> None:
    chart = _charts()
    spec = _line_spec()

    assert spec.contract_version == "corteris-chart-v1"
    assert chart.ChartSourceEvidence is DashboardSourceEvidence
    assert spec.series[0].points[0].y == Decimal("1.2500")
    assert spec.series[0].points[1].y is None
    with pytest.raises(FrozenInstanceError):
        spec.title = "Changed"  # type: ignore[misc]


def test_validation_rejects_float_nan_duplicate_ids_and_invalid_axis_combinations() -> None:
    chart = _charts()

    with pytest.raises((TypeError, ValueError), match="Decimal"):
        chart.ChartPoint("float", Decimal("1"), 1.25)
    with pytest.raises(ValueError, match="duplicate"):
        chart.ChartSeries(
            "duplicates",
            "Duplicates",
            (
                chart.ChartPoint("same", "A", Decimal("1")),
                chart.ChartPoint("same", "B", Decimal("2")),
            ),
        )
    with pytest.raises(ValueError, match="categorical"):
        chart.ChartSpec(
            chart_id="bad-line",
            kind=chart.ChartKind.LINE,
            title="Bad line",
            x_axis=chart.ChartAxis(chart.ChartAxisScale.CATEGORY),
            y_axis=chart.ChartAxis(chart.ChartAxisScale.NUMERIC),
            series=(),
        )


def test_time_axis_requires_aware_ordered_values() -> None:
    chart = _charts()
    aware = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="timezone-aware"):
        chart.ChartPoint("naive", datetime(2026, 7, 19, 12, 0), Decimal("1"))

    spec = chart.ChartSpec(
        chart_id="aware-time",
        kind=chart.ChartKind.LINE,
        title="Aware time",
        x_axis=chart.ChartAxis(chart.ChartAxisScale.TIME),
        y_axis=chart.ChartAxis(chart.ChartAxisScale.NUMERIC),
        series=(
            chart.ChartSeries(
                "time-series",
                "Time",
                (
                    chart.ChartPoint("later", aware, Decimal("1")),
                    chart.ChartPoint("earlier", aware.replace(hour=11), Decimal("2")),
                ),
            ),
        ),
    )
    with pytest.raises(ValueError, match="non-decreasing"):
        chart.normalize_chart(spec, chart.ChartViewport(800, 450), DARK_PALETTE)


def test_line_plan_preserves_order_exact_identity_and_missing_gap() -> None:
    chart = _charts()
    plan = chart.normalize_chart(_line_spec(), chart.ChartViewport(800, 450), DARK_PALETTE)

    assert plan.state is chart.ChartState.READY
    assert plan.total_points == 3
    assert tuple((mark.series_id, mark.point_id) for mark in plan.marks) == (
        ("series-a", "p-1"),
        ("series-a", "p-3"),
    )
    assert tuple(segment.point_ids for segment in plan.line_segments) == (("p-1",), ("p-3",))
    assert plan.selectable_ids == (("series-a", "p-1"), ("series-a", "p-3"))


def test_bar_plan_keeps_zero_as_a_real_value() -> None:
    chart = _charts()
    plan = chart.normalize_chart(_bar_spec(), chart.ChartViewport(640, 360), LIGHT_PALETTE)

    assert tuple(mark.point_id for mark in plan.marks) == ("a", "b")
    assert plan.marks[1].value == Decimal("0")
    assert plan.marks[1].height == 0


def test_theme_and_resize_change_geometry_or_color_but_not_semantics() -> None:
    chart = _charts()
    spec = _line_spec()
    dark = chart.normalize_chart(spec, chart.ChartViewport(800, 450), DARK_PALETTE)
    light = chart.normalize_chart(spec, chart.ChartViewport(800, 450), LIGHT_PALETTE)
    resized = chart.normalize_chart(spec, chart.ChartViewport(1024, 576), DARK_PALETTE)

    assert dark.semantic_projection() == light.semantic_projection()
    assert dark.semantic_projection() == resized.semantic_projection()
    assert dark.palette_projection() != light.palette_projection()
    assert dark.geometry_projection() != resized.geometry_projection()


def test_visual_limit_is_explicit_and_never_silently_samples() -> None:
    chart = _charts()
    points = tuple(
        chart.ChartPoint(f"p-{index}", Decimal(index), Decimal(index)) for index in range(1_001)
    )
    spec = chart.ChartSpec(
        chart_id="too-large",
        kind=chart.ChartKind.LINE,
        title="Too large",
        x_axis=chart.ChartAxis(chart.ChartAxisScale.NUMERIC),
        y_axis=chart.ChartAxis(chart.ChartAxisScale.NUMERIC),
        series=(chart.ChartSeries("large", "Large", points),),
        source_evidence=(_evidence(),),
    )

    plan = chart.normalize_chart(spec, chart.ChartViewport(800, 450), DARK_PALETTE)

    assert plan.state is chart.ChartState.TOO_LARGE
    assert plan.total_points == 1_001
    assert plan.marks == ()
    assert plan.line_segments == ()
    assert "1,000" in plan.state_message


def test_all_semantic_states_have_visible_non_color_text() -> None:
    chart = _charts()
    messages = {}
    for state in chart.ChartState:
        spec = chart.ChartSpec(
            chart_id=f"state-{state.value}",
            kind=chart.ChartKind.BAR,
            title="State",
            x_axis=chart.ChartAxis(chart.ChartAxisScale.CATEGORY),
            y_axis=chart.ChartAxis(chart.ChartAxisScale.NUMERIC),
            series=(),
            state=state,
            state_detail="Synthetic detail",
        )
        plan = chart.normalize_chart(spec, chart.ChartViewport(640, 360), DARK_PALETTE)
        messages[state] = plan.state_message

    assert all(messages.values())
    assert len(set(messages.values())) == len(chart.ChartState)
