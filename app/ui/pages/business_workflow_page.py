"""Business workflow page for proposals, estimates and projects."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import QItemSelection, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.repositories.business_metrics import (
    BusinessMetricsRepository,
    BusinessRecordKind,
    BusinessStatus,
    BusinessWorkflowRecord,
)
from app.ui.business_workflow.dialogs import BusinessRecordDialog
from app.ui.business_workflow.model import (
    KIND_LABELS,
    STATUS_LABELS,
    WORKFLOW_COLUMNS,
    WorkflowFilterProxyModel,
    WorkflowRole,
    WorkflowStatusDelegate,
    WorkflowTableModel,
    allowed_transitions,
    kind_label,
    preferred_next_status,
    status_label,
)
from app.ui.dashboard.kpi_center import KpiCenter
from app.ui.dashboard.status_banner import (
    DashboardStatusBanner,
    StatusTone,
)
from app.ui.theme.colors import ThemeName, get_palette
from app.ui.theme.typography import Typography
from app.ui.viewmodels.dashboard_viewmodel import DashboardKpi
from app.ui.widgets.button import (
    DangerButton,
    OutlineButton,
    PrimaryButton,
    SecondaryButton,
)


class BusinessWorkflowPage(QWidget):
    """Manage commercial proposals, estimates and projects."""

    workflow_changed = Signal()
    tender_open_requested = Signal(str)

    def __init__(
        self,
        *,
        repository: BusinessMetricsRepository | None = None,
        initial_kind: BusinessRecordKind | str | None = None,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.repository = repository or BusinessMetricsRepository()
        self._theme = ThemeName(theme)
        self._initial_kind = (
            BusinessRecordKind(initial_kind)
            if initial_kind is not None
            else None
        )
        self._selected_record: BusinessWorkflowRecord | None = None

        self.setObjectName("BusinessWorkflowPage")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 24)
        root.setSpacing(15)

        self._build_header(root)
        self._build_status(root)
        self._build_summary(root)
        self._build_filters(root)
        self._build_content(root)

        self.apply_theme(self._theme)
        self.refresh()

    def _build_header(self, root: QVBoxLayout) -> None:
        header = QHBoxLayout()
        header.setSpacing(12)

        titles = QVBoxLayout()
        titles.setSpacing(4)

        self.title_label = QLabel(
            "КП, сметы и проекты",
            self,
        )
        self.title_label.setObjectName("WorkflowTitle")

        self.subtitle_label = QLabel(
            "Управление коммерческими документами "
            "и этапами исполнения.",
            self,
        )
        self.subtitle_label.setObjectName("WorkflowSubtitle")

        titles.addWidget(self.title_label)
        titles.addWidget(self.subtitle_label)

        self.updated_label = QLabel("", self)
        self.updated_label.setObjectName("WorkflowUpdated")

        self.refresh_button = OutlineButton(
            "Обновить",
            icon_text="↻",
            theme=self._theme,
            parent=self,
        )
        self.refresh_button.clicked.connect(self.refresh)

        self.create_button = PrimaryButton(
            "Новая запись",
            icon_text="+",
            theme=self._theme,
            parent=self,
        )
        self.create_button.clicked.connect(self._create_record)

        header.addLayout(titles, 1)
        header.addWidget(self.updated_label)
        header.addWidget(self.refresh_button)
        header.addWidget(self.create_button)
        root.addLayout(header)

    def _build_status(self, root: QVBoxLayout) -> None:
        self.status_banner = DashboardStatusBanner(
            theme=self._theme,
            parent=self,
        )
        root.addWidget(self.status_banner)

    def _build_summary(self, root: QVBoxLayout) -> None:
        self.summary = KpiCenter(
            columns=4,
            theme=self._theme,
            parent=self,
        )
        self.summary.kpi_clicked.connect(
            self._filter_from_summary
        )
        root.addWidget(self.summary)

    def _build_filters(self, root: QVBoxLayout) -> None:
        bar = QFrame(self)
        bar.setObjectName("WorkflowFilterBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        self.search_edit = QLineEdit(bar)
        self.search_edit.setPlaceholderText(
            "Поиск по названию, тендеру или статусу"
        )
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(
            self._on_search_changed
        )

        self.kind_filter = QComboBox(bar)
        self.kind_filter.addItem("Все типы", "")
        for kind, label in KIND_LABELS.items():
            self.kind_filter.addItem(label, kind.value)
        self.kind_filter.currentIndexChanged.connect(
            self._on_kind_filter_changed
        )

        self.status_filter = QComboBox(bar)
        self.status_filter.addItem("Все статусы", "")
        for status, label in STATUS_LABELS.items():
            self.status_filter.addItem(label, status.value)
        self.status_filter.currentIndexChanged.connect(
            self._on_status_filter_changed
        )

        self.reset_button = SecondaryButton(
            "Сбросить",
            theme=self._theme,
            parent=bar,
        )
        self.reset_button.clicked.connect(self._reset_filters)

        layout.addWidget(self.search_edit, 1)
        layout.addWidget(self.kind_filter)
        layout.addWidget(self.status_filter)
        layout.addWidget(self.reset_button)
        root.addWidget(bar)

    def _build_content(self, root: QVBoxLayout) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setObjectName("WorkflowSplitter")
        splitter.setChildrenCollapsible(False)

        table_frame = QFrame(splitter)
        table_frame.setObjectName("WorkflowTableFrame")
        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(0, 0, 0, 0)

        self.model = WorkflowTableModel(parent=self)
        self.proxy = WorkflowFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)

        self.table = QTableView(table_frame)
        self.table.setObjectName("WorkflowTable")
        self.table.setModel(self.proxy)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setSortingEnabled(True)
        self.table.setWordWrap(False)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(46)
        self.table.setItemDelegate(
            WorkflowStatusDelegate(
                theme=self._theme,
                parent=self.table,
            )
        )

        header = self.table.horizontalHeader()
        header.setHighlightSections(False)
        header.setStretchLastSection(False)
        for index, column in enumerate(WORKFLOW_COLUMNS):
            if column.key == "title":
                header.setSectionResizeMode(
                    index,
                    QHeaderView.ResizeMode.Stretch,
                )
            else:
                header.setSectionResizeMode(
                    index,
                    QHeaderView.ResizeMode.Fixed,
                )
                self.table.setColumnWidth(index, column.width)

        self.table.selectionModel().selectionChanged.connect(
            self._selection_changed
        )
        self.table.doubleClicked.connect(
            lambda _index: self._open_selected_tender()
        )
        table_layout.addWidget(self.table)

        self.detail_panel = self._build_detail_panel(splitter)

        splitter.addWidget(table_frame)
        splitter.addWidget(self.detail_panel)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([900, 390])

        root.addWidget(splitter, 1)

    def _build_detail_panel(self, parent: QWidget) -> QFrame:
        panel = QFrame(parent)
        panel.setObjectName("WorkflowDetailPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(13)

        title = QLabel("Карточка записи", panel)
        title.setObjectName("WorkflowDetailTitle")
        layout.addWidget(title)

        self.empty_label = QLabel(
            "Выберите запись в таблице.",
            panel,
        )
        self.empty_label.setObjectName("WorkflowDetailEmpty")
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)

        self.detail_form = QFormLayout()
        self.detail_form.setHorizontalSpacing(12)
        self.detail_form.setVerticalSpacing(10)

        self.detail_kind = QLabel("—", panel)
        self.detail_title = QLabel("—", panel)
        self.detail_title.setWordWrap(True)
        self.detail_tender = QLabel("—", panel)
        self.detail_amount = QLabel("—", panel)
        self.detail_profit = QLabel("—", panel)
        self.detail_due = QLabel("—", panel)
        self.detail_file = QLabel("—", panel)
        self.detail_file.setWordWrap(True)

        self.detail_form.addRow("Тип:", self.detail_kind)
        self.detail_form.addRow("Название:", self.detail_title)
        self.detail_form.addRow("Тендер:", self.detail_tender)
        self.detail_form.addRow("Сумма:", self.detail_amount)
        self.detail_form.addRow("Прибыль:", self.detail_profit)
        self.detail_form.addRow("Срок:", self.detail_due)
        self.detail_form.addRow("Файл:", self.detail_file)
        layout.addLayout(self.detail_form)

        status_title = QLabel("Переход статуса", panel)
        status_title.setObjectName("WorkflowStatusTitle")
        layout.addWidget(status_title)

        self.transition_combo = QComboBox(panel)
        self.transition_combo.setEnabled(False)
        layout.addWidget(self.transition_combo)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self.apply_status_button = PrimaryButton(
            "Применить",
            theme=self._theme,
            parent=panel,
        )
        self.apply_status_button.clicked.connect(
            self._apply_selected_status
        )
        self.apply_status_button.setEnabled(False)

        self.advance_button = OutlineButton(
            "Следующий этап",
            theme=self._theme,
            parent=panel,
        )
        self.advance_button.clicked.connect(
            self._advance_selected
        )
        self.advance_button.setEnabled(False)

        action_row.addWidget(self.apply_status_button)
        action_row.addWidget(self.advance_button)
        layout.addLayout(action_row)

        self.open_file_button = SecondaryButton(
            "Открыть документ",
            theme=self._theme,
            parent=panel,
        )
        self.open_file_button.clicked.connect(
            self._open_selected_file
        )
        self.open_file_button.setEnabled(False)

        self.open_tender_button = SecondaryButton(
            "Открыть тендер",
            theme=self._theme,
            parent=panel,
        )
        self.open_tender_button.clicked.connect(
            self._open_selected_tender
        )
        self.open_tender_button.setEnabled(False)

        self.block_button = DangerButton(
            "Заблокировать",
            theme=self._theme,
            parent=panel,
        )
        self.block_button.clicked.connect(self._block_selected)
        self.block_button.setEnabled(False)

        layout.addWidget(self.open_file_button)
        layout.addWidget(self.open_tender_button)
        layout.addWidget(self.block_button)
        layout.addStretch(1)
        return panel

    @property
    def selected_record(self) -> BusinessWorkflowRecord | None:
        return self._selected_record

    def refresh(self) -> None:
        try:
            records = self.repository.list_records()
            summary = self.repository.summary(activity_limit=0)
        except Exception as exc:
            self.status_banner.show_status(
                title="Не удалось загрузить бизнес-процессы",
                message=str(exc),
                tone=StatusTone.ERROR,
            )
            return

        self.model.set_records(records)
        self._update_summary(summary)
        self.updated_label.setText(
            datetime.now().strftime("Обновлено %H:%M")
        )
        self._restore_initial_filter()
        self._select_first_visible()
        self.status_banner.clear()

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)

        self.summary.set_theme(self._theme)
        self.status_banner.apply_theme(self._theme)

        for button in (
            self.refresh_button,
            self.create_button,
            self.reset_button,
            self.apply_status_button,
            self.advance_button,
            self.open_file_button,
            self.open_tender_button,
            self.block_button,
        ):
            button.set_theme(self._theme)

        delegate = self.table.itemDelegate()
        if isinstance(delegate, WorkflowStatusDelegate):
            delegate.set_theme(self._theme)

        self.setStyleSheet(
            f"""
            QWidget#BusinessWorkflowPage {{
                background-color: {palette.app_background};
                color: {palette.text_primary};
            }}
            QLabel#WorkflowTitle {{
                color: {palette.text_primary};
                {Typography.H1.css()}
            }}
            QLabel#WorkflowSubtitle,
            QLabel#WorkflowUpdated,
            QLabel#WorkflowDetailEmpty {{
                color: {palette.text_muted};
                {Typography.BODY_S.css()}
            }}
            QFrame#WorkflowFilterBar,
            QFrame#WorkflowTableFrame,
            QFrame#WorkflowDetailPanel {{
                background-color: {palette.card_background};
                border: 1px solid {palette.border_subtle};
                border-radius: 11px;
            }}
            QLabel#WorkflowDetailTitle {{
                color: {palette.text_primary};
                {Typography.H3.css()}
            }}
            QLabel#WorkflowStatusTitle {{
                color: {palette.text_secondary};
                {Typography.BUTTON.css()}
            }}
            QFrame#WorkflowDetailPanel QLabel {{
                color: {palette.text_secondary};
                {Typography.BODY_S.css()}
            }}
            QLineEdit, QComboBox {{
                min-height: 34px;
                color: {palette.text_primary};
                background-color: {palette.input_background};
                border: 1px solid {palette.border_default};
                border-radius: 7px;
                padding: 4px 8px;
                {Typography.BODY_S.css()}
            }}
            QLineEdit:focus, QComboBox:focus {{
                border: 2px solid {palette.focus_ring};
            }}
            QTableView#WorkflowTable {{
                color: {palette.text_primary};
                background-color: {palette.card_background};
                alternate-background-color: {palette.panel_background};
                gridline-color: {palette.border_subtle};
                border: none;
                selection-background-color: {palette.selected_background};
                selection-color: {palette.text_primary};
                {Typography.BODY_S.css()}
            }}
            QHeaderView::section {{
                color: {palette.text_secondary};
                background-color: {palette.elevated_background};
                border: none;
                border-bottom: 1px solid {palette.border_default};
                padding: 9px 7px;
                {Typography.CAPTION.css()}
            }}
            QSplitter::handle {{
                background: transparent;
                width: 10px;
            }}
            """
        )
        self.table.viewport().update()

    def _update_summary(self, snapshot) -> None:
        self.summary.set_kpis(
            (
                DashboardKpi(
                    key="proposals",
                    title="КП в работе",
                    value=str(snapshot.proposals_in_work),
                    trend="Черновики, проверка и отправленные",
                    tone="info",
                    icon_text="КП",
                ),
                DashboardKpi(
                    key="estimates",
                    title="Сметы в работе",
                    value=str(snapshot.estimates_in_work),
                    trend="Черновики и согласование",
                    tone="warning",
                    icon_text="₽",
                ),
                DashboardKpi(
                    key="projects",
                    title="Активные проекты",
                    value=str(snapshot.active_projects),
                    trend="План, монтаж и пусконаладка",
                    tone="success",
                    icon_text="P",
                ),
                DashboardKpi(
                    key="profit",
                    title="Потенциальная прибыль",
                    value=self._money(snapshot.potential_profit),
                    trend=f"Источников расчёта: {snapshot.profit_sources}",
                    tone="success",
                    icon_text="₽",
                ),
            )
        )

    def _selection_changed(
        self,
        selected: QItemSelection,
        _deselected: QItemSelection,
    ) -> None:
        indexes = selected.indexes()
        if not indexes:
            self._set_selected_record(None)
            return

        proxy_index = indexes[0]
        source_index = self.proxy.mapToSource(proxy_index)
        record = self.model.record_at(source_index.row())
        self._set_selected_record(record)

    def _set_selected_record(
        self,
        record: BusinessWorkflowRecord | None,
    ) -> None:
        self._selected_record = record
        visible = record is not None

        self.empty_label.setVisible(not visible)
        self.transition_combo.setEnabled(visible)
        self.apply_status_button.setEnabled(visible)
        self.open_tender_button.setEnabled(
            bool(record and record.tender_id)
        )
        self.open_file_button.setEnabled(
            bool(
                record
                and record.file_path
                and Path(record.file_path).exists()
            )
        )

        if record is None:
            for label in (
                self.detail_kind,
                self.detail_title,
                self.detail_tender,
                self.detail_amount,
                self.detail_profit,
                self.detail_due,
                self.detail_file,
            ):
                label.setText("—")
            self.transition_combo.clear()
            self.advance_button.setEnabled(False)
            self.block_button.setEnabled(False)
            return

        kind = BusinessRecordKind(record.kind)
        status = BusinessStatus(record.status)

        self.detail_kind.setText(kind_label(kind))
        self.detail_title.setText(record.title)
        self.detail_tender.setText(record.tender_id or "—")
        self.detail_amount.setText(self._money(record.total))
        self.detail_profit.setText(self._money(record.profit))
        self.detail_due.setText(record.due_date or "—")
        self.detail_file.setText(record.file_path or "—")

        transitions = allowed_transitions(kind, status)
        self.transition_combo.clear()
        if transitions:
            for target in transitions:
                self.transition_combo.addItem(
                    STATUS_LABELS[target],
                    target.value,
                )
        else:
            self.transition_combo.addItem(
                "Нет доступных переходов",
                "",
            )

        next_status = preferred_next_status(kind, status)
        self.advance_button.setEnabled(next_status is not None)
        self.apply_status_button.setEnabled(bool(transitions))
        self.block_button.setEnabled(
            BusinessStatus.BLOCKED in transitions
        )

    def _create_record(self) -> None:
        initial_kind = (
            BusinessRecordKind(
                str(self.kind_filter.currentData())
            )
            if self.kind_filter.currentData()
            else self._initial_kind
            or BusinessRecordKind.PROPOSAL
        )
        dialog = BusinessRecordDialog(
            initial_kind=initial_kind,
            theme=self._theme,
            parent=self,
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        payload = dialog.payload()
        try:
            self.repository.save_record(**payload)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка сохранения",
                str(exc),
            )
            return

        self.status_banner.show_status(
            title="Запись сохранена",
            message=str(payload["title"]),
            tone=StatusTone.SUCCESS,
            auto_hide_ms=2500,
        )
        self.refresh()
        self.workflow_changed.emit()

    def _apply_selected_status(self) -> None:
        record = self._selected_record
        target = self.transition_combo.currentData()
        if record is None or not target:
            return
        self._change_status(record, BusinessStatus(str(target)))

    def _advance_selected(self) -> None:
        record = self._selected_record
        if record is None:
            return

        target = preferred_next_status(
            record.kind,
            record.status,
        )
        if target is not None:
            self._change_status(record, target)

    def _block_selected(self) -> None:
        record = self._selected_record
        if record is None:
            return
        self._change_status(record, BusinessStatus.BLOCKED)

    def _change_status(
        self,
        record: BusinessWorkflowRecord,
        target: BusinessStatus,
    ) -> None:
        if target not in allowed_transitions(
            record.kind,
            record.status,
        ):
            QMessageBox.warning(
                self,
                "Переход недоступен",
                (
                    f"Нельзя изменить статус "
                    f"«{status_label(record.status)}» на "
                    f"«{status_label(target)}»."
                ),
            )
            return

        try:
            self.repository.update_status(record.id, target)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка изменения статуса",
                str(exc),
            )
            return

        self.status_banner.show_status(
            title="Статус обновлён",
            message=(
                f"{record.title}: {status_label(target)}."
            ),
            tone=StatusTone.SUCCESS,
            auto_hide_ms=2500,
        )
        self.refresh()
        self.workflow_changed.emit()

    def _open_selected_file(self) -> None:
        record = self._selected_record
        if record is None or not record.file_path:
            return

        path = Path(record.file_path)
        if not path.exists():
            QMessageBox.warning(
                self,
                "Файл не найден",
                str(path),
            )
            return

        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(path.resolve()))
        )

    def _open_selected_tender(self) -> None:
        record = self._selected_record
        if record is not None and record.tender_id:
            self.tender_open_requested.emit(record.tender_id)

    def _filter_from_summary(self, key: str) -> None:
        mapping = {
            "proposals": BusinessRecordKind.PROPOSAL,
            "estimates": BusinessRecordKind.ESTIMATE,
            "projects": BusinessRecordKind.PROJECT,
        }
        kind = mapping.get(key)
        if kind is None:
            return
        index = self.kind_filter.findData(kind.value)
        if index >= 0:
            self.kind_filter.setCurrentIndex(index)

    def _on_search_changed(self, text: str) -> None:
        self.proxy.set_search(text)
        self._select_first_visible()

    def _on_kind_filter_changed(self) -> None:
        value = self.kind_filter.currentData()
        self.proxy.set_kind(value or None)
        self._select_first_visible()

    def _on_status_filter_changed(self) -> None:
        value = self.status_filter.currentData()
        self.proxy.set_status(value or None)
        self._select_first_visible()

    def _reset_filters(self) -> None:
        self.search_edit.clear()
        self.kind_filter.setCurrentIndex(0)
        self.status_filter.setCurrentIndex(0)

    def _restore_initial_filter(self) -> None:
        if self._initial_kind is None:
            return
        if self.kind_filter.currentData():
            return

        index = self.kind_filter.findData(
            self._initial_kind.value
        )
        if index >= 0:
            self.kind_filter.setCurrentIndex(index)

    def _select_first_visible(self) -> None:
        if self.proxy.rowCount() <= 0:
            self.table.clearSelection()
            self._set_selected_record(None)
            return

        index = self.proxy.index(0, 0)
        self.table.setCurrentIndex(index)
        self.table.selectRow(0)

    @staticmethod
    def _money(value: Decimal | float) -> str:
        amount = Decimal(str(value or 0))
        return f"{amount:,.0f} ₽".replace(",", " ")


__all__ = ["BusinessWorkflowPage"]
