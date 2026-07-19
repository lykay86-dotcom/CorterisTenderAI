"""Deterministic normalization from exact chart data to painter geometry."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import math
from typing import Final

from PySide6.QtCore import QPoint

from app.ui.charts.contracts import (
    MAX_RENDER_POINTS,
    ChartAxisScale,
    ChartKind,
    ChartLineStyle,
    ChartMarker,
    ChartSpec,
    ChartState,
    ChartViewport,
    ChartXValue,
)
from app.ui.theme.colors import ThemePalette


_INTERACTABLE_STATES: Final = {ChartState.READY, ChartState.PARTIAL, ChartState.STALE}
_STATE_MESSAGES: Final = {
    ChartState.LOADING: "Загрузка данных графика…",
    ChartState.READY: "Данные графика готовы.",
    ChartState.EMPTY: "Нет данных для отображения.",
    ChartState.PARTIAL: "Показаны неполные данные.",
    ChartState.STALE: "Показаны устаревшие данные.",
    ChartState.ERROR: "Не удалось отобразить данные графика.",
    ChartState.TOO_LARGE: f"Слишком много точек для визуализации; предел {MAX_RENDER_POINTS:,}.",
    ChartState.UNAVAILABLE: "График недоступен.",
}


@dataclass(frozen=True, slots=True)
class GeometryPoint:
    """Backend-neutral logical point."""

    x: float
    y: float

    def to_point(self) -> QPoint:
        """Convert to a Qt integer point only at the widget event boundary."""
        return QPoint(round(self.x), round(self.y))


@dataclass(frozen=True, slots=True)
class GeometryRect:
    """Backend-neutral logical rectangle."""

    x: float
    y: float
    width: float
    height: float

    def center(self) -> GeometryPoint:
        return GeometryPoint(self.x + (self.width / 2), self.y + (self.height / 2))

    def contains(self, x: float, y: float) -> bool:
        return self.x <= x <= self.x + self.width and self.y <= y <= self.y + self.height


@dataclass(frozen=True, slots=True)
class RenderTick:
    """One stable logical tick."""

    label: str
    position: float


@dataclass(frozen=True, slots=True)
class RenderMark:
    """One selectable point/bar mark."""

    series_id: str
    point_id: str
    label: str
    value: Decimal
    x_value: ChartXValue
    x: float
    y: float
    width: float
    height: float
    hit_rect: GeometryRect
    color: str
    marker: ChartMarker


@dataclass(frozen=True, slots=True)
class RenderLineSegment:
    """One contiguous non-missing line path."""

    series_id: str
    point_ids: tuple[str, ...]
    points: tuple[GeometryPoint, ...]
    color: str
    line_style: ChartLineStyle


@dataclass(frozen=True, slots=True)
class ChartRenderPlan:
    """Immutable semantic geometry consumed by every painter target."""

    spec: ChartSpec
    viewport: ChartViewport
    state: ChartState
    state_message: str
    total_points: int
    plot_rect: GeometryRect
    marks: tuple[RenderMark, ...]
    line_segments: tuple[RenderLineSegment, ...]
    x_ticks: tuple[RenderTick, ...]
    y_ticks: tuple[RenderTick, ...]
    selectable_ids: tuple[tuple[str, str], ...]
    background_color: str
    text_color: str
    muted_text_color: str
    grid_color: str
    axis_color: str
    focus_color: str

    def semantic_projection(self) -> tuple[object, ...]:
        """Return semantics only, intentionally excluding theme and geometry."""
        return (
            self.spec.contract_version,
            self.spec.chart_id,
            self.spec.kind.value,
            self.spec.title,
            self.state.value,
            self.total_points,
            tuple(
                (
                    series.series_id,
                    series.label,
                    series.line_style.value,
                    series.marker.value,
                    tuple(
                        (point.point_id, _x_text(point.x), _decimal_text(point.y))
                        for point in series.points
                    ),
                )
                for series in self.spec.series
            ),
            self.selectable_ids,
        )

    def palette_projection(self) -> tuple[str, ...]:
        return (
            self.background_color,
            self.text_color,
            self.muted_text_color,
            self.grid_color,
            self.axis_color,
            self.focus_color,
            *(mark.color for mark in self.marks),
        )

    def geometry_projection(self) -> tuple[object, ...]:
        return (
            self.viewport.width,
            self.viewport.height,
            self.plot_rect,
            tuple((mark.point_id, mark.x, mark.y, mark.width, mark.height) for mark in self.marks),
            tuple(
                tuple((point.x, point.y) for point in line.points) for line in self.line_segments
            ),
        )


def _decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _x_text(value: ChartXValue) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _numeric_x(value: ChartXValue) -> float:
    if isinstance(value, datetime):
        return value.timestamp()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return float(value)
    raise TypeError("Expected numeric or datetime X value")


def _validate_order(spec: ChartSpec) -> None:
    if spec.x_axis.scale is ChartAxisScale.CATEGORY:
        return
    for series in spec.series:
        values = tuple(_numeric_x(point.x) for point in series.points)
        if any(current < previous for previous, current in zip(values, values[1:])):
            raise ValueError(f"X values in series {series.series_id!r} must be non-decreasing")


def _plot_rect(viewport: ChartViewport) -> GeometryRect:
    left = min(72.0, viewport.width * 0.22)
    right = min(28.0, viewport.width * 0.09)
    top = min(54.0, viewport.height * 0.22)
    bottom = min(62.0, viewport.height * 0.25)
    return GeometryRect(
        round(left, 4),
        round(top, 4),
        round(max(1.0, viewport.width - left - right), 4),
        round(max(1.0, viewport.height - top - bottom), 4),
    )


def _scale(value: float, minimum: float, maximum: float, start: float, length: float) -> float:
    if math.isclose(minimum, maximum):
        return start + (length / 2)
    return start + ((value - minimum) / (maximum - minimum) * length)


def _state_message(state: ChartState, detail: str) -> str:
    base = _STATE_MESSAGES[state]
    return f"{base} {detail}" if detail else base


def normalize_chart(
    spec: ChartSpec,
    viewport: ChartViewport,
    palette: ThemePalette,
) -> ChartRenderPlan:
    """Normalize exact source values without reordering or business aggregation."""
    if not isinstance(spec, ChartSpec):
        raise TypeError("spec must be ChartSpec")
    if not isinstance(viewport, ChartViewport):
        raise TypeError("viewport must be ChartViewport")
    if not isinstance(palette, ThemePalette):
        raise TypeError("palette must be ThemePalette")
    _validate_order(spec)

    total_points = sum(len(series.points) for series in spec.series)
    state = ChartState.TOO_LARGE if total_points > MAX_RENDER_POINTS else spec.state
    plot = _plot_rect(viewport)
    message = _state_message(state, spec.state_detail)
    base = dict(
        spec=spec,
        viewport=viewport,
        state=state,
        state_message=message,
        total_points=total_points,
        plot_rect=plot,
        background_color=palette.card_background,
        text_color=palette.text_primary,
        muted_text_color=palette.text_muted,
        grid_color=palette.chart_grid,
        axis_color=palette.chart_axis,
        focus_color=palette.focus_ring,
    )
    if state not in _INTERACTABLE_STATES or total_points == 0:
        return ChartRenderPlan(
            **base,
            marks=(),
            line_segments=(),
            x_ticks=(),
            y_ticks=(),
            selectable_ids=(),
        )

    present = tuple(
        (series, point) for series in spec.series for point in series.points if point.y is not None
    )
    if not present:
        return ChartRenderPlan(
            **base,
            marks=(),
            line_segments=(),
            x_ticks=(),
            y_ticks=(),
            selectable_ids=(),
        )

    y_values = tuple(float(point.y) for _series, point in present if point.y is not None)
    y_min = min((*y_values, 0.0))
    y_max = max((*y_values, 0.0))
    if math.isclose(y_min, y_max):
        y_max = y_min + 1.0
    y_ticks = tuple(
        RenderTick(
            label=format(y_min + ((y_max - y_min) * index / 4), ".6g"),
            position=round(plot.y + plot.height - (plot.height * index / 4), 4),
        )
        for index in range(5)
    )

    if spec.kind is ChartKind.BAR:
        marks, x_ticks = _bar_marks(spec, plot, palette, y_min, y_max)
        lines: tuple[RenderLineSegment, ...] = ()
    else:
        marks, lines, x_ticks = _line_marks(spec, plot, palette, y_min, y_max)

    return ChartRenderPlan(
        **base,
        marks=marks,
        line_segments=lines,
        x_ticks=x_ticks,
        y_ticks=y_ticks,
        selectable_ids=tuple((mark.series_id, mark.point_id) for mark in marks),
    )


def _bar_marks(
    spec: ChartSpec,
    plot: GeometryRect,
    palette: ThemePalette,
    y_min: float,
    y_max: float,
) -> tuple[tuple[RenderMark, ...], tuple[RenderTick, ...]]:
    slots = tuple((series, point) for series in spec.series for point in series.points)
    slot_width = plot.width / max(1, len(slots))
    bar_width = max(1.0, min(48.0, slot_width * 0.64))
    zero_y = plot.y + plot.height - _scale(0.0, y_min, y_max, 0.0, plot.height)
    marks = []
    ticks = []
    for index, (series, point) in enumerate(slots):
        center_x = plot.x + (slot_width * (index + 0.5))
        ticks.append(RenderTick(point.label or _x_text(point.x), round(center_x, 4)))
        if point.y is None:
            continue
        value_y = plot.y + plot.height - _scale(float(point.y), y_min, y_max, 0.0, plot.height)
        top = min(value_y, zero_y)
        height = abs(zero_y - value_y)
        rect = GeometryRect(
            round(center_x - (bar_width / 2), 4),
            round(top, 4),
            round(bar_width, 4),
            round(height, 4),
        )
        hit_height = max(12.0, rect.height)
        hit_top = rect.y if rect.height >= 12 else rect.y - ((12 - rect.height) / 2)
        marks.append(
            RenderMark(
                series.series_id,
                point.point_id,
                point.label or _x_text(point.x),
                point.y,
                point.x,
                rect.x,
                rect.y,
                rect.width,
                rect.height,
                GeometryRect(rect.x - 3, hit_top, rect.width + 6, hit_height),
                getattr(palette, series.color_role.value),
                series.marker,
            )
        )
    return tuple(marks), tuple(ticks)


def _line_marks(
    spec: ChartSpec,
    plot: GeometryRect,
    palette: ThemePalette,
    y_min: float,
    y_max: float,
) -> tuple[tuple[RenderMark, ...], tuple[RenderLineSegment, ...], tuple[RenderTick, ...]]:
    all_x = tuple(_numeric_x(point.x) for series in spec.series for point in series.points)
    x_min = min(all_x)
    x_max = max(all_x)
    marks = []
    segments = []
    for series in spec.series:
        color = getattr(palette, series.color_role.value)
        current_ids: list[str] = []
        current_points: list[GeometryPoint] = []
        for point in series.points:
            if point.y is None:
                if current_ids:
                    segments.append(
                        RenderLineSegment(
                            series.series_id,
                            tuple(current_ids),
                            tuple(current_points),
                            color,
                            series.line_style,
                        )
                    )
                    current_ids = []
                    current_points = []
                continue
            x = _scale(_numeric_x(point.x), x_min, x_max, plot.x, plot.width)
            y = plot.y + plot.height - _scale(float(point.y), y_min, y_max, 0.0, plot.height)
            logical = GeometryPoint(round(x, 4), round(y, 4))
            current_ids.append(point.point_id)
            current_points.append(logical)
            marks.append(
                RenderMark(
                    series.series_id,
                    point.point_id,
                    point.label or _x_text(point.x),
                    point.y,
                    point.x,
                    logical.x,
                    logical.y,
                    0.0,
                    0.0,
                    GeometryRect(logical.x - 8, logical.y - 8, 16, 16),
                    color,
                    series.marker,
                )
            )
        if current_ids:
            segments.append(
                RenderLineSegment(
                    series.series_id,
                    tuple(current_ids),
                    tuple(current_points),
                    color,
                    series.line_style,
                )
            )
    ticks = tuple(
        RenderTick(
            label=format(x_min + ((x_max - x_min) * index / 4), ".6g"),
            position=round(plot.x + (plot.width * index / 4), 4),
        )
        for index in range(5)
    )
    return tuple(marks), tuple(segments), ticks


__all__ = [
    "ChartRenderPlan",
    "GeometryPoint",
    "GeometryRect",
    "RenderLineSegment",
    "RenderMark",
    "RenderTick",
    "normalize_chart",
]
