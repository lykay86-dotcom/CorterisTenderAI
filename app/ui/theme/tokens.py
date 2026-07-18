"""Versioned immutable design tokens for Corteris desktop UI."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum
from types import MappingProxyType
from typing import Final, Mapping


DESIGN_SYSTEM_VERSION: Final[str] = "corteris-design-v1"


class Spacing(IntEnum):
    ZERO = 0
    XS = 4
    S = 8
    M = 12
    L = 16
    XL = 24
    XXL = 32
    XXXL = 48


class IconSize(IntEnum):
    XS = 12
    S = 16
    M = 20
    L = 24
    XL = 32


class BorderWidth(IntEnum):
    DEFAULT = 1
    FOCUS = 2
    EMPHASIS = 3


class Radius(IntEnum):
    SMALL = 4
    MEDIUM = 6
    LARGE = 12
    PILL = 999


class MotionDuration(IntEnum):
    INSTANT = 0
    FAST = 100
    STANDARD = 180
    SLOW = 300


class ControlSize(StrEnum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


@dataclass(frozen=True, slots=True)
class ControlMetrics:
    height: int
    horizontal_padding: int
    vertical_padding: int
    icon_size: int
    radius: int


@dataclass(frozen=True, slots=True)
class LayoutTokens:
    page_margin: int = int(Spacing.XL)
    section_gap: int = int(Spacing.L)
    component_gap: int = int(Spacing.S)
    compact_margin: int = int(Spacing.M)
    sidebar_width: int = 252
    content_max_width: int = 1440


@dataclass(frozen=True, slots=True)
class MotionTokens:
    fast_ms: int = int(MotionDuration.FAST)
    standard_ms: int = int(MotionDuration.STANDARD)
    slow_ms: int = int(MotionDuration.SLOW)
    loading_frame_ms: int = int(MotionDuration.STANDARD)


@dataclass(frozen=True, slots=True)
class ElevationTokens:
    card_blur: int = 26
    card_offset_y: int = 6
    dialog_blur: int = 36
    dialog_offset_y: int = 10


@dataclass(frozen=True, slots=True)
class DesignTokens:
    version: str
    migration_matrix_version: str
    transparent: str
    layout: LayoutTokens
    motion: MotionTokens
    elevation: ElevationTokens
    controls: Mapping[str, ControlMetrics]


_CONTROL_METRICS: Final[Mapping[str, ControlMetrics]] = MappingProxyType(
    {
        ControlSize.SMALL.value: ControlMetrics(32, 10, 5, int(IconSize.S), int(Radius.MEDIUM)),
        ControlSize.MEDIUM.value: ControlMetrics(38, 14, 7, int(IconSize.M), int(Radius.MEDIUM)),
        ControlSize.LARGE.value: ControlMetrics(46, 18, 9, int(IconSize.L), int(Radius.LARGE)),
    }
)


DESIGN_TOKENS: Final[DesignTokens] = DesignTokens(
    version=DESIGN_SYSTEM_VERSION,
    migration_matrix_version="rm143-style-matrix-v1",
    transparent="transparent",
    layout=LayoutTokens(),
    motion=MotionTokens(),
    elevation=ElevationTokens(),
    controls=_CONTROL_METRICS,
)


__all__ = [
    "BorderWidth",
    "ControlMetrics",
    "ControlSize",
    "DESIGN_SYSTEM_VERSION",
    "DESIGN_TOKENS",
    "DesignTokens",
    "ElevationTokens",
    "IconSize",
    "LayoutTokens",
    "MotionDuration",
    "MotionTokens",
    "Radius",
    "Spacing",
]
