"""Local tender-registry browser with filtering and archive controls."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from html import escape

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.tenders.collector.freshness import (
    DeadlineTimezoneStatus,
    TenderFreshnessState,
    TenderFreshnessStatus,
)
from app.tenders.collector.store import CollectorStateRepository
from app.tenders.collector.verification import (
    TenderVerificationState,
    TenderVerificationStatus,
)
from app.tenders.collector.verification_review import STATUS_LABELS
from app.tenders.tender_registry import (
    TenderRegistryQuery,
    TenderRegistryRecord,
    TenderRegistryRepository,
    TenderRegistrySort,
)
from app.ui.theme.colors import ThemeName, get_palette


_STATE_ACTIVE_ACCEPTED = "active_accepted"
_STATE_ACTIVE_ALL = "active_all"
_STATE_ARCHIVED = "archived"
_STATE_ALL = "all"


class TenderRegistryDialog(QDialog):
    """Browse saved tenders and their discovery history."""

    profiles_requested = Signal()
    documents_requested = Signal(str)
    analysis_requested = Signal(str)
    score_requested = Signal(str)
    full_analysis_requested = Signal(str)
    verification_requested = Signal(str)

    def __init__(
        self,
        repository: TenderRegistryRepository,
        *,
        verification_repository: CollectorStateRepository | None = None,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.repository = repository
        self.verification_repository = (
            verification_repository
            or CollectorStateRepository(repository.path)
        )
        try:
            self._theme = ThemeName(theme)
        except (TypeError, ValueError, AttributeError):
            self._theme = ThemeName.DARK
        self._records: tuple[TenderRegistryRecord, ...] = ()
        self._verification_states: dict[
            str, TenderVerificationState
        ] = {}
        self._freshness_states: dict[str, TenderFreshnessState] = {}

        self.setWindowTitle("Corteris Tender AI — реестр тендеров")
        self.setModal(False)
        self.resize(1480, 860)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        root.addWidget(self._build_summary())
        root.addWidget(self._build_filters())

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, 1)

        table_frame = QFrame(splitter)
        table_frame.setObjectName("TenderRegistryTableFrame")
        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(10, 10, 10, 10)
        table_layout.setSpacing(8)

        table_title = QLabel("Сохранённые закупки", table_frame)
        table_title.setObjectName("TenderRegistrySectionTitle")
        table_layout.addWidget(table_title)

        self.table = QTableWidget(table_frame)
        self.table.setObjectName("TenderRegistryTable")
        self.table.setColumnCount(13)
        self.table.setHorizontalHeaderLabels(
            (
                "Балл",
                "Результат",
                "Достоверность",
                "Свежесть",
                "Номер",
                "Закупка",
                "Заказчик",
                "Регион",
                "Цена",
                "Срок подачи",
                "Обнаружено",
                "Последний раз",
                "Источник",
            )
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            5,
            QHeaderView.ResizeMode.Stretch,
        )
        self.table.itemSelectionChanged.connect(
            self._show_selected_record
        )
        self.table.cellDoubleClicked.connect(
            lambda _row, _column: self._open_selected_source()
        )
        table_layout.addWidget(self.table, 1)
        splitter.addWidget(table_frame)

        details_frame = QFrame(splitter)
        details_frame.setObjectName("TenderRegistryDetailsFrame")
        details_layout = QVBoxLayout(details_frame)
        details_layout.setContentsMargins(12, 12, 12, 12)
        details_layout.setSpacing(8)

        details_title = QLabel("Карточка закупки", details_frame)
        details_title.setObjectName("TenderRegistrySectionTitle")
        details_layout.addWidget(details_title)

        self.details = QTextBrowser(details_frame)
        self.details.setObjectName("TenderRegistryDetails")
        self.details.setOpenExternalLinks(False)
        self.details.anchorClicked.connect(QDesktopServices.openUrl)
        details_layout.addWidget(self.details, 1)

        history_title = QLabel(
            "История обнаружений",
            details_frame,
        )
        history_title.setObjectName("TenderRegistrySectionTitle")
        details_layout.addWidget(history_title)

        self.history_table = QTableWidget(details_frame)
        self.history_table.setObjectName("TenderRegistryHistoryTable")
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels(
            (
                "Дата",
                "Профиль",
                "Балл",
                "Результат",
                "Направления",
            )
        )
        self.history_table.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.history_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.history_table.horizontalHeader().setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )
        details_layout.addWidget(self.history_table, 1)
        splitter.addWidget(details_frame)
        splitter.setSizes([970, 510])

        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self.open_source_button = QPushButton(
            "Открыть в источнике",
            self,
        )
        self.open_source_button.setObjectName("PrimaryActionButton")
        self.open_source_button.clicked.connect(
            self._open_selected_source
        )

        self.full_analysis_button = QPushButton(
            "Скачать документы и провести полный анализ",
            self,
        )
        self.full_analysis_button.setObjectName("PrimaryActionButton")
        self.full_analysis_button.clicked.connect(
            self._request_selected_full_analysis
        )

        self.analysis_button = QPushButton(
            "Анализ требований",
            self,
        )
        self.analysis_button.setObjectName("PrimaryActionButton")
        self.analysis_button.clicked.connect(
            self._request_selected_analysis
        )

        self.score_button = QPushButton(
            "Оценка участия",
            self,
        )
        self.score_button.setObjectName("PrimaryActionButton")
        self.score_button.clicked.connect(
            self._request_selected_score
        )

        self.verification_button = QPushButton(
            "Достоверность и источники",
            self,
        )
        self.verification_button.clicked.connect(
            self._request_selected_verification
        )

        self.documents_button = QPushButton(
            "Скачать документацию",
            self,
        )
        self.documents_button.clicked.connect(
            self._request_selected_documents
        )

        self.archive_button = QPushButton(
            "В архив",
            self,
        )
        self.archive_button.clicked.connect(
            self._toggle_selected_archive
        )

        self.refresh_button = QPushButton(
            "Обновить",
            self,
        )
        self.refresh_button.clicked.connect(self.refresh_records)

        self.profiles_button = QPushButton(
            "Профили поиска",
            self,
        )
        self.profiles_button.clicked.connect(
            self.profiles_requested.emit
        )

        action_row.addWidget(self.open_source_button)
        action_row.addWidget(self.full_analysis_button)
        action_row.addWidget(self.analysis_button)
        action_row.addWidget(self.score_button)
        action_row.addWidget(self.verification_button)
        action_row.addWidget(self.documents_button)
        action_row.addWidget(self.archive_button)
        action_row.addWidget(self.refresh_button)
        action_row.addWidget(self.profiles_button)
        action_row.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close,
            self,
        )
        buttons.button(
            QDialogButtonBox.StandardButton.Close
        ).setText("Закрыть")
        buttons.rejected.connect(self.reject)
        action_row.addWidget(buttons)
        root.addLayout(action_row)

        self.status_label = QLabel("", self)
        self.status_label.setObjectName("TenderRegistryStatus")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.apply_theme(self._theme)
        self.refresh_records()

    @property
    def records(self) -> tuple[TenderRegistryRecord, ...]:
        return self._records

    def _build_summary(self) -> QFrame:
        frame = QFrame(self)
        frame.setObjectName("TenderRegistrySummary")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(22)

        heading = QVBoxLayout()
        title = QLabel("Реестр найденных тендеров", frame)
        title.setObjectName("TenderRegistryTitle")
        subtitle = QLabel(
            (
                "Локальная история закупок без повторного добавления. "
                "Поиск, сортировка, архив и история обнаружений."
            ),
            frame,
        )
        subtitle.setObjectName("TenderRegistrySubtitle")
        subtitle.setWordWrap(True)
        heading.addWidget(title)
        heading.addWidget(subtitle)
        layout.addLayout(heading, 1)

        self.total_metric = self._add_metric(
            layout,
            frame,
            "Всего",
        )
        self.active_metric = self._add_metric(
            layout,
            frame,
            "Активные",
        )
        self.accepted_metric = self._add_metric(
            layout,
            frame,
            "Релевантные",
        )
        self.archived_metric = self._add_metric(
            layout,
            frame,
            "Архив",
        )
        self.runs_metric = self._add_metric(
            layout,
            frame,
            "Запуски",
        )
        return frame

    @staticmethod
    def _add_metric(
        layout: QHBoxLayout,
        parent: QWidget,
        label: str,
    ) -> QLabel:
        column = QVBoxLayout()
        value = QLabel("0", parent)
        value.setObjectName("TenderRegistryMetricValue")
        value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        caption = QLabel(label, parent)
        caption.setObjectName("TenderRegistryMetricLabel")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        column.addWidget(value)
        column.addWidget(caption)
        layout.addLayout(column)
        return value

    def _build_filters(self) -> QFrame:
        frame = QFrame(self)
        frame.setObjectName("TenderRegistryFilters")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        self.search_edit = QLineEdit(frame)
        self.search_edit.setObjectName("TenderRegistrySearch")
        self.search_edit.setPlaceholderText(
            "Поиск по номеру, названию, заказчику, ИНН или региону"
        )
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.returnPressed.connect(self.refresh_records)
        layout.addWidget(self.search_edit, 1)

        self.state_combo = QComboBox(frame)
        self.state_combo.setObjectName("TenderRegistryState")
        self.state_combo.addItem(
            "Активные релевантные",
            _STATE_ACTIVE_ACCEPTED,
        )
        self.state_combo.addItem("Все активные", _STATE_ACTIVE_ALL)
        self.state_combo.addItem("Архив", _STATE_ARCHIVED)
        self.state_combo.addItem("Все записи", _STATE_ALL)
        self.state_combo.currentIndexChanged.connect(
            self.refresh_records
        )
        layout.addWidget(self.state_combo)

        score_label = QLabel("Балл от", frame)
        score_label.setObjectName("TenderRegistryFilterLabel")
        layout.addWidget(score_label)

        self.minimum_score_spin = QSpinBox(frame)
        self.minimum_score_spin.setObjectName(
            "TenderRegistryMinimumScore"
        )
        self.minimum_score_spin.setRange(0, 100)
        self.minimum_score_spin.setValue(0)
        self.minimum_score_spin.setSuffix(" / 100")
        self.minimum_score_spin.valueChanged.connect(
            self.refresh_records
        )
        layout.addWidget(self.minimum_score_spin)

        self.sort_combo = QComboBox(frame)
        self.sort_combo.setObjectName("TenderRegistrySort")
        self.sort_combo.addItem(
            "Сначала релевантные",
            TenderRegistrySort.RELEVANCE_DESC.value,
        )
        self.sort_combo.addItem(
            "Ближайший срок",
            TenderRegistrySort.DEADLINE_ASC.value,
        )
        self.sort_combo.addItem(
            "Недавно обнаруженные",
            TenderRegistrySort.LAST_SEEN_DESC.value,
        )
        self.sort_combo.addItem(
            "Новые в реестре",
            TenderRegistrySort.FIRST_SEEN_DESC.value,
        )
        self.sort_combo.addItem(
            "Сначала дорогие",
            TenderRegistrySort.PRICE_DESC.value,
        )
        self.sort_combo.addItem(
            "По названию",
            TenderRegistrySort.TITLE_ASC.value,
        )
        self.sort_combo.currentIndexChanged.connect(
            self.refresh_records
        )
        layout.addWidget(self.sort_combo)

        self.apply_filter_button = QPushButton("Найти", frame)
        self.apply_filter_button.clicked.connect(self.refresh_records)
        layout.addWidget(self.apply_filter_button)
        return frame

    def current_query(self) -> TenderRegistryQuery:
        state = str(self.state_combo.currentData() or "")
        sort_value = str(
            self.sort_combo.currentData()
            or TenderRegistrySort.RELEVANCE_DESC.value
        )
        return TenderRegistryQuery(
            text=self.search_edit.text().strip(),
            include_archived=state == _STATE_ALL,
            archived_only=state == _STATE_ARCHIVED,
            accepted_only=state == _STATE_ACTIVE_ACCEPTED,
            minimum_score=self.minimum_score_spin.value(),
            sort=TenderRegistrySort(sort_value),
            limit=1000,
        )

    def refresh_records(self) -> None:
        selected_key = (
            self.selected_record().registry_key
            if self.selected_record() is not None
            else ""
        )
        try:
            statistics = self.repository.statistics()
            query = self.current_query()
            records = self.repository.search_tenders(query)
            total_matches = self.repository.count_search_results(query)
            registry_keys = tuple(
                item.registry_key for item in records
            )
            self._verification_states = dict(
                self.verification_repository.list_verification_states(
                    registry_keys
                )
            )
            self._freshness_states = dict(
                self.verification_repository.list_freshness_states(
                    registry_keys
                )
            )
        except Exception as exc:
            self.set_status(
                f"Не удалось прочитать реестр: {exc}",
                error=True,
            )
            return

        self.total_metric.setText(str(statistics.total_count))
        self.active_metric.setText(str(statistics.active_count))
        self.accepted_metric.setText(str(statistics.accepted_count))
        self.archived_metric.setText(str(statistics.archived_count))
        self.runs_metric.setText(str(statistics.search_run_count))

        self._records = records
        self._populate_table(selected_key)
        self.set_status(
            (
                f"Показано {len(records)} из {total_matches}. "
                f"База: {self.repository.path}"
            )
        )

    def _populate_table(self, selected_key: str = "") -> None:
        self.table.setRowCount(len(self._records))
        selected_row = -1

        for row, record in enumerate(self._records):
            result_text = (
                "Архив"
                if record.archived
                else ("Подходит" if record.last_accepted else "Отсеяно")
            )
            verification_state = self._verification_states.get(
                record.registry_key
            )
            verification_text = _verification_text(verification_state)
            freshness_state = self._freshness_states.get(
                record.registry_key
            )
            freshness_text = _freshness_text(freshness_state)
            values = (
                str(record.relevance_score),
                result_text,
                verification_text,
                freshness_text,
                record.procurement_number,
                record.title,
                record.customer_name,
                record.region or "—",
                _format_price(record.price_amount, record.currency),
                _format_timestamp(record.application_deadline),
                str(record.seen_count),
                _format_timestamp(record.last_seen_at),
                record.source,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(
                        Qt.ItemDataRole.UserRole,
                        record.registry_key,
                    )
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignCenter
                    )
                if column == 2:
                    item.setForeground(
                        QColor(
                            _verification_color(
                                verification_state,
                                get_palette(self._theme),
                            )
                        )
                    )
                    item.setToolTip(
                        _verification_tooltip(verification_state)
                    )
                if column == 3:
                    item.setForeground(
                        QColor(
                            _freshness_color(
                                freshness_state,
                                get_palette(self._theme),
                            )
                        )
                    )
                    item.setToolTip(
                        _freshness_tooltip(freshness_state)
                    )
                self.table.setItem(row, column, item)

            if record.registry_key == selected_key:
                selected_row = row

        if self._records:
            target_row = selected_row if selected_row >= 0 else 0
            # QTableWidget.selectRow() may update only the selection
            # model without establishing a current index in offscreen
            # and some platform styles. Set the current cell first so
            # action buttons and signal handlers can resolve the row
            # immediately, even before the event loop processes events.
            self.table.setCurrentCell(target_row, 0)
            self.table.selectRow(target_row)
            self._show_selected_record()
        else:
            self.details.setHtml(
                "<h3>Записи не найдены</h3>"
                "<p>Измените строку поиска, состояние или минимальный "
                "балл. Новые результаты появляются после запуска "
                "поискового профиля.</p>"
            )
            self.history_table.setRowCount(0)
            self.open_source_button.setEnabled(False)
            self.full_analysis_button.setEnabled(False)
            self.analysis_button.setEnabled(False)
            self.documents_button.setEnabled(False)
            self.verification_button.setEnabled(False)
            self.archive_button.setEnabled(False)

    def selected_record(self) -> TenderRegistryRecord | None:
        """Return the selected record without relying only on currentRow()."""

        row = -1
        selection_model = self.table.selectionModel()
        if selection_model is not None:
            selected_rows = selection_model.selectedRows(0)
            if selected_rows:
                row = selected_rows[0].row()

        if row < 0:
            row = self.table.currentRow()

        if not 0 <= row < len(self._records):
            return None
        return self._records[row]

    def _show_selected_record(self) -> None:
        record = self.selected_record()
        if record is None:
            self.open_source_button.setEnabled(False)
            self.full_analysis_button.setEnabled(False)
            self.analysis_button.setEnabled(False)
            self.documents_button.setEnabled(False)
            self.verification_button.setEnabled(False)
            self.archive_button.setEnabled(False)
            return

        self.open_source_button.setEnabled(bool(record.source_url))
        self.full_analysis_button.setEnabled(True)
        self.analysis_button.setEnabled(True)
        self.documents_button.setEnabled(True)
        self.verification_button.setEnabled(True)
        self.archive_button.setEnabled(True)
        self.archive_button.setText(
            "Вернуть из архива" if record.archived else "В архив"
        )

        verification_state = self._verification_states.get(
            record.registry_key
        )
        freshness_state = self._freshness_states.get(
            record.registry_key
        )
        state = (
            "Архив"
            if record.archived
            else ("Подходит" if record.last_accepted else "Отсеяно")
        )
        self.details.setHtml(
            f"<h2>{escape(record.title)}</h2>"
            f"<p><b>Номер:</b> "
            f"{escape(record.procurement_number or '—')}</p>"
            f"<p><b>Заказчик:</b> "
            f"{escape(record.customer_name or '—')}</p>"
            f"<p><b>ИНН:</b> "
            f"{escape(record.customer_inn or '—')}</p>"
            f"<p><b>Регион:</b> "
            f"{escape(record.region or '—')}</p>"
            f"<p><b>Цена:</b> "
            f"{escape(_format_price(record.price_amount, record.currency))}</p>"
            f"<p><b>Срок подачи:</b> "
            f"{escape(_deadline_display(record.application_deadline, freshness_state))}</p>"
            f"<p><b>Состояние:</b> {escape(state)}</p>"
            f"<p><b>Достоверность данных:</b> "
            f"{escape(_verification_text(verification_state))}</p>"
            f"<p><b>Свежесть данных:</b> "
            f"{escape(_freshness_text(freshness_state))}</p>"
            f"<p><b>Следующая проверка:</b> "
            f"{escape(_freshness_due_text(freshness_state))}</p>"
            f"<p><b>Последняя релевантность:</b> "
            f"{record.relevance_score}/100 "
            f"({escape(record.relevance_grade)})</p>"
            f"<p><b>Обнаружено:</b> {record.seen_count} раз</p>"
            f"<p><b>Первое обнаружение:</b> "
            f"{escape(_format_timestamp(record.first_seen_at))}</p>"
            f"<p><b>Последнее обнаружение:</b> "
            f"{escape(_format_timestamp(record.last_seen_at))}</p>"
            f"<p><b>Источник:</b> {escape(record.source)}</p>"
            f"<p><a href=\"{escape(record.source_url)}\">"
            "Открыть официальную карточку закупки</a></p>"
        )
        self._populate_history(record.registry_key)

    def _populate_history(self, registry_key: str) -> None:
        try:
            occurrences = self.repository.list_tender_occurrences(
                registry_key,
                limit=100,
            )
        except Exception as exc:
            self.history_table.setRowCount(0)
            self.set_status(
                f"Не удалось загрузить историю: {exc}",
                error=True,
            )
            return

        self.history_table.setRowCount(len(occurrences))
        for row, occurrence in enumerate(occurrences):
            values = (
                _format_timestamp(occurrence.executed_at),
                occurrence.profile_name,
                str(occurrence.relevance_score),
                "Подходит" if occurrence.accepted else "Отсеяно",
                ", ".join(occurrence.directions) or "—",
            )
            for column, value in enumerate(values):
                self.history_table.setItem(
                    row,
                    column,
                    QTableWidgetItem(value),
                )

    def _toggle_selected_archive(self) -> None:
        record = self.selected_record()
        if record is None:
            return
        new_state = not record.archived
        try:
            changed = self.repository.set_archived(
                record.registry_key,
                new_state,
            )
        except Exception as exc:
            self.set_status(
                f"Не удалось изменить архив: {exc}",
                error=True,
            )
            return

        if not changed:
            self.set_status(
                "Запись уже отсутствует в реестре.",
                error=True,
            )
            return

        self.set_status(
            (
                "Закупка перемещена в архив."
                if new_state
                else "Закупка возвращена из архива."
            )
        )
        self.refresh_records()

    def _request_selected_full_analysis(self) -> None:
        record = self.selected_record()
        if record is None:
            return
        self.full_analysis_requested.emit(record.registry_key)

    def _request_selected_analysis(self) -> None:
        record = self.selected_record()
        if record is None:
            return
        self.analysis_requested.emit(record.registry_key)

    def _request_selected_score(self) -> None:
        record = self.selected_record()
        if record is None:
            return
        self.score_requested.emit(record.registry_key)

    def _request_selected_verification(self) -> None:
        record = self.selected_record()
        if record is None:
            return
        self.verification_requested.emit(record.registry_key)

    def _request_selected_documents(self) -> None:
        record = self.selected_record()
        if record is None:
            return
        self.documents_requested.emit(record.registry_key)

    def _open_selected_source(self) -> None:
        record = self.selected_record()
        if record is None or not record.source_url:
            return
        QDesktopServices.openUrl(QUrl(record.source_url))

    def set_status(self, message: str, *, error: bool = False) -> None:
        self.status_label.setText(message)
        self.status_label.setProperty("error", error)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)
        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {palette.app_background};
                color: {palette.text_primary};
            }}
            QFrame#TenderRegistrySummary,
            QFrame#TenderRegistryFilters,
            QFrame#TenderRegistryTableFrame,
            QFrame#TenderRegistryDetailsFrame {{
                background-color: {palette.card_background};
                border: 1px solid {palette.border_default};
                border-radius: 9px;
            }}
            QLabel#TenderRegistryTitle {{
                color: {palette.text_primary};
                font-size: 22px;
                font-weight: 700;
            }}
            QLabel#TenderRegistrySubtitle,
            QLabel#TenderRegistryMetricLabel,
            QLabel#TenderRegistryFilterLabel {{
                color: {palette.text_secondary};
            }}
            QLabel#TenderRegistryMetricValue {{
                color: {palette.brand_accent};
                font-size: 22px;
                font-weight: 700;
            }}
            QLabel#TenderRegistrySectionTitle {{
                color: {palette.text_primary};
                font-size: 14px;
                font-weight: 700;
            }}
            QLabel#TenderRegistryStatus {{
                color: {palette.text_secondary};
            }}
            QLabel#TenderRegistryStatus[error="true"] {{
                color: {palette.danger};
            }}
            QLineEdit,
            QComboBox,
            QSpinBox {{
                min-height: 32px;
                color: {palette.text_primary};
                background-color: {palette.input_background};
                border: 1px solid {palette.border_default};
                border-radius: 7px;
                padding: 3px 8px;
            }}
            QLineEdit:focus,
            QComboBox:focus,
            QSpinBox:focus {{
                border-color: {palette.focus_ring};
            }}
            QTableWidget#TenderRegistryTable,
            QTableWidget#TenderRegistryHistoryTable {{
                color: {palette.text_primary};
                background-color: {palette.input_background};
                alternate-background-color: {palette.panel_background};
                border: 1px solid {palette.border_default};
                gridline-color: {palette.divider};
                selection-background-color: {palette.selected_background};
                selection-color: {palette.text_primary};
            }}
            QHeaderView::section {{
                color: {palette.text_secondary};
                background-color: {palette.elevated_background};
                border: none;
                border-right: 1px solid {palette.divider};
                border-bottom: 1px solid {palette.divider};
                padding: 7px;
                font-weight: 600;
            }}
            QTextBrowser#TenderRegistryDetails {{
                color: {palette.text_primary};
                background-color: {palette.input_background};
                border: 1px solid {palette.border_default};
                border-radius: 7px;
                padding: 7px;
            }}
            QPushButton {{
                min-height: 32px;
                color: {palette.text_primary};
                background-color: {palette.elevated_background};
                border: 1px solid {palette.border_default};
                border-radius: 7px;
                padding: 4px 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {palette.hover_background};
            }}
            QPushButton:disabled {{
                color: {palette.text_disabled};
                background-color: {palette.neutral_background};
            }}
            QPushButton#PrimaryActionButton {{
                color: {palette.text_on_brand};
                background-color: {palette.brand_primary};
                border-color: {palette.brand_primary};
            }}
            QPushButton#PrimaryActionButton:hover {{
                background-color: {palette.brand_primary_hover};
            }}
            QSplitter::handle {{
                background-color: transparent;
                width: 8px;
            }}
            """
        )


def _format_price(
    amount: Decimal | None,
    currency: str,
) -> str:
    if amount is None:
        return "Не указана"
    rendered = f"{amount:,.2f}".replace(",", " ").replace(".00", "")
    symbol = "₽" if currency.upper() in {"", "RUB"} else currency.upper()
    return f"{rendered} {symbol}"


def _format_timestamp(value: str) -> str:
    if not value:
        return "Не указано"
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return value
    if parsed.hour == 0 and parsed.minute == 0 and "T" not in value:
        return parsed.strftime("%d.%m.%Y")
    return parsed.strftime("%d.%m.%Y %H:%M")


def _freshness_text(
    state: TenderFreshnessState | None,
) -> str:
    if state is None:
        return "Не рассчитана"
    labels = {
        TenderFreshnessStatus.FRESH: "Актуально",
        TenderFreshnessStatus.DUE_SOON: "Срок менее 48 ч",
        TenderFreshnessStatus.STALE: "Требуется проверка",
        TenderFreshnessStatus.EXPIRED: "Подача завершена",
        TenderFreshnessStatus.UNVERIFIED: "Не подтверждено",
    }
    return labels.get(state.status, state.status.value)


def _freshness_due_text(
    state: TenderFreshnessState | None,
) -> str:
    if state is None:
        return "Не рассчитана"
    if state.deadline_expired:
        return "Не назначена: срок подачи завершён"
    if state.is_stale:
        return "Требуется сейчас"
    return _format_timestamp(state.verification_due_at)


def _deadline_display(
    fallback: str,
    state: TenderFreshnessState | None,
) -> str:
    if state is None or not state.deadline_user_local:
        return _format_timestamp(fallback)
    rendered = _format_timestamp(state.deadline_user_local)
    return f"{rendered} ({state.user_timezone})"


def _freshness_tooltip(
    state: TenderFreshnessState | None,
) -> str:
    if state is None:
        return "Свежесть и часовой пояс ещё не рассчитаны."
    timezone_label = {
        DeadlineTimezoneStatus.EXPLICIT: "указан в дате",
        DeadlineTimezoneStatus.SOURCE_ZONE: "указан источником",
        DeadlineTimezoneStatus.UNKNOWN: "не указан",
        DeadlineTimezoneStatus.INVALID: "не распознан",
        DeadlineTimezoneStatus.MISSING: "срок отсутствует",
    }.get(state.timezone_status, state.timezone_status.value)
    return (
        f"{_freshness_text(state)}\n"
        f"Причина: {state.stale_reason or '—'}\n"
        f"Исходный срок: {state.deadline_original or '—'}\n"
        f"Часовой пояс источника: {state.source_timezone or '—'} "
        f"({timezone_label})\n"
        f"UTC: {_format_timestamp(state.deadline_utc)}\n"
        f"Локальное время: {_format_timestamp(state.deadline_user_local)} "
        f"({state.user_timezone or '—'})\n"
        f"Последняя проверка: {_format_timestamp(state.last_verified_at)}\n"
        f"Следующая проверка: {_freshness_due_text(state)}"
    )


def _freshness_color(state, palette) -> str:
    if state is None:
        return palette.neutral
    if state.status in {
        TenderFreshnessStatus.STALE,
        TenderFreshnessStatus.UNVERIFIED,
    }:
        return palette.danger
    if state.status == TenderFreshnessStatus.DUE_SOON:
        return palette.warning
    if state.status == TenderFreshnessStatus.EXPIRED:
        return palette.neutral
    return palette.success


def _verification_text(
    state: TenderVerificationState | None,
) -> str:
    if state is None:
        return "Не проверено"
    label = STATUS_LABELS.get(state.status, state.status.value)
    if state.unresolved_conflict_count:
        return f"{label} · {state.unresolved_conflict_count}"
    return label


def _verification_tooltip(
    state: TenderVerificationState | None,
) -> str:
    if state is None:
        return "Проверка происхождения критичных полей ещё не выполнялась."
    return (
        f"{_verification_text(state)}\n"
        f"Подтверждено: {state.verified_field_count}/"
        f"{state.critical_field_count}\n"
        f"Официальных полей: {state.official_field_count}\n"
        f"Конфликтов: {state.conflict_count}; нерешённых: "
        f"{state.unresolved_conflict_count}\n"
        f"Минимальная достоверность: {state.minimum_confidence:.0%}"
    )


def _verification_color(state, palette) -> str:
    if state is None:
        return palette.neutral
    if state.status == TenderVerificationStatus.CONFLICT:
        return palette.danger
    if state.status in {
        TenderVerificationStatus.INCOMPLETE,
        TenderVerificationStatus.AGGREGATOR_ONLY,
        TenderVerificationStatus.PUBLIC_CARD,
    }:
        return palette.warning
    if state.status in {
        TenderVerificationStatus.VERIFIED_DOCUMENTATION,
        TenderVerificationStatus.VERIFIED_EIS,
        TenderVerificationStatus.VERIFIED_PLATFORM,
        TenderVerificationStatus.VERIFIED_OFFICIAL_API,
    }:
        return palette.success
    return palette.info


__all__ = ["TenderRegistryDialog"]
