"""Responsive layout rules for Dashboard 1.0."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DashboardDensity(StrEnum):
    """Dashboard density selected for the available content width."""

    NARROW = "narrow"
    COMPACT = "compact"
    STANDARD = "standard"
    WIDE = "wide"


@dataclass(frozen=True, slots=True)
class DashboardLayoutSpec:
    """Visual layout parameters for one dashboard breakpoint."""

    density: DashboardDensity
    outer_margin: int
    section_spacing: int
    grid_spacing: int
    kpi_columns: int
    quick_action_columns: int
    primary_columns: int
    secondary_columns: int
    tender_min_height: int
    advisor_min_height: int
    activity_min_height: int

    @property
    def compact(self) -> bool:
        return self.density in {
            DashboardDensity.NARROW,
            DashboardDensity.COMPACT,
        }


def dashboard_layout_for_width(width: int) -> DashboardLayoutSpec:
    """Return deterministic layout settings for the content width."""
    normalized = max(0, int(width))

    if normalized < 760:
        return DashboardLayoutSpec(
            density=DashboardDensity.NARROW,
            outer_margin=12,
            section_spacing=12,
            grid_spacing=12,
            kpi_columns=1,
            quick_action_columns=1,
            primary_columns=1,
            secondary_columns=1,
            tender_min_height=300,
            advisor_min_height=390,
            activity_min_height=240,
        )

    if normalized < 1180:
        return DashboardLayoutSpec(
            density=DashboardDensity.COMPACT,
            outer_margin=16,
            section_spacing=14,
            grid_spacing=14,
            kpi_columns=2,
            quick_action_columns=2,
            primary_columns=1,
            secondary_columns=1,
            tender_min_height=330,
            advisor_min_height=370,
            activity_min_height=240,
        )

    if normalized < 1560:
        return DashboardLayoutSpec(
            density=DashboardDensity.STANDARD,
            outer_margin=22,
            section_spacing=16,
            grid_spacing=16,
            kpi_columns=3,
            quick_action_columns=2,
            primary_columns=2,
            secondary_columns=2,
            tender_min_height=380,
            advisor_min_height=380,
            activity_min_height=260,
        )

    return DashboardLayoutSpec(
        density=DashboardDensity.WIDE,
        outer_margin=28,
        section_spacing=18,
        grid_spacing=18,
        kpi_columns=3,
        quick_action_columns=2,
        primary_columns=2,
        secondary_columns=2,
        tender_min_height=420,
        advisor_min_height=420,
        activity_min_height=280,
    )


__all__ = [
    "DashboardDensity",
    "DashboardLayoutSpec",
    "dashboard_layout_for_width",
]
