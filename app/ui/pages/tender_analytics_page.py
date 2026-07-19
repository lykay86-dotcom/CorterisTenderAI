"""Accessible RM-147 tender analytics page using the RM-146 chart package."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.tenders.analytics import (
    AnalyticsTenderFact,
    TenderAnalyticsChartAdapter,
    TenderAnalyticsSnapshot,
)
from app.ui.charts import (
    ChartAxis,
    ChartAxisScale,
    ChartKind,
    ChartSelection,
    ChartSpec,
    ChartState,
    ChartWidget,
)
from app.ui.theme.colors import ThemeName, get_palette


_METRIC_IDS = (
    "tenders_discovered",
    "tenders_by_status",
    "source_observations",
    "application_deadline_horizon",
)
_METRIC_TITLES = (
    "Обнаруженные тендеры",
    "Текущий состав по статусу",
    "Наблюдения по источникам",
    "Горизонт сроков подачи",
)


class TenderAnalyticsPage(QWidget):
    """One responsive analytics surface with visible text equivalents."""

    refresh_requested = Signal()
    filters_applied = Signal()
    filters_reset = Signal()
    export_requested = Signal(str)
    contributor_activated = Signal(str)

    def __init__(
        self,
        *,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = ThemeName(theme)
        self._snapshot: TenderAnalyticsSnapshot | None = None
        self._adapter = TenderAnalyticsChartAdapter()
        self._charts: dict[str, ChartWidget] = {}
        self.setObjectName("TenderAnalyticsPage")

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Аналитика тендеров", self)
        title.setObjectName("TenderAnalyticsTitle")
        title.setAccessibleName("Аналитика тендеров")
        header.addWidget(title)
        header.addStretch(1)
        self.refresh_button = QPushButton("Обновить локальные данные", self)
        self.refresh_button.setObjectName("TenderAnalyticsRefresh")
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        header.addWidget(self.refresh_button)
        root.addLayout(header)

        filters = QFrame(self)
        filters.setObjectName("TenderAnalyticsFilters")
        filter_layout = QHBoxLayout(filters)
        self.preset_combo = QComboBox(filters)
        self.preset_combo.setObjectName("TenderAnalyticsPreset")
        self.preset_combo.addItem("Последние 30 полных дней", "last_30_complete_days")
        self.preset_combo.addItem("Последние 7 полных дней", "last_7_complete_days")
        self.preset_combo.addItem("Текущий месяц", "current_month")
        self.preset_combo.addItem("Свои границы", "custom")
        self.preset_combo.addItem("Всё доступное", "all_available")
        today = QDate.currentDate()
        self.start_date = QDateEdit(today.addDays(-30), filters)
        self.start_date.setObjectName("TenderAnalyticsStartDate")
        self.start_date.setCalendarPopup(True)
        self.start_date.setAccessibleName("Начало интервала")
        self.end_date = QDateEdit(today, filters)
        self.end_date.setObjectName("TenderAnalyticsEndDate")
        self.end_date.setCalendarPopup(True)
        self.end_date.setAccessibleName("Конец интервала, исключая указанную дату")
        self.grain_combo = QComboBox(filters)
        self.grain_combo.setObjectName("TenderAnalyticsGrain")
        self.grain_combo.addItem("Дни", "day")
        self.grain_combo.addItem("Недели", "week")
        self.grain_combo.addItem("Месяцы", "month")
        self.source_combo = QComboBox(filters)
        self.source_combo.setObjectName("TenderAnalyticsSource")
        self.source_combo.addItem("Все источники", "")
        self.status_combo = QComboBox(filters)
        self.status_combo.setObjectName("TenderAnalyticsStatus")
        self.status_combo.addItem("Все статусы", "")
        for status in (
            "published",
            "accepting_applications",
            "applications_closed",
            "review",
            "completed",
            "cancelled",
            "unknown",
        ):
            self.status_combo.addItem(status, status)
        self.law_combo = QComboBox(filters)
        self.law_combo.setObjectName("TenderAnalyticsLaw")
        self.law_combo.addItem("Все законы", "")
        self.include_archived = QCheckBox("Включить архив", filters)
        self.include_archived.setObjectName("TenderAnalyticsArchived")
        self.apply_button = QPushButton("Применить", filters)
        self.apply_button.setObjectName("TenderAnalyticsApply")
        self.reset_button = QPushButton("Сбросить", filters)
        self.reset_button.setObjectName("TenderAnalyticsReset")
        self.apply_button.clicked.connect(self.filters_applied.emit)
        self.reset_button.clicked.connect(self._reset_filters)
        filter_layout.addWidget(self.preset_combo)
        filter_layout.addWidget(self.start_date)
        filter_layout.addWidget(self.end_date)
        filter_layout.addWidget(self.grain_combo)
        filter_layout.addWidget(self.source_combo)
        filter_layout.addWidget(self.status_combo)
        filter_layout.addWidget(self.law_combo)
        filter_layout.addWidget(self.include_archived)
        filter_layout.addStretch(1)
        filter_layout.addWidget(self.apply_button)
        filter_layout.addWidget(self.reset_button)
        root.addWidget(filters)

        self.coverage_label = QLabel("Загрузка локального снимка…", self)
        self.coverage_label.setObjectName("TenderAnalyticsCoverage")
        self.coverage_label.setWordWrap(True)
        root.addWidget(self.coverage_label)

        splitter = QSplitter(self)
        chart_host = QWidget(splitter)
        chart_grid = QGridLayout(chart_host)
        chart_grid.setContentsMargins(0, 0, 0, 0)
        palette = get_palette(self._theme)
        for index, (metric_id, metric_title) in enumerate(
            zip(_METRIC_IDS, _METRIC_TITLES, strict=True)
        ):
            is_time = metric_id == "tenders_discovered"
            spec = ChartSpec(
                chart_id=metric_id.replace("_", "-"),
                kind=ChartKind.LINE if is_time else ChartKind.BAR,
                title=metric_title,
                x_axis=ChartAxis(ChartAxisScale.TIME if is_time else ChartAxisScale.CATEGORY),
                y_axis=ChartAxis(ChartAxisScale.NUMERIC),
                series=(),
                state=ChartState.LOADING,
            )
            chart = ChartWidget(spec, palette=palette, parent=chart_host)
            chart.setMinimumHeight(250)
            chart.selection_changed.connect(
                lambda selection, current_id=metric_id: self._show_selection(current_id, selection)
            )
            chart.selection_confirmed.connect(
                lambda selection, current_id=metric_id: self._activate_selection(
                    current_id, selection
                )
            )
            self._charts[metric_id] = chart
            chart_grid.addWidget(chart, index // 2, index % 2)

        details = QWidget(splitter)
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(8, 0, 0, 0)
        self.selection_label = QLabel("Выберите точку графика", details)
        self.selection_label.setWordWrap(True)
        self.contributor_list = QListWidget(details)
        self.contributor_list.setObjectName("TenderAnalyticsContributors")
        self.contributor_list.itemActivated.connect(
            lambda item: self.contributor_activated.emit(item.data(Qt.ItemDataRole.UserRole))
        )
        details_layout.addWidget(self.selection_label)
        details_layout.addWidget(self.contributor_list, 1)
        splitter.addWidget(chart_host)
        splitter.addWidget(details)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

        self.text_table = QTableWidget(self)
        self.text_table.setObjectName("TenderAnalyticsTextTable")
        self.text_table.setColumnCount(5)
        self.text_table.setHorizontalHeaderLabels(
            ("Метрика", "Категория", "Значение", "Состояние", "Участники")
        )
        self.text_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        root.addWidget(self.text_table)

        exports = QHBoxLayout()
        exports.addStretch(1)
        self.export_json_button = QPushButton("Экспорт JSON", self)
        self.export_csv_button = QPushButton("Экспорт CSV", self)
        self.export_json_button.clicked.connect(lambda: self.export_requested.emit("json"))
        self.export_csv_button.clicked.connect(lambda: self.export_requested.emit("csv"))
        self.export_json_button.setEnabled(False)
        self.export_csv_button.setEnabled(False)
        exports.addWidget(self.export_json_button)
        exports.addWidget(self.export_csv_button)
        root.addLayout(exports)

        focus_chain = (
            self.preset_combo,
            self.start_date,
            self.end_date,
            self.grain_combo,
            self.source_combo,
            self.status_combo,
            self.law_combo,
            self.include_archived,
            self.apply_button,
            self.reset_button,
            self.refresh_button,
            *(chart.canvas for chart in self._charts.values()),
            self.contributor_list,
            self.text_table,
            self.export_json_button,
            self.export_csv_button,
        )
        for current, following in zip(focus_chain, focus_chain[1:]):
            QWidget.setTabOrder(current, following)

    @property
    def snapshot(self) -> TenderAnalyticsSnapshot | None:
        return self._snapshot

    def filter_values(
        self,
    ) -> tuple[
        str,
        date,
        date,
        str,
        tuple[str, ...],
        tuple[str, ...],
        tuple[str, ...],
        bool,
    ]:
        source_id = str(self.source_combo.currentData() or "")
        status = str(self.status_combo.currentData() or "")
        law = str(self.law_combo.currentData() or "")
        return (
            str(self.preset_combo.currentData()),
            self.start_date.date().toPython(),
            self.end_date.date().toPython(),
            str(self.grain_combo.currentData()),
            (source_id,) if source_id else (),
            (status,) if status else (),
            (law,) if law else (),
            self.include_archived.isChecked(),
        )

    def set_filter_options(self, records: tuple[AnalyticsTenderFact, ...]) -> None:
        self._replace_combo_options(
            self.source_combo,
            "Все источники",
            tuple(sorted({item.source_id for item in records})),
        )
        self._replace_combo_options(
            self.law_combo,
            "Все законы",
            tuple(sorted({item.law for item in records if item.law.strip()})),
        )

    def set_loading(self, *, retain_snapshot: bool) -> None:
        self.refresh_button.setEnabled(False)
        if not retain_snapshot:
            self.coverage_label.setText("Загрузка локального снимка…")
            self.export_json_button.setEnabled(False)
            self.export_csv_button.setEnabled(False)

    def set_snapshot(self, snapshot: TenderAnalyticsSnapshot) -> None:
        self._snapshot = snapshot
        self.refresh_button.setEnabled(True)
        self.export_json_button.setEnabled(True)
        self.export_csv_button.setEnabled(True)
        coverage = ", ".join(
            f"{item.source_id}: {item.outcome}"
            + ("" if item.item_count is None else f" ({item.item_count})")
            for item in snapshot.coverage
        )
        self.coverage_label.setText(
            f"Состояние: {snapshot.state.value}. Источники: {coverage or 'нет наблюдений'}. "
            f"Снимок: {snapshot.fingerprint[:12]}"
        )
        for metric in snapshot.metrics:
            chart = self._charts.get(metric.metric_id)
            if chart is not None:
                chart.set_chart(self._adapter.adapt(metric, snapshot.coverage))
        rows = tuple((metric, point) for metric in snapshot.metrics for point in metric.points)
        self.text_table.setRowCount(len(rows))
        for row, (metric, point) in enumerate(rows):
            values = (
                metric.title,
                point.bucket_label,
                str(point.value),
                metric.state.value,
                str(len(point.contributor_ids)),
            )
            for column, value in enumerate(values):
                self.text_table.setItem(row, column, QTableWidgetItem(value))

    def set_error(self, reason_code: str, *, stale: bool) -> None:
        self.refresh_button.setEnabled(True)
        if stale:
            self.coverage_label.setText(f"Показан сохранённый снимок: stale ({reason_code}).")
            return
        self.coverage_label.setText(f"Локальная аналитика недоступна ({reason_code}).")

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)
        for chart in self._charts.values():
            chart.set_palette(palette)

    def _reset_filters(self) -> None:
        self.preset_combo.setCurrentIndex(0)
        today = QDate.currentDate()
        self.start_date.setDate(today.addDays(-30))
        self.end_date.setDate(today)
        self.grain_combo.setCurrentIndex(0)
        self.include_archived.setChecked(False)
        self.source_combo.setCurrentIndex(0)
        self.status_combo.setCurrentIndex(0)
        self.law_combo.setCurrentIndex(0)
        self.filters_reset.emit()

    @staticmethod
    def _replace_combo_options(
        combo: QComboBox,
        all_label: str,
        values: tuple[str, ...],
    ) -> None:
        selected = str(combo.currentData() or "")
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(all_label, "")
        for value in values:
            combo.addItem(value, value)
        index = combo.findData(selected)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

    def _show_selection(
        self,
        metric_id: str,
        selection: ChartSelection | None,
    ) -> None:
        self.contributor_list.clear()
        if self._snapshot is None or selection is None:
            self.selection_label.setText("Выберите точку графика")
            return
        metric = next(
            (item for item in self._snapshot.metrics if item.metric_id == metric_id), None
        )
        point = (
            next(
                (item for item in metric.points if item.point_id == selection.point_id),
                None,
            )
            if metric is not None
            else None
        )
        if point is None:
            self.selection_label.setText("Выбор не относится к текущему снимку")
            return
        self.selection_label.setText(
            f"{point.bucket_label}: {point.value}; участников: {len(point.contributor_ids)}"
        )
        for registry_key in point.contributor_ids:
            # QListWidget accepts QListWidgetItem; construct through addItem to keep
            # the displayed string and then attach the exact internal identity.
            self.contributor_list.addItem(registry_key)
            list_item = self.contributor_list.item(self.contributor_list.count() - 1)
            list_item.setData(Qt.ItemDataRole.UserRole, registry_key)

    def _activate_selection(self, metric_id: str, selection: ChartSelection) -> None:
        self._show_selection(metric_id, selection)
        if self.contributor_list.count() == 1:
            self.contributor_activated.emit(
                self.contributor_list.item(0).data(Qt.ItemDataRole.UserRole)
            )


__all__ = ["TenderAnalyticsPage"]
