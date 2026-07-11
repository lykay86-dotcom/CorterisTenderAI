"""Tests for final Dashboard responsive polish."""

from __future__ import annotations

from app.ui.dashboard.responsive import (
    DashboardDensity,
    dashboard_layout_for_width,
)


def test_narrow_dashboard_uses_single_column() -> None:
    spec = dashboard_layout_for_width(640)

    assert spec.density == DashboardDensity.NARROW
    assert spec.kpi_columns == 1
    assert spec.primary_columns == 1
    assert spec.secondary_columns == 1


def test_compact_dashboard_stacks_major_sections() -> None:
    spec = dashboard_layout_for_width(1000)

    assert spec.density == DashboardDensity.COMPACT
    assert spec.kpi_columns == 2
    assert spec.primary_columns == 1
    assert spec.quick_action_columns == 2


def test_standard_dashboard_uses_two_column_sections() -> None:
    spec = dashboard_layout_for_width(1360)

    assert spec.density == DashboardDensity.STANDARD
    assert spec.kpi_columns == 3
    assert spec.primary_columns == 2
    assert spec.secondary_columns == 2


def test_wide_dashboard_increases_working_height() -> None:
    standard = dashboard_layout_for_width(1360)
    wide = dashboard_layout_for_width(1700)

    assert wide.density == DashboardDensity.WIDE
    assert wide.tender_min_height > standard.tender_min_height
    assert wide.outer_margin > standard.outer_margin
