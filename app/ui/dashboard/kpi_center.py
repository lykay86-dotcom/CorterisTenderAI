"""KPI Center for Dashboard 1.0."""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QSizePolicy, QWidget

from app.ui.theme.colors import ThemeName
from app.ui.viewmodels.dashboard_viewmodel import DashboardKpi
from app.ui.widgets.card import CardTone, KpiCard


class KpiCenter(QWidget):
    """Responsive group of interactive KPI cards."""

    kpi_clicked = Signal(str)

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

    def set_kpis(self, kpis: Iterable[DashboardKpi]) -> None:
        """Replace all KPI cards."""
        self._clear_layout()
        self._cards.clear()
        self._kpis = {kpi.key: kpi for kpi in kpis}

        for index, kpi in enumerate(self._kpis.values()):
            card = self._create_card(kpi)
            self._cards[kpi.key] = card
            row, column = divmod(index, self._columns)
            self._layout.addWidget(card, row, column)

        for column in range(self._columns):
            self._layout.setColumnStretch(column, 1)

    def update_kpi(self, kpi: DashboardKpi) -> None:
        """Update one KPI card or create it when missing."""
        self._kpis[kpi.key] = kpi
        card = self._cards.get(kpi.key)
        if card is None:
            self.set_kpis(self._kpis.values())
            return

        card.title = kpi.title
        card.value = kpi.value
        card.icon_text = kpi.icon_text
        card.set_trend(kpi.trend, self._tone(kpi.tone))
        card.setAccessibleDescription(
            f"{kpi.title}: {kpi.value}. {kpi.trend}"
        )

    def set_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        for card in self._cards.values():
            card.set_theme(self._theme)

    def _create_card(self, kpi: DashboardKpi) -> KpiCard:
        card = KpiCard(
            kpi.title,
            kpi.value,
            trend=kpi.trend,
            trend_tone=self._tone(kpi.tone),
            icon_text=kpi.icon_text,
            theme=self._theme,
            clickable=True,
        )
        card.setMinimumHeight(132)
        card.setAccessibleDescription(
            f"{kpi.title}: {kpi.value}. {kpi.trend}"
        )
        card.clicked.connect(
            lambda key=kpi.key: self.kpi_clicked.emit(key)
        )
        return card

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


__all__ = ["KpiCenter"]
