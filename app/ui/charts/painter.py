"""One QPainter implementation shared by screen, PNG, and SVG targets."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF

from app.ui.charts.contracts import ChartKind, ChartLineStyle, ChartMarker, ChartState
from app.ui.charts.render_plan import ChartRenderPlan, RenderMark


def _pen_style(style: ChartLineStyle) -> Qt.PenStyle:
    return {
        ChartLineStyle.SOLID: Qt.PenStyle.SolidLine,
        ChartLineStyle.DASHED: Qt.PenStyle.DashLine,
        ChartLineStyle.DOTTED: Qt.PenStyle.DotLine,
    }[style]


def _draw_marker(painter: QPainter, mark: RenderMark, *, selected: bool) -> None:
    radius = 5.0 if selected else 4.0
    painter.setPen(QPen(QColor(mark.color), 2.0))
    painter.setBrush(QColor(mark.color))
    center = QPointF(mark.x, mark.y)
    if mark.marker is ChartMarker.CIRCLE:
        painter.drawEllipse(center, radius, radius)
    elif mark.marker is ChartMarker.SQUARE:
        painter.drawRect(QRectF(mark.x - radius, mark.y - radius, radius * 2, radius * 2))
    elif mark.marker is ChartMarker.DIAMOND:
        painter.drawPolygon(
            QPolygonF(
                [
                    QPointF(mark.x, mark.y - radius),
                    QPointF(mark.x + radius, mark.y),
                    QPointF(mark.x, mark.y + radius),
                    QPointF(mark.x - radius, mark.y),
                ]
            )
        )
    else:
        painter.drawPolygon(
            QPolygonF(
                [
                    QPointF(mark.x, mark.y - radius),
                    QPointF(mark.x + radius, mark.y + radius),
                    QPointF(mark.x - radius, mark.y + radius),
                ]
            )
        )


def paint_chart(
    painter: QPainter,
    plan: ChartRenderPlan,
    *,
    selected_id: tuple[str, str] | None = None,
    focused: bool = False,
) -> None:
    """Paint a normalized plan without reading external or widget state."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    painter.fillRect(
        QRectF(0, 0, plan.viewport.width, plan.viewport.height),
        QColor(plan.background_color),
    )

    title_font = QFont("Segoe UI", 11)
    title_font.setWeight(QFont.Weight.DemiBold)
    painter.setFont(title_font)
    painter.setPen(QColor(plan.text_color))
    painter.drawText(
        QRectF(16, 10, plan.viewport.width - 32, 30),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        plan.spec.title,
    )

    label_font = QFont("Segoe UI", 8)
    painter.setFont(label_font)
    plot = plan.plot_rect
    if plan.marks:
        painter.setPen(QPen(QColor(plan.grid_color), 1.0))
        for tick in plan.y_ticks:
            painter.drawLine(
                QPointF(plot.x, tick.position), QPointF(plot.x + plot.width, tick.position)
            )
        painter.setPen(QPen(QColor(plan.axis_color), 1.0))
        painter.drawLine(QPointF(plot.x, plot.y), QPointF(plot.x, plot.y + plot.height))
        painter.drawLine(
            QPointF(plot.x, plot.y + plot.height),
            QPointF(plot.x + plot.width, plot.y + plot.height),
        )
        for tick in plan.y_ticks:
            painter.drawText(
                QRectF(2, tick.position - 8, max(1.0, plot.x - 8), 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                tick.label,
            )
        for tick in plan.x_ticks:
            painter.drawText(
                QRectF(tick.position - 42, plot.y + plot.height + 7, 84, 18),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                tick.label,
            )

    if plan.spec.kind is ChartKind.BAR:
        painter.setPen(Qt.PenStyle.NoPen)
        for mark in plan.marks:
            painter.setBrush(QColor(mark.color))
            painter.drawRect(QRectF(mark.x, mark.y, mark.width, mark.height))
            if selected_id == (mark.series_id, mark.point_id):
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor(plan.focus_color), 2.0))
                painter.drawRect(
                    QRectF(mark.x - 3, mark.y - 3, mark.width + 6, max(6.0, mark.height + 6))
                )
                painter.setPen(Qt.PenStyle.NoPen)
    else:
        for segment in plan.line_segments:
            if not segment.points:
                continue
            path = QPainterPath(QPointF(segment.points[0].x, segment.points[0].y))
            for point in segment.points[1:]:
                path.lineTo(point.x, point.y)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(segment.color), 2.0, _pen_style(segment.line_style)))
            painter.drawPath(path)
        for mark in plan.marks:
            _draw_marker(
                painter,
                mark,
                selected=selected_id == (mark.series_id, mark.point_id),
            )

    if plan.state is not ChartState.READY:
        banner = QRectF(16, 42, plan.viewport.width - 32, 28)
        painter.setPen(QPen(QColor(plan.axis_color), 1.0))
        painter.setBrush(QColor(plan.background_color))
        painter.drawRoundedRect(banner, 4, 4)
        painter.setPen(QColor(plan.text_color))
        painter.drawText(
            banner.adjusted(8, 0, -8, 0), Qt.AlignmentFlag.AlignVCenter, plan.state_message
        )

    if focused:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(plan.focus_color), 2.0))
        painter.drawRoundedRect(
            QRectF(2, 2, plan.viewport.width - 4, plan.viewport.height - 4), 5, 5
        )
    painter.restore()


__all__ = ["paint_chart"]
