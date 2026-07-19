"""Immutable, backend-neutral contracts for Corteris charts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
import math
import re
import unicodedata
from typing import Final, TypeAlias

from app.ui.viewmodels.dashboard_viewmodel import DashboardSourceEvidence


CONTRACT_VERSION: Final = "corteris-chart-v1"
MAX_SERIES: Final = 6
MAX_POINTS_PER_SERIES: Final = 10_000
MAX_RENDER_POINTS: Final = 1_000

_ID_PATTERN: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")
_BIDI_CONTROLS: Final = frozenset(
    "\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"
)

ChartSourceEvidence: TypeAlias = DashboardSourceEvidence
ChartXValue: TypeAlias = str | int | Decimal | datetime


class ChartKind(StrEnum):
    """Supported visual chart families."""

    BAR = "bar"
    LINE = "line"


class ChartAxisScale(StrEnum):
    """Closed axis-value semantics."""

    CATEGORY = "category"
    NUMERIC = "numeric"
    TIME = "time"


class ChartState(StrEnum):
    """Closed semantic data/rendering states."""

    LOADING = "loading"
    READY = "ready"
    EMPTY = "empty"
    PARTIAL = "partial"
    STALE = "stale"
    ERROR = "error"
    TOO_LARGE = "too_large"
    UNAVAILABLE = "unavailable"


class ChartColorRole(StrEnum):
    """RM-143 palette roles available to a series."""

    CHART_1 = "chart_1"
    CHART_2 = "chart_2"
    CHART_3 = "chart_3"
    CHART_4 = "chart_4"
    CHART_5 = "chart_5"
    CHART_6 = "chart_6"


class ChartLineStyle(StrEnum):
    """Non-colour line discriminator."""

    SOLID = "solid"
    DASHED = "dashed"
    DOTTED = "dotted"


class ChartMarker(StrEnum):
    """Non-colour point discriminator."""

    CIRCLE = "circle"
    SQUARE = "square"
    DIAMOND = "diamond"
    TRIANGLE = "triangle"


class ChartSelectionCause(StrEnum):
    """Origin of one typed chart selection."""

    MOUSE = "mouse"
    KEYBOARD = "keyboard"
    PROGRAMMATIC = "programmatic"


def _checked_id(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not _ID_PATTERN.fullmatch(value):
        raise ValueError(
            f"{field_name} must be a 1-64 character ASCII identifier using letters, "
            "digits, dot, underscore, colon, or hyphen"
        )
    return value


def _checked_text(
    value: str,
    field_name: str,
    *,
    maximum: int,
    required: bool = False,
) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be text")
    if required and not value.strip():
        raise ValueError(f"{field_name} must not be blank")
    if len(value) > maximum:
        raise ValueError(f"{field_name} must not exceed {maximum} characters")
    if any(
        unicodedata.category(character) == "Cc" or character in _BIDI_CONTROLS
        for character in value
    ):
        raise ValueError(f"{field_name} must not contain control or bidi characters")
    return value


def _checked_decimal(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    if not isinstance(value, Decimal):
        raise TypeError("Chart Y values must be Decimal or None")
    if not value.is_finite():
        raise ValueError("Chart Decimal values must be finite")
    return value


def _checked_x(value: ChartXValue) -> ChartXValue:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal, datetime)):
        raise TypeError("Chart X values must be str, int, Decimal, or datetime")
    if isinstance(value, str):
        return _checked_text(value, "x", maximum=256, required=True)
    if isinstance(value, Decimal) and not value.is_finite():
        raise ValueError("Chart Decimal values must be finite")
    if isinstance(value, datetime) and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError("Chart datetime X values must be timezone-aware")
    return value


@dataclass(frozen=True, slots=True)
class ChartAxis:
    """One immutable axis definition."""

    scale: ChartAxisScale
    title: str = ""
    unit: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.scale, ChartAxisScale):
            raise TypeError("scale must be ChartAxisScale")
        _checked_text(self.title, "axis title", maximum=128)
        _checked_text(self.unit, "axis unit", maximum=32)


@dataclass(frozen=True, slots=True)
class ChartPoint:
    """One stable exact source point."""

    point_id: str
    x: ChartXValue
    y: Decimal | None
    label: str = ""

    def __post_init__(self) -> None:
        _checked_id(self.point_id, "point_id")
        _checked_x(self.x)
        _checked_decimal(self.y)
        _checked_text(self.label, "point label", maximum=256)


@dataclass(frozen=True, slots=True)
class ChartSeries:
    """One ordered immutable series."""

    series_id: str
    label: str
    points: tuple[ChartPoint, ...]
    color_role: ChartColorRole = ChartColorRole.CHART_1
    line_style: ChartLineStyle = ChartLineStyle.SOLID
    marker: ChartMarker = ChartMarker.CIRCLE

    def __post_init__(self) -> None:
        _checked_id(self.series_id, "series_id")
        _checked_text(self.label, "series label", maximum=128, required=True)
        if not isinstance(self.points, tuple) or not all(
            isinstance(point, ChartPoint) for point in self.points
        ):
            raise TypeError("points must be a tuple of ChartPoint")
        if len(self.points) > MAX_POINTS_PER_SERIES:
            raise ValueError(f"A series may contain at most {MAX_POINTS_PER_SERIES:,} points")
        point_ids = tuple(point.point_id for point in self.points)
        if len(set(point_ids)) != len(point_ids):
            raise ValueError("duplicate point_id in series")
        if not isinstance(self.color_role, ChartColorRole):
            raise TypeError("color_role must be ChartColorRole")
        if not isinstance(self.line_style, ChartLineStyle):
            raise TypeError("line_style must be ChartLineStyle")
        if not isinstance(self.marker, ChartMarker):
            raise TypeError("marker must be ChartMarker")


@dataclass(frozen=True, slots=True)
class ChartSpec:
    """Complete chart input with no business calculation behavior."""

    chart_id: str
    kind: ChartKind
    title: str
    x_axis: ChartAxis
    y_axis: ChartAxis
    series: tuple[ChartSeries, ...]
    description: str = ""
    state: ChartState = ChartState.READY
    source_evidence: tuple[ChartSourceEvidence, ...] = ()
    state_detail: str = ""
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        _checked_id(self.chart_id, "chart_id")
        _checked_text(self.title, "chart title", maximum=160, required=True)
        _checked_text(self.description, "chart description", maximum=512)
        _checked_text(self.state_detail, "state detail", maximum=512)
        if self.contract_version != CONTRACT_VERSION:
            raise ValueError(f"Unsupported chart contract version: {self.contract_version!r}")
        if not isinstance(self.kind, ChartKind):
            raise TypeError("kind must be ChartKind")
        if not isinstance(self.x_axis, ChartAxis) or not isinstance(self.y_axis, ChartAxis):
            raise TypeError("x_axis and y_axis must be ChartAxis")
        if self.y_axis.scale is not ChartAxisScale.NUMERIC:
            raise ValueError("The Y axis must be numeric")
        if self.kind is ChartKind.BAR and self.x_axis.scale is not ChartAxisScale.CATEGORY:
            raise ValueError("Bar charts require a categorical X axis")
        if self.kind is ChartKind.LINE and self.x_axis.scale is ChartAxisScale.CATEGORY:
            raise ValueError("Line charts do not support a categorical X axis")
        if not isinstance(self.series, tuple) or not all(
            isinstance(series, ChartSeries) for series in self.series
        ):
            raise TypeError("series must be a tuple of ChartSeries")
        if len(self.series) > MAX_SERIES:
            raise ValueError(f"A chart may contain at most {MAX_SERIES} series")
        series_ids = tuple(series.series_id for series in self.series)
        if len(set(series_ids)) != len(series_ids):
            raise ValueError("duplicate series_id in chart")
        if not isinstance(self.state, ChartState):
            raise TypeError("state must be ChartState")
        if not isinstance(self.source_evidence, tuple) or not all(
            isinstance(item, DashboardSourceEvidence) for item in self.source_evidence
        ):
            raise TypeError("source_evidence must be a tuple of DashboardSourceEvidence")
        self._validate_x_types()

    def _validate_x_types(self) -> None:
        for series in self.series:
            for point in series.points:
                if self.x_axis.scale is ChartAxisScale.CATEGORY and not isinstance(point.x, str):
                    raise TypeError("Categorical X values must be text")
                if self.x_axis.scale is ChartAxisScale.NUMERIC and (
                    isinstance(point.x, bool) or not isinstance(point.x, (int, Decimal))
                ):
                    raise TypeError("Numeric X values must be int or Decimal")
                if self.x_axis.scale is ChartAxisScale.TIME and not isinstance(point.x, datetime):
                    raise TypeError("Time X values must be timezone-aware datetime")


@dataclass(frozen=True, slots=True)
class ChartSelection:
    """Stable typed selection emitted by the presentation layer."""

    chart_id: str
    series_id: str
    point_id: str
    cause: ChartSelectionCause

    def __post_init__(self) -> None:
        _checked_id(self.chart_id, "chart_id")
        _checked_id(self.series_id, "series_id")
        _checked_id(self.point_id, "point_id")
        if not isinstance(self.cause, ChartSelectionCause):
            raise TypeError("cause must be ChartSelectionCause")


@dataclass(frozen=True, slots=True)
class ChartViewport:
    """Logical viewport plus checked device scale."""

    width: int
    height: int
    device_scale: float = 1.0

    def __post_init__(self) -> None:
        if isinstance(self.width, bool) or not isinstance(self.width, int) or self.width <= 0:
            raise ValueError("viewport width must be a positive integer")
        if isinstance(self.height, bool) or not isinstance(self.height, int) or self.height <= 0:
            raise ValueError("viewport height must be a positive integer")
        if (
            isinstance(self.device_scale, bool)
            or not isinstance(self.device_scale, (int, float))
            or not math.isfinite(float(self.device_scale))
            or float(self.device_scale) <= 0
        ):
            raise ValueError("device_scale must be a positive finite number")


__all__ = [
    "CONTRACT_VERSION",
    "MAX_POINTS_PER_SERIES",
    "MAX_RENDER_POINTS",
    "MAX_SERIES",
    "ChartAxis",
    "ChartAxisScale",
    "ChartColorRole",
    "ChartKind",
    "ChartLineStyle",
    "ChartMarker",
    "ChartPoint",
    "ChartSelection",
    "ChartSelectionCause",
    "ChartSeries",
    "ChartSourceEvidence",
    "ChartSpec",
    "ChartState",
    "ChartViewport",
    "ChartXValue",
]
