"""Accessible keyboard/mouse chart widget backed by one semantic render plan."""

from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent, QPaintEvent, QPainter, QResizeEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.ui.charts.contracts import (
    ChartSelection,
    ChartSelectionCause,
    ChartSpec,
    ChartState,
    ChartViewport,
)
from app.ui.charts.painter import paint_chart
from app.ui.charts.render_plan import ChartRenderPlan, RenderMark, normalize_chart
from app.ui.charts.table_model import ChartTableModel
from app.ui.theme.colors import ThemePalette


class ChartCanvas(QWidget):
    """Focusable painted chart surface with stable-ID interaction."""

    selection_changed = Signal(object)
    selection_confirmed = Signal(object)
    table_requested = Signal()

    def __init__(
        self, spec: ChartSpec, palette: ThemePalette, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._spec = spec
        self._palette = palette
        self._selection: ChartSelection | None = None
        self._render_plan = normalize_chart(spec, ChartViewport(640, 360), palette)
        self._tooltip_text = ""
        self.setObjectName("CorterisChartCanvas")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(160, 120)
        self.setMouseTracking(True)
        self._update_accessibility()

    @property
    def spec(self) -> ChartSpec:
        return self._spec

    @property
    def render_plan(self) -> ChartRenderPlan:
        return self._render_plan

    @property
    def selection(self) -> ChartSelection | None:
        return self._selection

    @property
    def tooltip_text(self) -> str:
        return self._tooltip_text

    def set_chart(self, spec: ChartSpec) -> None:
        retained = (
            None
            if self._selection is None
            else (self._selection.series_id, self._selection.point_id)
        )
        self._spec = spec
        self._rebuild_plan()
        if retained not in self._render_plan.selectable_ids:
            self.clear_selection()
        self._update_accessibility()
        self.update()

    def set_palette(self, palette: ThemePalette) -> None:
        self._palette = palette
        self._rebuild_plan()
        self.update()

    def clear_selection(self) -> None:
        if self._selection is None:
            return
        self._selection = None
        self._tooltip_text = ""
        self.setToolTip("")
        self.selection_changed.emit(None)
        self._update_accessibility()
        self.update()

    def _viewport(self) -> ChartViewport:
        return ChartViewport(max(1, self.width()), max(1, self.height()))

    def _rebuild_plan(self) -> None:
        self._render_plan = normalize_chart(self._spec, self._viewport(), self._palette)

    def _update_accessibility(self) -> None:
        self.setAccessibleName(f"{self._spec.title} — {self._spec.kind.value} chart")
        parts = [
            self._spec.description,
            f"{len(self._spec.series)} series, {self._render_plan.total_points} points.",
            self._render_plan.state_message,
            "Press F2 to open the complete data table.",
        ]
        if self._selection is not None:
            mark = self._mark(self._selection.series_id, self._selection.point_id)
            if mark is not None:
                parts.append(self._tooltip_for(mark))
        self.setAccessibleDescription(" ".join(part for part in parts if part))

    def _mark(self, series_id: str, point_id: str) -> RenderMark | None:
        return next(
            (
                mark
                for mark in self._render_plan.marks
                if mark.series_id == series_id and mark.point_id == point_id
            ),
            None,
        )

    def _series_label(self, series_id: str) -> str:
        return next(series.label for series in self._spec.series if series.series_id == series_id)

    def _tooltip_for(self, mark: RenderMark) -> str:
        unit = f" {self._spec.y_axis.unit}" if self._spec.y_axis.unit else ""
        state = ""
        if self._render_plan.state in (ChartState.PARTIAL, ChartState.STALE):
            state = f" {self._render_plan.state_message}"
        return (
            f"{self._spec.title}; {self._series_label(mark.series_id)}; "
            f"{mark.label}; {mark.value}{unit}.{state}"
        )

    def _select(self, series_id: str, point_id: str, cause: ChartSelectionCause) -> None:
        if (series_id, point_id) not in self._render_plan.selectable_ids:
            return
        selection = ChartSelection(self._spec.chart_id, series_id, point_id, cause)
        if self._selection == selection:
            return
        self._selection = selection
        mark = self._mark(series_id, point_id)
        self._tooltip_text = "" if mark is None else self._tooltip_for(mark)
        self.setToolTip(escape(self._tooltip_text))
        self.selection_changed.emit(selection)
        self._update_accessibility()
        self.update()

    def _current_index(self) -> int | None:
        if self._selection is None:
            return None
        try:
            return self._render_plan.selectable_ids.index(
                (self._selection.series_id, self._selection.point_id)
            )
        except ValueError:
            return None

    def _move_linear(self, delta: int) -> None:
        identities = self._render_plan.selectable_ids
        if not identities:
            return
        current = self._current_index()
        target = 0 if current is None else max(0, min(len(identities) - 1, current + delta))
        self._select(*identities[target], ChartSelectionCause.KEYBOARD)

    def _move_home_end(self, *, end: bool, all_series: bool) -> None:
        identities = self._render_plan.selectable_ids
        if not identities:
            return
        candidates = identities
        if not all_series and self._selection is not None:
            same_series = tuple(
                identity for identity in identities if identity[0] == self._selection.series_id
            )
            if same_series:
                candidates = same_series
        self._select(*(candidates[-1] if end else candidates[0]), ChartSelectionCause.KEYBOARD)

    def _move_series(self, delta: int) -> None:
        identities = self._render_plan.selectable_ids
        if not identities:
            return
        if self._selection is None:
            self._select(*identities[0], ChartSelectionCause.KEYBOARD)
            return
        series_ids = tuple(series.series_id for series in self._spec.series)
        current_series_index = series_ids.index(self._selection.series_id)
        target_index = max(0, min(len(series_ids) - 1, current_series_index + delta))
        if target_index == current_series_index:
            return
        current_series_points = tuple(
            identity for identity in identities if identity[0] == self._selection.series_id
        )
        point_position = current_series_points.index(
            (self._selection.series_id, self._selection.point_id)
        )
        target_points = tuple(
            identity for identity in identities if identity[0] == series_ids[target_index]
        )
        if target_points:
            self._select(
                *target_points[min(point_position, len(target_points) - 1)],
                ChartSelectionCause.KEYBOARD,
            )

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        selected_id = (
            None
            if self._selection is None
            else (self._selection.series_id, self._selection.point_id)
        )
        paint_chart(painter, self._render_plan, selected_id=selected_id, focused=self.hasFocus())
        painter.end()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._rebuild_plan()
        self._update_accessibility()

    def focusInEvent(self, event) -> None:  # noqa: N802
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event) -> None:  # noqa: N802
        super().focusOutEvent(event)
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()
        modifiers = event.modifiers()
        if key == Qt.Key.Key_Left:
            self._move_linear(-1)
        elif key == Qt.Key.Key_Right:
            self._move_linear(1)
        elif key == Qt.Key.Key_Up:
            self._move_series(-1)
        elif key == Qt.Key.Key_Down:
            self._move_series(1)
        elif key in (Qt.Key.Key_Home, Qt.Key.Key_End):
            self._move_home_end(
                end=key == Qt.Key.Key_End,
                all_series=bool(modifiers & Qt.KeyboardModifier.ControlModifier),
            )
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            if self._selection is not None:
                self.selection_confirmed.emit(self._selection)
        elif key == Qt.Key.Key_Escape:
            self.clear_selection()
        elif key == Qt.Key.Key_F2:
            self.table_requested.emit()
        else:
            super().keyPressEvent(event)
            return
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() is not Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        position = event.position()
        candidates = tuple(
            mark
            for mark in self._render_plan.marks
            if mark.hit_rect.contains(position.x(), position.y())
        )
        if candidates:
            selected = min(
                candidates,
                key=lambda mark: ((mark.x - position.x()) ** 2) + ((mark.y - position.y()) ** 2),
            )
            self._select(selected.series_id, selected.point_id, ChartSelectionCause.MOUSE)
        event.accept()


class ChartWidget(QWidget):
    """Composite visual chart and complete native Qt data table."""

    selection_changed = Signal(object)
    selection_confirmed = Signal(object)

    def __init__(
        self,
        spec: ChartSpec,
        *,
        palette: ThemePalette,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("CorterisChart")
        self.canvas = ChartCanvas(spec, palette, self)
        self.model = ChartTableModel(spec, self)
        self.table = QTableView(self)
        self.table.setObjectName("CorterisChartDataTable")
        self.table.setModel(self.model)
        self.table.setAccessibleName(f"{spec.title} — data table")
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.canvas, 1)
        layout.addWidget(self.table, 1)

        self.canvas.selection_changed.connect(self.selection_changed.emit)
        self.canvas.selection_confirmed.connect(self.selection_confirmed.emit)
        self.canvas.table_requested.connect(self.show_data_table)

    @property
    def selection(self) -> ChartSelection | None:
        return self.canvas.selection

    def set_chart(self, spec: ChartSpec) -> None:
        self.canvas.set_chart(spec)
        self.model.set_spec(spec)
        self.table.setAccessibleName(f"{spec.title} — data table")

    def set_palette(self, palette: ThemePalette) -> None:
        self.canvas.set_palette(palette)

    def clear_selection(self) -> None:
        self.canvas.clear_selection()

    def show_data_table(self) -> None:
        self.table.setVisible(True)
        self.table.setFocus(Qt.FocusReason.ShortcutFocusReason)


__all__ = ["ChartCanvas", "ChartWidget"]
