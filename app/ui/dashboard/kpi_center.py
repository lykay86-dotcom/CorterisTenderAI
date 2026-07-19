"""KPI Center for Dashboard 1.0."""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFocusEvent, QKeyEvent
from PySide6.QtWidgets import QGridLayout, QSizePolicy, QWidget

from app.ui.dashboard.data_state import DataState, DataStateKind
from app.ui.theme.colors import ThemeName
from app.ui.viewmodels.dashboard_viewmodel import DashboardKpi, DashboardKpiState
from app.ui.widgets.card import CardTone, KpiCard


class KeyboardKpiCard(KpiCard):
    """KPI card that supports keyboard focus and activation."""

    def __init__(self, *args, **kwargs) -> None:
        self._keyboard_focused = False
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def focusInEvent(self, event: QFocusEvent) -> None:
        self._keyboard_focused = True
        self._hovered = True
        self._apply_theme()
        super().focusInEvent(event)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        self._keyboard_focused = False
        self._hovered = False
        self._pressed = False
        self._apply_theme()
        super().focusOutEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in {
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Space,
        }:
            self.clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class KpiCenter(QWidget):
    """Responsive group of interactive KPI cards."""

    kpi_clicked = Signal(object)

    def __init__(
        self,
        kpis: Iterable[DashboardKpi] = (),
        *,
        theme: ThemeName | str = ThemeName.DARK,
        columns: int = 3,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        if columns < 1:
            raise ValueError("columns must be >= 1")

        self._theme = ThemeName(theme)
        self._columns = columns
        self._cards: dict[str, KpiCard] = {}
        self._kpis: dict[str, DashboardKpi] = {}
        self._data_state = DataState.ready()

        self.setObjectName("KpiCenter")
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(14)
        self._layout.setVerticalSpacing(14)

        self.set_kpis(kpis)

    @property
    def cards(self) -> dict[str, KpiCard]:
        return dict(self._cards)

    @property
    def columns(self) -> int:
        return self._columns

    @property
    def data_state(self) -> DataState:
        return self._data_state

    def set_data_state(self, state: DataState) -> None:
        """Render loading, empty, error or partial values."""
        self._data_state = state
        for key, kpi in self._kpis.items():
            card = self._cards.get(key)
            if card is not None:
                self._render_card(card, kpi)

    def focus_first(self) -> None:
        """Move keyboard focus to the first KPI card."""
        first = next(iter(self._cards.values()), None)
        if first is not None:
            first.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def focus_key(self, key: str) -> None:
        card = self._cards.get(key)
        if card is None:
            raise KeyError(key)
        card.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def set_columns(self, columns: int) -> None:
        """Change the number of columns without recreating cards."""
        if columns < 1:
            raise ValueError("columns must be >= 1")
        if columns == self._columns:
            return

        self._columns = columns
        self._relayout()

    def set_kpis(self, kpis: Iterable[DashboardKpi]) -> None:
        """Replace all KPI cards."""
        self._clear_layout()
        self._cards.clear()
        self._kpis = {kpi.key: kpi for kpi in kpis}

        for kpi in self._kpis.values():
            card = self._create_card(kpi)
            self._cards[kpi.key] = card

        self._relayout()

    def update_kpi(self, kpi: DashboardKpi) -> None:
        """Update one KPI card or create it when missing."""
        self._kpis[kpi.key] = kpi
        card = self._cards.get(kpi.key)
        if card is None:
            self.set_kpis(self._kpis.values())
            return

        self._render_card(card, kpi)

    def set_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        for card in self._cards.values():
            card.set_theme(self._theme)

    def _create_card(self, kpi: DashboardKpi) -> KpiCard:
        card = KeyboardKpiCard(
            kpi.title,
            kpi.value,
            trend=kpi.trend,
            trend_tone=self._tone(kpi.tone),
            icon_text=kpi.icon_text,
            theme=self._theme,
            clickable=kpi.action is not None,
        )
        card.setMinimumHeight(132)
        card.clicked.connect(
            lambda action=kpi.action: self.kpi_clicked.emit(action) if action is not None else None
        )
        self._render_card(card, kpi)
        return card

    def _render_card(
        self,
        card: KpiCard,
        kpi: DashboardKpi,
    ) -> None:
        state = self._data_state
        title = kpi.title
        value = kpi.value
        trend = kpi.trend
        tone = self._tone(kpi.tone)
        enabled = kpi.action is not None and kpi.state not in {
            DashboardKpiState.LOADING,
            DashboardKpiState.ERROR,
        }

        if kpi.state is DashboardKpiState.LOADING:
            value = "…"
            trend = kpi.state_reason or "Обновление данных"
            tone = CardTone.INFO
        elif kpi.state is DashboardKpiState.ERROR:
            value = "—"
            trend = kpi.state_reason or "Ошибка источника"
            tone = CardTone.WARNING
        elif kpi.state is DashboardKpiState.PARTIAL:
            trend = f"Частичные данные · {trend}" if trend else "Частичные данные"
            tone = CardTone.WARNING
        elif kpi.state is DashboardKpiState.STALE:
            trend = f"Устаревшие данные · {trend}" if trend else "Устаревшие данные"
            tone = CardTone.WARNING

        if state.kind == DataStateKind.LOADING:
            value = "…"
            trend = "Обновление данных"
            tone = CardTone.INFO
            enabled = False
        elif state.kind == DataStateKind.EMPTY:
            value = "—"
            trend = "Нет данных"
            tone = CardTone.DEFAULT
            enabled = False
        elif state.kind == DataStateKind.ERROR:
            value = "—"
            trend = "Ошибка загрузки"
            tone = CardTone.WARNING
            enabled = False
        elif state.kind == DataStateKind.PARTIAL:
            trend = trend or "Частичные данные"
            tone = CardTone.WARNING

        card.title = title
        card.value = value
        card.icon_text = kpi.icon_text
        card.set_trend(trend, tone)
        card.setEnabled(enabled)
        card.setAccessibleName(f"{title}: {value}")
        card.setAccessibleDescription(
            " ".join(
                part
                for part in (
                    kpi.accessible_description,
                    f"Отображается: {value}.",
                    trend,
                )
                if part
            )
        )

    def _relayout(self) -> None:
        while self._layout.count():
            self._layout.takeAt(0)

        previous: KpiCard | None = None
        for index, card in enumerate(self._cards.values()):
            row, column = divmod(index, self._columns)
            self._layout.addWidget(card, row, column)
            if previous is not None:
                QWidget.setTabOrder(previous, card)
            previous = card

        if self._cards:
            self.setFocusProxy(next(iter(self._cards.values())))

        max_columns = max(self._columns, len(self._cards), 1)
        for column in range(max_columns):
            self._layout.setColumnStretch(
                column,
                1 if column < self._columns else 0,
            )

    def _clear_layout(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    @staticmethod
    def _tone(value: str) -> CardTone:
        try:
            return CardTone(value)
        except ValueError:
            return CardTone.DEFAULT


__all__ = ["KeyboardKpiCard", "KpiCenter"]
