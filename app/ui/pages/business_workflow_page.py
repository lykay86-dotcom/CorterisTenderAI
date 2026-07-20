"""Business workflow page for proposals, estimates and projects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
import logging
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QItemSelection, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QCloseEvent, QDesktopServices, QResizeEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QMenu,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.operations.contracts import OperationEpisodeId, OperationKind, OperationReasonCode
from app.operations.diagnostics import DiagnosticRegistry
from app.operations.safe_feedback import SafeFeedbackProjector
from app.financial import MoneyAmount, format_money
from app.core.crash_report_catalog import (
    CrashReportCatalogService,
)
from app.core.crash_reporting import CrashReportService
from app.core.diagnostic_support_bundle import (
    DiagnosticSupportBundleService,
)
from app.core.system_health_monitor import SystemHealthMonitor
from app.core.system_health import (
    SystemHealthJournal,
    SystemHealthService,
    SystemHealthSeverity,
)
from app.core.workflow_auto_backup import WorkflowAutoBackupService
from app.core.workflow_backup import WorkflowBackupService
from app.core.workflow_backup_catalog import (
    WorkflowBackupCatalogService,
)
from app.core.workflow_database_health import (
    WorkflowDatabaseHealthReport,
    WorkflowDatabaseHealthService,
    WorkflowDatabaseHealthStatus,
)
from app.reporting.workflow_excel import WorkflowExcelExporter
from app.reporting.workflow_excel_import import WorkflowExcelImporter
from app.reporting.workflow_excel_template import (
    WorkflowExcelTemplateService,
)
from app.repositories.business_metrics import (
    BusinessAuditAction,
    BusinessAuditEvent,
    BusinessMetricsRepository,
    BusinessMetricsSnapshot,
    BusinessRecordKind,
    BusinessStatus,
    BusinessWorkflowRecord,
)
from app.ui.business_workflow.backup_center_dialog import (
    WorkflowBackupCenterDialog,
)
from app.ui.business_workflow.backup_settings_dialog import (
    WorkflowBackupSettingsDialog,
)
from app.ui.crash_report_center_dialog import (
    CrashReportCenterDialog,
)
from app.ui.business_workflow.database_recovery_dialog import (
    WorkflowDatabaseRecoveryAction,
    WorkflowDatabaseRecoveryDialog,
)
from app.ui.business_workflow.dialogs import BusinessRecordDialog
from app.ui.business_workflow.system_health_badge import (
    SystemHealthBadge,
)
from app.ui.business_workflow.system_health_dialog import (
    SystemHealthCenterDialog,
)
from app.ui.business_workflow.import_dialog import (
    WorkflowImportPreviewDialog,
)
from app.ui.business_workflow.model import (
    KIND_LABELS,
    STATUS_LABELS,
    WORKFLOW_COLUMNS,
    WorkflowArchiveMode,
    WorkflowFilterProxyModel,
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
from app.ui.navigation.contracts import DashboardFilterId, RouteId
from app.ui.theme.colors import ThemeName, get_palette
from app.ui.theme.typography import Typography
from app.ui.viewmodels.dashboard_viewmodel import DashboardKpi
from app.ui.widgets.button import (
    DangerButton,
    OutlineButton,
    PrimaryButton,
    SecondaryButton,
)


@dataclass(frozen=True, slots=True)
class WorkflowNavigationState:
    """Presentation-only workflow filters and stable selection identity."""

    search_text: str = ""
    kind: str = ""
    status: str = ""
    archive_mode: str = WorkflowArchiveMode.ACTIVE.value
    record_id: str | None = None
    dashboard_filter: str = ""

    def __post_init__(self) -> None:
        if self.kind not in {"", *(kind.value for kind in BusinessRecordKind)}:
            raise ValueError("Unknown workflow kind")
        if self.status not in {"", *(status.value for status in BusinessStatus)}:
            raise ValueError("Unknown workflow status")
        if self.archive_mode not in {mode.value for mode in WorkflowArchiveMode}:
            raise ValueError("Unknown workflow archive mode")
        if self.record_id is not None and not str(self.record_id).strip():
            raise ValueError("Workflow record identity must not be blank")
        if self.dashboard_filter:
            dashboard_filter = DashboardFilterId(self.dashboard_filter)
            if dashboard_filter.route_id is not RouteId.WORKFLOW:
                raise ValueError("Dashboard filter does not belong to workflow")


class BusinessWorkflowLifecycleState(StrEnum):
    """Terminal lifecycle for page-owned scheduling and health delivery."""

    OPEN = "open"
    CLOSING = "closing"
    CLOSED = "closed"


LOGGER = logging.getLogger("corteris.ui.business_workflow")


class BusinessWorkflowPage(QWidget):
    """Manage commercial proposals, estimates and projects."""

    workflow_changed = Signal()
    tender_open_requested = Signal(str)

    def __init__(
        self,
        *,
        repository: BusinessMetricsRepository | None = None,
        excel_exporter: WorkflowExcelExporter | None = None,
        excel_importer: WorkflowExcelImporter | None = None,
        excel_template_service: (WorkflowExcelTemplateService | None) = None,
        backup_service: WorkflowBackupService | None = None,
        backup_catalog_service: (WorkflowBackupCatalogService | None) = None,
        database_health_service: (WorkflowDatabaseHealthService | None) = None,
        crash_report_service: CrashReportService | None = None,
        crash_report_catalog_service: (CrashReportCatalogService | None) = None,
        system_health_service: SystemHealthService | None = None,
        system_health_journal: SystemHealthJournal | None = None,
        system_health_monitor: SystemHealthMonitor | None = None,
        auto_backup_service: (WorkflowAutoBackupService | None) = None,
        initial_kind: BusinessRecordKind | str | None = None,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.repository = repository or BusinessMetricsRepository()
        self.excel_exporter = excel_exporter or WorkflowExcelExporter()
        self.excel_importer = excel_importer or WorkflowExcelImporter()
        self.excel_template_service = excel_template_service or WorkflowExcelTemplateService()
        self.backup_service = backup_service or WorkflowBackupService()
        self.backup_catalog_service = backup_catalog_service or WorkflowBackupCatalogService(
            self.backup_service
        )
        self.database_health_service = database_health_service or WorkflowDatabaseHealthService(
            backup_service=self.backup_service,
            catalog_service=self.backup_catalog_service,
        )
        self.crash_report_service = crash_report_service or CrashReportService(
            self.repository.path.parent / "crash_reports"
        )
        self.crash_report_catalog_service = (
            crash_report_catalog_service or CrashReportCatalogService(self.crash_report_service)
        )
        self.system_health_service = system_health_service or SystemHealthService()
        self.system_health_journal = system_health_journal or SystemHealthJournal.for_repository(
            self.repository
        )
        self.auto_backup_service = auto_backup_service or WorkflowAutoBackupService.for_repository(
            self.repository,
            backup_service=self.backup_service,
        )
        self.system_health_monitor = system_health_monitor or SystemHealthMonitor(
            self._collect_system_health_snapshot,
            parent=self,
        )
        self.operation_diagnostic_registry = DiagnosticRegistry(max_records=256)
        self.operation_feedback_projector = SafeFeedbackProjector(
            registry=self.operation_diagnostic_registry
        )
        self._theme = ThemeName(theme)
        self._initial_kind = BusinessRecordKind(initial_kind) if initial_kind is not None else None
        self._dashboard_filter: DashboardFilterId | None = None
        self._selected_record: BusinessWorkflowRecord | None = None
        self._content_orientation: Qt.Orientation | None = None
        self._database_health_prompt_shown = False
        self._last_health_severity: SystemHealthSeverity | None = None
        self._lifecycle_state = BusinessWorkflowLifecycleState.OPEN

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

        self._auto_backup_timer = QTimer(self)
        self._auto_backup_timer.setInterval(15 * 60 * 1000)
        self._auto_backup_timer.timeout.connect(self._check_automatic_backup)
        self._auto_backup_timer.start()
        self.workflow_changed.connect(self._check_automatic_backup)

        self.system_health_monitor.snapshot_ready.connect(self._system_health_snapshot_ready)
        self.system_health_monitor.check_failed.connect(self._system_health_check_failed)
        self.system_health_monitor.busy_changed.connect(self.system_health_badge.set_busy)
        self.workflow_changed.connect(self._request_system_health_refresh)

        self._system_health_timer = QTimer(self)
        self._system_health_timer.setInterval(2 * 60 * 1000)
        self._system_health_timer.timeout.connect(self._request_system_health_refresh)
        self._system_health_timer.start()

        QTimer.singleShot(
            0,
            lambda: self._run_when_open(self._initialize_database_safety),
        )
        QTimer.singleShot(
            250,
            lambda: self._run_when_open(self._request_system_health_refresh),
        )

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
            "Управление коммерческими документами и этапами исполнения.",
            self,
        )
        self.subtitle_label.setObjectName("WorkflowSubtitle")

        titles.addWidget(self.title_label)
        titles.addWidget(self.subtitle_label)

        self.updated_label = QLabel("", self)
        self.updated_label.setObjectName("WorkflowUpdated")

        self.system_health_badge = SystemHealthBadge(
            theme=self._theme,
            parent=self,
        )
        self.system_health_badge.clicked.connect(self._open_system_health_center)

        self.refresh_button = OutlineButton(
            "Обновить",
            icon_text="↻",
            theme=self._theme,
            parent=self,
        )
        self.refresh_button.clicked.connect(self.refresh)

        self.export_button = OutlineButton(
            "Экспорт Excel",
            icon_text="⇩",
            theme=self._theme,
            parent=self,
        )
        self.export_button.clicked.connect(self._export_excel)

        self.import_button = OutlineButton(
            "Импорт Excel",
            icon_text="⇧",
            theme=self._theme,
            parent=self,
        )
        self.import_button.clicked.connect(self._import_excel)

        self.template_button = OutlineButton(
            "Шаблон Excel",
            icon_text="▤",
            theme=self._theme,
            parent=self,
        )
        self.template_button.clicked.connect(self._save_excel_template)

        self.data_button = OutlineButton(
            "Данные",
            icon_text="⛁",
            theme=self._theme,
            parent=self,
        )
        self.data_menu = QMenu(self.data_button)
        self.system_health_action = self.data_menu.addAction("Состояние системы…")
        self.system_health_action.triggered.connect(self._open_system_health_center)
        self.data_menu.addSeparator()
        self.backup_center_action = self.data_menu.addAction("Центр резервных копий…")
        self.backup_center_action.triggered.connect(self._open_backup_center)
        self.database_diagnostics_action = self.data_menu.addAction("Диагностика базы…")
        self.database_diagnostics_action.triggered.connect(self._run_database_diagnostics)
        self.data_menu.addSeparator()
        self.create_backup_action = self.data_menu.addAction("Создать резервную копию…")
        self.create_backup_action.triggered.connect(self._create_workflow_backup)
        self.restore_backup_action = self.data_menu.addAction("Восстановить из копии…")
        self.restore_backup_action.triggered.connect(self._restore_workflow_backup)
        self.data_menu.addSeparator()
        self.auto_backup_settings_action = self.data_menu.addAction("Настроить автокопирование…")
        self.auto_backup_settings_action.triggered.connect(self._configure_automatic_backup)
        self.run_auto_backup_action = self.data_menu.addAction("Создать автокопию сейчас")
        self.run_auto_backup_action.triggered.connect(self._run_automatic_backup_now)
        self.data_button.setMenu(self.data_menu)

        self.create_button = PrimaryButton(
            "Новая запись",
            icon_text="+",
            theme=self._theme,
            parent=self,
        )
        self.create_button.clicked.connect(self._create_record)

        header.addLayout(titles, 1)
        header.addWidget(self.updated_label)
        header.addWidget(self.system_health_badge)
        header.addWidget(self.refresh_button)
        header.addWidget(self.data_button)
        header.addWidget(self.template_button)
        header.addWidget(self.import_button)
        header.addWidget(self.export_button)
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
        self.summary.kpi_clicked.connect(self._filter_from_summary)
        root.addWidget(self.summary)

    def _build_filters(self, root: QVBoxLayout) -> None:
        bar = QFrame(self)
        bar.setObjectName("WorkflowFilterBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        self.search_edit = QLineEdit(bar)
        self.search_edit.setObjectName("WorkflowSearch")
        self.search_edit.setAccessibleName("Поиск записей workflow")
        self.search_edit.setAccessibleDescription(
            "Поиск по названию, тендеру и отображаемому статусу записи"
        )
        self.search_edit.setPlaceholderText("Поиск по названию, тендеру или статусу")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search_changed)

        self.kind_filter = QComboBox(bar)
        self.kind_filter.setObjectName("WorkflowKindFilter")
        self.kind_filter.setAccessibleName("Тип записи workflow")
        self.kind_filter.addItem("Все типы", "")
        for kind, label in KIND_LABELS.items():
            self.kind_filter.addItem(label, kind.value)
        self.kind_filter.currentIndexChanged.connect(self._on_kind_filter_changed)

        self.status_filter = QComboBox(bar)
        self.status_filter.setObjectName("WorkflowStatusFilter")
        self.status_filter.setAccessibleName("Статус записи workflow")
        self.status_filter.addItem("Все статусы", "")
        for status, label in STATUS_LABELS.items():
            self.status_filter.addItem(label, status.value)
        self.status_filter.currentIndexChanged.connect(self._on_status_filter_changed)

        self.archive_filter = QComboBox(bar)
        self.archive_filter.setObjectName("WorkflowArchiveFilter")
        self.archive_filter.setAccessibleName("Режим архива workflow")
        self.archive_filter.addItem(
            "Активные",
            WorkflowArchiveMode.ACTIVE.value,
        )
        self.archive_filter.addItem(
            "Архив",
            WorkflowArchiveMode.ARCHIVED.value,
        )
        self.archive_filter.addItem(
            "Все записи",
            WorkflowArchiveMode.ALL.value,
        )
        self.archive_filter.currentIndexChanged.connect(self._on_archive_filter_changed)

        self.reset_button = SecondaryButton(
            "Сбросить",
            theme=self._theme,
            parent=bar,
        )
        self.reset_button.clicked.connect(self._reset_filters)

        layout.addWidget(self.search_edit, 1)
        layout.addWidget(self.kind_filter)
        layout.addWidget(self.status_filter)
        layout.addWidget(self.archive_filter)
        layout.addWidget(self.reset_button)
        root.addWidget(bar)

    def _build_content(self, root: QVBoxLayout) -> None:
        self.splitter = QSplitter(
            Qt.Orientation.Horizontal,
            self,
        )
        self.splitter.setObjectName("WorkflowSplitter")
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(10)

        self.table_frame = QFrame(self.splitter)
        self.table_frame.setObjectName("WorkflowTableFrame")
        table_layout = QVBoxLayout(self.table_frame)
        table_layout.setContentsMargins(0, 0, 0, 0)

        self.model = WorkflowTableModel(parent=self)
        self.proxy = WorkflowFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)

        self.table = QTableView(self.table_frame)
        self.table.setObjectName("WorkflowTable")
        self.table.setAccessibleName("Business workflow records")
        self.table.setAccessibleDescription(
            "Estimates, proposals and projects with exact record identity and Decimal values."
        )
        self.table.setTabKeyNavigation(False)
        self.table.setModel(self.proxy)
        self.model.modelReset.connect(self._restore_exact_selection_after_model_change)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
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

        self.table.selectionModel().selectionChanged.connect(self._selection_changed)
        self.table.doubleClicked.connect(lambda _index: self._open_selected_tender())
        table_layout.addWidget(self.table)

        self.detail_panel = self._build_detail_panel(self.splitter)

        self.splitter.addWidget(self.table_frame)
        self.splitter.addWidget(self.detail_panel)
        root.addWidget(self.splitter, 1)
        self._apply_content_orientation(self.width(), force=True)

    def _build_detail_panel(self, parent: QWidget) -> QFrame:
        panel = QFrame(parent)
        panel.setObjectName("WorkflowDetailPanel")
        panel.setMinimumWidth(460)
        panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.detail_scroll = QScrollArea(panel)
        self.detail_scroll.setObjectName("WorkflowDetailScroll")
        self.detail_scroll.setWidgetResizable(True)
        self.detail_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.detail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget(self.detail_scroll)
        content.setObjectName("WorkflowDetailContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(22, 20, 22, 22)
        layout.setSpacing(18)

        title = QLabel("Карточка записи", content)
        title.setObjectName("WorkflowDetailTitle")
        layout.addWidget(title)

        self.empty_label = QLabel(
            "Выберите запись в таблице.",
            content,
        )
        self.empty_label.setObjectName("WorkflowDetailEmpty")
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)

        self.detail_form = QFormLayout()
        self.detail_form.setContentsMargins(0, 2, 0, 2)
        self.detail_form.setHorizontalSpacing(14)
        self.detail_form.setVerticalSpacing(14)
        self.detail_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.detail_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.detail_form.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom
        )
        self.detail_form.setFormAlignment(Qt.AlignmentFlag.AlignTop)

        def detail_value() -> QLabel:
            label = QLabel("—", content)
            label.setObjectName("WorkflowDetailValue")
            label.setWordWrap(True)
            label.setMinimumHeight(38)
            label.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.MinimumExpanding,
            )
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            return label

        self.detail_kind = detail_value()
        self.detail_title = detail_value()
        self.detail_tender = detail_value()
        self.detail_amount = detail_value()
        self.detail_profit = detail_value()
        self.detail_due = detail_value()
        self.detail_file = detail_value()

        self.detail_form.addRow("Тип", self.detail_kind)
        self.detail_form.addRow("Название", self.detail_title)
        self.detail_form.addRow("Тендер", self.detail_tender)
        self.detail_form.addRow("Сумма", self.detail_amount)
        self.detail_form.addRow("Прибыль", self.detail_profit)
        self.detail_form.addRow("Срок", self.detail_due)
        self.detail_form.addRow("Файл", self.detail_file)
        layout.addLayout(self.detail_form)

        history_title = QLabel("История изменений", content)
        history_title.setObjectName("WorkflowHistoryTitle")
        layout.addWidget(history_title)

        self.history_empty = QLabel(
            "История для выбранной записи пока отсутствует.",
            content,
        )
        self.history_empty.setObjectName("WorkflowHistoryEmpty")
        self.history_empty.setWordWrap(True)
        layout.addWidget(self.history_empty)

        self.history_list = QListWidget(content)
        self.history_list.setObjectName("WorkflowHistoryList")
        self.history_list.setWordWrap(True)
        self.history_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.history_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.history_list.setMinimumHeight(190)
        self.history_list.setMaximumHeight(310)
        self.history_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.history_list)

        status_title = QLabel("Переход статуса", content)
        status_title.setObjectName("WorkflowStatusTitle")
        layout.addWidget(status_title)

        self.transition_combo = QComboBox(content)
        self.transition_combo.setEnabled(False)
        layout.addWidget(self.transition_combo)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)

        self.apply_status_button = PrimaryButton(
            "Применить",
            theme=self._theme,
            parent=content,
        )
        self.apply_status_button.clicked.connect(self._apply_selected_status)
        self.apply_status_button.setEnabled(False)

        self.advance_button = OutlineButton(
            "Следующий этап",
            theme=self._theme,
            parent=content,
        )
        self.advance_button.clicked.connect(self._advance_selected)
        self.advance_button.setEnabled(False)

        action_row.addWidget(self.apply_status_button)
        action_row.addWidget(self.advance_button)
        layout.addLayout(action_row)

        self.edit_button = OutlineButton(
            "Редактировать",
            icon_text="✎",
            theme=self._theme,
            parent=content,
        )
        self.edit_button.clicked.connect(self._edit_selected)
        self.edit_button.setEnabled(False)

        self.open_file_button = SecondaryButton(
            "Открыть документ",
            theme=self._theme,
            parent=content,
        )
        self.open_file_button.clicked.connect(self._open_selected_file)
        self.open_file_button.setEnabled(False)

        self.open_tender_button = SecondaryButton(
            "Открыть тендер",
            theme=self._theme,
            parent=content,
        )
        self.open_tender_button.clicked.connect(self._open_selected_tender)
        self.open_tender_button.setEnabled(False)

        self.block_button = DangerButton(
            "Заблокировать",
            theme=self._theme,
            parent=content,
        )
        self.block_button.clicked.connect(self._block_selected)
        self.block_button.setEnabled(False)

        self.archive_button = DangerButton(
            "В архив",
            theme=self._theme,
            parent=content,
        )
        self.archive_button.clicked.connect(self._archive_selected)
        self.archive_button.setEnabled(False)

        self.restore_button = OutlineButton(
            "Восстановить",
            icon_text="↺",
            theme=self._theme,
            parent=content,
        )
        self.restore_button.clicked.connect(self._restore_selected)
        self.restore_button.setEnabled(False)
        self.restore_button.hide()

        layout.addWidget(self.edit_button)
        layout.addWidget(self.open_file_button)
        layout.addWidget(self.open_tender_button)
        layout.addWidget(self.block_button)
        layout.addWidget(self.archive_button)
        layout.addWidget(self.restore_button)
        layout.addStretch(1)

        self.detail_scroll.setWidget(content)
        outer.addWidget(self.detail_scroll)
        return panel

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._apply_content_orientation(event.size().width())

    def _apply_content_orientation(
        self,
        width: int,
        *,
        force: bool = False,
    ) -> None:
        """Keep the record card readable at every practical window width."""
        orientation = Qt.Orientation.Horizontal if width >= 1320 else Qt.Orientation.Vertical
        if not force and orientation == self._content_orientation:
            return

        self._content_orientation = orientation
        self.splitter.setOrientation(orientation)

        if orientation == Qt.Orientation.Horizontal:
            self.detail_panel.setMinimumWidth(460)
            self.detail_panel.setMinimumHeight(0)
            self.table_frame.setMinimumHeight(0)
            self.splitter.setStretchFactor(0, 3)
            self.splitter.setStretchFactor(1, 2)
            self.splitter.setSizes([860, 500])
        else:
            self.detail_panel.setMinimumWidth(0)
            self.detail_panel.setMinimumHeight(330)
            self.table_frame.setMinimumHeight(280)
            self.splitter.setStretchFactor(0, 3)
            self.splitter.setStretchFactor(1, 2)
            self.splitter.setSizes([430, 390])

    @property
    def selected_record(self) -> BusinessWorkflowRecord | None:
        return self._selected_record

    @property
    def lifecycle_state(self) -> BusinessWorkflowLifecycleState:
        return self._lifecycle_state

    def _run_when_open(self, callback) -> None:
        if self._lifecycle_state is BusinessWorkflowLifecycleState.OPEN:
            callback()

    def shutdown(self, timeout_ms: int = 1000) -> bool:
        """Stop page scheduling and close its monitor within a fixed budget."""
        if timeout_ms < 0:
            raise ValueError("timeout_ms must be non-negative")
        if self._lifecycle_state is BusinessWorkflowLifecycleState.CLOSED:
            return True

        self._lifecycle_state = BusinessWorkflowLifecycleState.CLOSING
        self._auto_backup_timer.stop()
        self._system_health_timer.stop()
        for callback in (
            self._check_automatic_backup,
            self._request_system_health_refresh,
        ):
            try:
                self.workflow_changed.disconnect(callback)
            except (RuntimeError, TypeError):
                pass

        if not self.system_health_monitor.shutdown(timeout_ms=timeout_ms):
            return False

        self._lifecycle_state = BusinessWorkflowLifecycleState.CLOSED
        return True

    def closeEvent(self, event: QCloseEvent) -> None:
        """Fail safe when the page is closed outside the production shell."""
        if not self.shutdown():
            event.ignore()
            return
        super().closeEvent(event)

    def capture_navigation_state(self) -> WorkflowNavigationState:
        """Capture current filters without retaining a repository record."""
        return WorkflowNavigationState(
            search_text=self.search_edit.text(),
            kind=str(self.kind_filter.currentData() or ""),
            status=str(self.status_filter.currentData() or ""),
            archive_mode=str(self.archive_filter.currentData() or WorkflowArchiveMode.ACTIVE.value),
            record_id=(self._selected_record.id if self._selected_record is not None else None),
            dashboard_filter=(
                self._dashboard_filter.value if self._dashboard_filter is not None else ""
            ),
        )

    def apply_navigation_state(self, state: WorkflowNavigationState) -> None:
        """Restore filters and select only an exact still-visible stable ID."""
        if not isinstance(state, WorkflowNavigationState):
            raise TypeError("Workflow navigation requires WorkflowNavigationState")

        self.search_edit.setText(state.search_text)
        self._set_filter_value(self.kind_filter, state.kind)
        self._set_filter_value(self.status_filter, state.status)
        self._set_filter_value(self.archive_filter, state.archive_mode)
        self.apply_dashboard_filter(state.dashboard_filter or None)

        if state.record_id is not None and self._select_record_id(state.record_id):
            return
        self.table.clearSelection()
        self.table.setCurrentIndex(self.proxy.index(-1, -1))
        self._set_selected_record(None)

    @staticmethod
    def _set_filter_value(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index < 0:
            raise ValueError("Workflow navigation filter is unavailable")
        combo.setCurrentIndex(index)

    def _safe_workflow_error(
        self,
        error: Exception,
        *,
        reason: OperationReasonCode = OperationReasonCode.INTERNAL_ERROR,
    ) -> str:
        LOGGER.error(
            "Business workflow operation failed.",
            exc_info=(type(error), error, error.__traceback__),
        )
        feedback = self.operation_feedback_projector.project_reason(
            reason,
            episode_id=OperationEpisodeId(f"episode-{uuid4().hex}"),
            kind=OperationKind.WORKFLOW_RECOVERY,
            occurred_at=datetime.now().astimezone(),
            unsafe_detail=error,
            register_diagnostic=True,
        )
        return feedback.to_plain_text()

    def refresh(
        self,
        preferred_record_id: str | None = None,
    ) -> None:
        previous_record_id = self._selected_record.id if self._selected_record is not None else None
        try:
            records = self.repository.list_records(include_archived=True)
            summary = self.repository.summary(activity_limit=0)
        except Exception as exc:
            self.status_banner.show_status(
                title="Не удалось загрузить бизнес-процессы",
                message=self._safe_workflow_error(exc),
                tone=StatusTone.ERROR,
            )
            return

        self.model.set_records(records)
        self._apply_dashboard_scope(summary)
        self._update_summary(summary)
        self.updated_label.setText(datetime.now().strftime("Обновлено %H:%M"))
        self._restore_initial_filter()
        target_record_id = preferred_record_id or previous_record_id
        if target_record_id and self._select_record_id(target_record_id):
            pass
        elif target_record_id:
            self.table.clearSelection()
            self._set_selected_record(None)
        else:
            self._select_first_visible()
        self.status_banner.clear()

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)

        self.summary.set_theme(self._theme)
        self.status_banner.apply_theme(self._theme)
        self.system_health_badge.apply_theme(self._theme)

        for button in (
            self.refresh_button,
            self.data_button,
            self.template_button,
            self.import_button,
            self.export_button,
            self.create_button,
            self.reset_button,
            self.apply_status_button,
            self.advance_button,
            self.edit_button,
            self.open_file_button,
            self.open_tender_button,
            self.block_button,
            self.archive_button,
            self.restore_button,
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
            QLabel#WorkflowStatusTitle,
            QLabel#WorkflowHistoryTitle {{
                color: {palette.text_secondary};
                {Typography.BUTTON.css()}
            }}
            QLabel#WorkflowHistoryEmpty {{
                color: {palette.text_muted};
                {Typography.BODY_S.css()}
            }}
            QFrame#WorkflowDetailPanel QLabel {{
                color: {palette.text_secondary};
                {Typography.BODY_S.css()}
            }}
            QScrollArea#WorkflowDetailScroll,
            QWidget#WorkflowDetailContent {{
                background: transparent;
                border: none;
            }}
            QLabel#WorkflowDetailValue {{
                color: {palette.text_primary};
                background-color: {palette.input_background};
                border: 1px solid {palette.border_subtle};
                border-radius: 8px;
                padding: 9px 10px;
                {Typography.BODY_M.css()}
            }}
            QListWidget#WorkflowHistoryList {{
                color: {palette.text_primary};
                background-color: {palette.input_background};
                border: 1px solid {palette.border_subtle};
                border-radius: 8px;
                padding: 5px;
                outline: none;
                {Typography.BODY_S.css()}
            }}
            QListWidget#WorkflowHistoryList::item {{
                border-bottom: 1px solid {palette.border_subtle};
                padding: 9px 7px;
            }}
            QListWidget#WorkflowHistoryList::item:last {{
                border-bottom: none;
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
            QMenu {{
                color: {palette.text_primary};
                background-color: {palette.elevated_background};
                border: 1px solid {palette.border_default};
                border-radius: 8px;
                padding: 6px;
                {Typography.BODY_S.css()}
            }}
            QMenu::item {{
                border-radius: 6px;
                padding: 8px 22px 8px 10px;
            }}
            QMenu::item:selected {{
                background-color: {palette.selected_background};
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
        is_archived = bool(record and record.is_archived)
        self.edit_button.setEnabled(visible and not is_archived)
        self.transition_combo.setEnabled(visible and not is_archived)
        self.apply_status_button.setEnabled(visible and not is_archived)
        self.open_tender_button.setEnabled(bool(record and record.tender_id))
        self.archive_button.setVisible(not is_archived)
        self.archive_button.setEnabled(visible and not is_archived)
        self.restore_button.setVisible(is_archived)
        self.restore_button.setEnabled(is_archived)
        self.open_file_button.setEnabled(
            bool(record and record.file_path and Path(record.file_path).exists())
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
            self.history_list.clear()
            self.history_empty.show()
            self.advance_button.setEnabled(False)
            self.block_button.setEnabled(False)
            self.archive_button.setEnabled(False)
            self.restore_button.setEnabled(False)
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
        self.detail_title.setToolTip(record.title)
        self.detail_tender.setToolTip(record.tender_id or "")
        self.detail_file.setToolTip(record.file_path or "")
        self._load_history(record.id)

        transitions = () if record.is_archived else allowed_transitions(kind, status)
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
            (not record.is_archived and BusinessStatus.BLOCKED in transitions)
        )

    def create_diagnostic_support_bundle(
        self,
        target: str | Path,
    ):
        """Create a privacy-aware support bundle for global crash UI."""
        snapshot = self.system_health_monitor.last_snapshot
        if snapshot is None:
            snapshot = self._collect_system_health_snapshot()

        result = DiagnosticSupportBundleService().create_bundle(
            target,
            repository=self.repository,
            snapshot=snapshot,
            journal=self.system_health_journal,
            auto_backup_service=self.auto_backup_service,
            backup_catalog_service=self.backup_catalog_service,
            backup_directories=self._database_backup_directories(),
        )
        self._record_system_event(
            severity=SystemHealthSeverity.SUCCESS,
            component="support",
            title="Создан пакет диагностики после ошибки",
            details="Пакет диагностики создан в выбранном расположении.",
        )
        return result

    def _collect_system_health_snapshot(self):
        return self.system_health_service.collect(
            repository=self.repository,
            database_health_service=self.database_health_service,
            auto_backup_service=self.auto_backup_service,
            backup_catalog_service=self.backup_catalog_service,
            journal=self.system_health_journal,
            backup_directories=self._database_backup_directories(),
        )

    def _request_system_health_refresh(self) -> None:
        if self._lifecycle_state is not BusinessWorkflowLifecycleState.OPEN:
            return
        self.system_health_monitor.request_refresh()

    def _system_health_snapshot_ready(self, snapshot: object) -> None:
        if self._lifecycle_state is not BusinessWorkflowLifecycleState.OPEN:
            return
        if not hasattr(snapshot, "severity"):
            return

        self.system_health_badge.set_snapshot(snapshot)
        severity = snapshot.severity
        previous = self._last_health_severity
        self._last_health_severity = severity

        if previous is None or previous == severity:
            return

        self._record_system_event(
            severity=severity,
            component="system",
            title="Изменилось общее состояние системы",
            details=(f"{previous.value} → {severity.value}; " + "; ".join(snapshot.issues)),
        )

        if severity in {
            SystemHealthSeverity.WARNING,
            SystemHealthSeverity.ERROR,
        }:
            tone = (
                StatusTone.ERROR if severity == SystemHealthSeverity.ERROR else StatusTone.WARNING
            )
            self.status_banner.show_status(
                title=snapshot.status_label,
                message=(
                    snapshot.issues[0]
                    if snapshot.issues
                    else "Откройте центр состояния для подробностей."
                ),
                tone=tone,
                auto_hide_ms=9000,
            )

    def _system_health_check_failed(self, message: str) -> None:
        if self._lifecycle_state is not BusinessWorkflowLifecycleState.OPEN:
            return
        self.system_health_badge.set_error(message)
        self._record_system_event(
            severity=SystemHealthSeverity.WARNING,
            component="system",
            title="Не удалось обновить состояние системы",
            details=message,
        )

    def _record_system_event(
        self,
        *,
        severity: SystemHealthSeverity | str,
        component: str,
        title: str,
        details: str = "",
    ) -> None:
        try:
            self.system_health_journal.record(
                severity=severity,
                component=component,
                title=title,
                details=details,
            )
        except Exception:
            # Diagnostics must never interrupt the business workflow UI.
            return

    def _open_system_health_center(self) -> None:
        dialog = SystemHealthCenterDialog(
            repository=self.repository,
            health_service=self.system_health_service,
            journal=self.system_health_journal,
            database_health_service=self.database_health_service,
            auto_backup_service=self.auto_backup_service,
            backup_catalog_service=self.backup_catalog_service,
            backup_directories=self._database_backup_directories(),
            theme=self._theme,
            parent=self,
        )
        dialog.database_diagnostics_requested.connect(self._run_database_diagnostics)
        dialog.backup_center_requested.connect(self._open_backup_center)
        dialog.crash_reports_requested.connect(self._open_crash_report_center)
        dialog.exec()
        self._request_system_health_refresh()

    def _open_crash_report_center(self) -> None:
        dialog = CrashReportCenterDialog(
            catalog_service=self.crash_report_catalog_service,
            directories=[self.crash_report_service.directory],
            support_bundle_provider=(self.create_diagnostic_support_bundle),
            theme=self._theme,
            parent=self,
        )
        dialog.exec()

    def _database_backup_directories(self) -> list[Path]:
        settings = self.auto_backup_service.load_settings()
        automatic_directory = self.auto_backup_service.backup_directory(
            self.repository,
            settings,
        )
        return [
            self.repository.path.parent / "backups",
            automatic_directory,
        ]

    def _initialize_database_safety(self) -> None:
        """Run a fast, non-blocking startup check.

        A modal recovery dialog must never be opened from a zero-delay
        timer: it blocks headless tests and may make application startup
        appear frozen. Full backup discovery and recovery remain available
        through the explicit «Диагностика базы…» action.
        """
        if self._lifecycle_state is not BusinessWorkflowLifecycleState.OPEN:
            return
        report = self._inspect_database_health(include_backups=False)
        if report.requires_recovery:
            self._record_system_event(
                severity=SystemHealthSeverity.ERROR,
                component="database",
                title="Стартовая диагностика обнаружила ошибку",
                details=(
                    f"{report.status_label}: " + "; ".join(issue.message for issue in report.issues)
                ),
            )
            self.status_banner.show_status(
                title="База требует диагностики",
                message=(
                    f"{report.status_label}. "
                    "Автокопирование приостановлено. "
                    "Откройте «Данные → Диагностика базы…»."
                ),
                tone=StatusTone.WARNING,
                auto_hide_ms=12000,
            )
            return

        if report.safe_for_backup:
            self._record_system_event(
                severity=SystemHealthSeverity.SUCCESS,
                component="database",
                title="Стартовая диагностика завершена",
                details=(
                    f"{report.status_label}; "
                    f"записей: {report.record_count}; "
                    f"событий: {report.event_count}."
                ),
            )
            self._check_automatic_backup()

    def _run_database_diagnostics(self) -> None:
        self._database_health_prompt_shown = False
        report = self._inspect_database_health(include_backups=True)
        self._record_system_event(
            severity=(
                SystemHealthSeverity.ERROR
                if report.requires_recovery
                else SystemHealthSeverity.SUCCESS
            ),
            component="database",
            title="Выполнена ручная диагностика базы",
            details=(
                f"{report.status_label}; "
                f"записей: {report.record_count}; "
                f"событий: {report.event_count}."
            ),
        )
        if report.requires_recovery:
            self._show_database_recovery(report)
            return

        if report.status == WorkflowDatabaseHealthStatus.MISSING:
            message = "Файл базы ещё не создан. Он появится после добавления первой записи."
        else:
            message = (
                f"Состояние: {report.status_label}; "
                f"записей: {report.record_count}; "
                f"событий: {report.event_count}; "
                f"схема: {report.schema_version}."
            )

        QMessageBox.information(
            self,
            "Диагностика базы завершена",
            message,
        )

    def _inspect_database_health(
        self,
        *,
        include_backups: bool,
    ) -> WorkflowDatabaseHealthReport:
        directories = self._database_backup_directories() if include_backups else ()
        return self.database_health_service.inspect(
            self.repository,
            backup_directories=directories,
        )

    def _show_database_recovery(
        self,
        report: WorkflowDatabaseHealthReport,
    ) -> None:
        if self._database_health_prompt_shown:
            return
        self._database_health_prompt_shown = True

        dialog = WorkflowDatabaseRecoveryDialog(
            report,
            theme=self._theme,
            parent=self,
        )
        dialog.exec()
        action = dialog.selected_action
        self._database_health_prompt_shown = False

        if action == WorkflowDatabaseRecoveryAction.RESTORE_LATEST:
            self._recover_latest_database_backup()
        elif action == WorkflowDatabaseRecoveryAction.OPEN_BACKUP_CENTER:
            self._database_health_prompt_shown = False
            self._open_backup_center()
        elif action == WorkflowDatabaseRecoveryAction.INITIALIZE_EMPTY:
            self._initialize_empty_database()
        else:
            self.status_banner.show_status(
                title="База требует восстановления",
                message=(
                    "Автоматическое резервное копирование приостановлено до устранения ошибки."
                ),
                tone=StatusTone.WARNING,
                auto_hide_ms=9000,
            )

    def _recover_latest_database_backup(self) -> None:
        answer = QMessageBox.warning(
            self,
            "Восстановить последнюю исправную копию?",
            (
                "Повреждённый JSON будет сохранён в карантин, "
                "после чего база будет восстановлена из последней "
                "проверенной резервной копии."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            result = self.database_health_service.recover_latest(
                self.repository,
                backup_directories=(self._database_backup_directories()),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка автоматического восстановления",
                self._safe_workflow_error(exc, reason=OperationReasonCode.DATA_DAMAGED),
            )
            return

        self._database_health_prompt_shown = False
        self.refresh()
        self.workflow_changed.emit()
        self.status_banner.show_status(
            title="База успешно восстановлена",
            message=(
                f"Записей: {result.report.record_count}; "
                f"событий: {result.report.event_count}. "
                + (
                    "Повреждённые данные сохранены в карантине."
                    if result.quarantine_path is not None
                    else "Карантинная копия не требовалась."
                )
            ),
            tone=StatusTone.SUCCESS,
            auto_hide_ms=10000,
        )

    def _initialize_empty_database(self) -> None:
        answer = QMessageBox.warning(
            self,
            "Создать пустую базу?",
            (
                "Текущий повреждённый JSON будет сохранён "
                "в карантин. В приложении будет создана новая "
                "пустая база. Используйте это действие только "
                "когда исправной резервной копии нет."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            result = self.database_health_service.initialize_empty(
                self.repository,
                backup_directories=(self._database_backup_directories()),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка создания пустой базы",
                self._safe_workflow_error(exc, reason=OperationReasonCode.DATA_DAMAGED),
            )
            return

        self._database_health_prompt_shown = False
        self.refresh()
        self.workflow_changed.emit()
        self.status_banner.show_status(
            title="Создана новая пустая база",
            message=(
                "Повреждённые данные сохранены в карантине."
                if result.quarantine_path is not None
                else "Карантинная копия не требовалась."
            ),
            tone=StatusTone.WARNING,
            auto_hide_ms=10000,
        )

    def _open_backup_center(self) -> None:
        directories = self._database_backup_directories()

        dialog = WorkflowBackupCenterDialog(
            repository=self.repository,
            backup_service=self.backup_service,
            catalog_service=self.backup_catalog_service,
            directories=directories,
            theme=self._theme,
            parent=self,
        )
        dialog.backup_restored.connect(self._backup_center_restored)
        dialog.exec()

    def _backup_center_restored(self, result: object) -> None:
        self._database_health_prompt_shown = False
        self._record_system_event(
            severity=SystemHealthSeverity.SUCCESS,
            component="backup",
            title="База восстановлена из Центра копий",
            details=(
                f"Записей: {getattr(result, 'record_count', 0)}; "
                f"событий: {getattr(result, 'event_count', 0)}."
            ),
        )
        self.refresh()
        self.workflow_changed.emit()

        record_count = getattr(result, "record_count", 0)
        event_count = getattr(result, "event_count", 0)
        safety_backup = getattr(result, "safety_backup", "")

        self.status_banner.show_status(
            title="Данные восстановлены из центра копий",
            message=(
                f"Записей: {record_count}; "
                f"событий: {event_count}. "
                f"Страховочная копия: {safety_backup}"
            ),
            tone=StatusTone.SUCCESS,
            auto_hide_ms=9000,
        )

    def _configure_automatic_backup(self) -> None:
        current = self.auto_backup_service.load_settings()
        dialog = WorkflowBackupSettingsDialog(
            current,
            default_directory=self.auto_backup_service.backup_directory(
                self.repository,
                current,
            ),
            auto_backup_service=self.auto_backup_service,
            theme=self._theme,
            parent=self,
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        values = dialog.settings()
        try:
            saved = self.auto_backup_service.update_preferences(
                enabled=values.enabled,
                interval_hours=values.interval_hours,
                retention_count=values.retention_count,
                directory=values.directory,
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка сохранения настроек",
                self._safe_workflow_error(exc),
            )
            return

        if saved.enabled:
            next_run = self.auto_backup_service.next_run_at(saved)
            next_text = (
                next_run.strftime("%d.%m.%Y %H:%M")
                if next_run is not None
                else "при следующей проверке"
            )
            message = (
                f"Интервал: {saved.interval_hours} ч.; "
                f"хранить: {saved.retention_count}; "
                f"следующая копия: {next_text}."
            )
        else:
            message = "Автоматическое резервное копирование отключено."

        self.status_banner.show_status(
            title="Настройки автокопирования сохранены",
            message=message,
            tone=StatusTone.SUCCESS,
            auto_hide_ms=6500,
        )

    def _run_automatic_backup_now(self) -> None:
        self._check_automatic_backup(force=True, show_success=True)

    def _check_automatic_backup(
        self,
        *,
        force: bool = False,
        show_success: bool = False,
    ) -> None:
        if self._lifecycle_state is not BusinessWorkflowLifecycleState.OPEN:
            return
        health = self._inspect_database_health(include_backups=False)
        if not health.safe_for_backup:
            if health.requires_recovery:
                self._record_system_event(
                    severity=SystemHealthSeverity.WARNING,
                    component="auto_backup",
                    title="Автокопирование приостановлено",
                    details=health.status_label,
                )
                self.status_banner.show_status(
                    title="Автокопирование приостановлено",
                    message=(
                        "База бизнес-процессов повреждена. Запустите «Данные → Диагностика базы»."
                    ),
                    tone=StatusTone.WARNING,
                    auto_hide_ms=8000,
                )
            return

        try:
            result = self.auto_backup_service.run_if_due(
                self.repository,
                force=force,
            )
        except Exception as exc:
            rendered = self._safe_workflow_error(exc)
            self._record_system_event(
                severity=SystemHealthSeverity.ERROR,
                component="auto_backup",
                title="Ошибка автоматической резервной копии",
                details=rendered,
            )
            self.status_banner.show_status(
                title="Ошибка автоматической резервной копии",
                message=rendered,
                tone=StatusTone.WARNING,
                auto_hide_ms=8000,
            )
            return

        if not result.executed or result.backup is None:
            return

        self._record_system_event(
            severity=SystemHealthSeverity.SUCCESS,
            component="auto_backup",
            title="Автоматическая резервная копия создана",
            details=f"Удалено старых копий: {len(result.removed_paths)}.",
        )

        if show_success or force:
            removed_text = (
                f"; удалено старых: {len(result.removed_paths)}" if result.removed_paths else ""
            )
            self.status_banner.show_status(
                title="Автоматическая копия создана",
                message=(f"Копия сохранена в настроенном расположении{removed_text}."),
                tone=StatusTone.SUCCESS,
                auto_hide_ms=7000,
            )

    def _create_workflow_backup(self) -> None:
        timestamp = datetime.now()
        default_name = f"CORTERIS_business_workflow_{timestamp:%Y%m%d_%H%M%S}.ctbackup"
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Создать резервную копию бизнес-процессов",
            str(Path.home() / "Documents" / default_name),
            ("Резервная копия CORTERIS (*.ctbackup);;ZIP-архив (*.zip)"),
        )
        if not filename:
            return

        try:
            result = self.backup_service.create_backup(
                self.repository,
                filename,
                created_at=timestamp,
            )
        except Exception as exc:
            rendered = self._safe_workflow_error(exc)
            self._record_system_event(
                severity=SystemHealthSeverity.ERROR,
                component="backup",
                title="Ошибка ручного резервного копирования",
                details=rendered,
            )
            QMessageBox.critical(
                self,
                "Ошибка резервного копирования",
                rendered,
            )
            return

        self._record_system_event(
            severity=SystemHealthSeverity.SUCCESS,
            component="backup",
            title="Ручная резервная копия создана",
            details="Резервная копия создана в выбранном расположении.",
        )
        self.status_banner.show_status(
            title="Резервная копия создана",
            message=(
                f"Записей: {result.inspection.record_count}; "
                f"событий: {result.inspection.event_count}; "
                "копия сохранена в выбранном расположении."
            ),
            tone=StatusTone.SUCCESS,
            auto_hide_ms=7000,
        )

    def _restore_workflow_backup(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Восстановить бизнес-процессы из копии",
            str(Path.home() / "Documents"),
            ("Резервная копия CORTERIS (*.ctbackup *.zip);;Все файлы (*)"),
        )
        if not filename:
            return

        inspection = self.backup_service.inspect_backup(filename)
        if not inspection.valid:
            QMessageBox.critical(
                self,
                "Резервная копия повреждена",
                "Резервная копия не прошла проверку. Откройте диагностику или выберите другую копию.",
            )
            return

        created = inspection.created_timestamp
        created_text = (
            created.strftime("%d.%m.%Y %H:%M:%S")
            if created is not None
            else inspection.created_at or "не указана"
        )
        answer = QMessageBox.warning(
            self,
            "Восстановить резервную копию?",
            (
                "Текущие КП, сметы, проекты и журнал изменений "
                "будут заменены.\n\n"
                f"Дата копии: {created_text}\n"
                f"Записей: {inspection.record_count}\n"
                f"Архивных: {inspection.archived_count}\n"
                f"Событий: {inspection.event_count}\n"
                f"Схема данных: {inspection.schema_version}\n\n"
                "Перед заменой будет создана автоматическая "
                "страховочная копия текущих данных."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            result = self.backup_service.restore_backup(
                filename,
                self.repository,
            )
        except Exception as exc:
            rendered = self._safe_workflow_error(exc)
            self._record_system_event(
                severity=SystemHealthSeverity.ERROR,
                component="backup",
                title="Ошибка восстановления резервной копии",
                details=rendered,
            )
            QMessageBox.critical(
                self,
                "Ошибка восстановления",
                rendered,
            )
            return

        self._record_system_event(
            severity=SystemHealthSeverity.SUCCESS,
            component="backup",
            title="База восстановлена из резервной копии",
            details="Восстановление завершено; страховочная копия сохранена.",
        )
        self.refresh()
        self.workflow_changed.emit()
        self.status_banner.show_status(
            title="Данные восстановлены",
            message=(
                f"Записей: {result.record_count}; "
                f"событий: {result.event_count}. "
                "Страховочная копия сохранена."
            ),
            tone=StatusTone.SUCCESS,
            auto_hide_ms=9000,
        )

    def _save_excel_template(self) -> None:
        default_path = Path.home() / "Documents" / self.excel_template_service.DEFAULT_FILENAME
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить шаблон массового импорта",
            str(default_path),
            "Книга Excel (*.xlsx)",
        )
        if not filename:
            return

        try:
            result = self.excel_template_service.copy_to(filename)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка сохранения шаблона",
                self._safe_workflow_error(exc),
            )
            return

        self.status_banner.show_status(
            title="Шаблон Excel сохранён",
            message=(
                "Шаблон сохранён в выбранном расположении · "
                f"размер: {result.size_bytes / 1024:.1f} КБ"
            ),
            tone=StatusTone.SUCCESS,
            auto_hide_ms=6000,
        )

    def _import_excel(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Импорт КП, смет и проектов из Excel",
            str(Path.home() / "Documents"),
            "Книга Excel (*.xlsx)",
        )
        if not filename:
            return

        try:
            preview = self.excel_importer.preview(
                filename,
                existing_records=self.repository.list_records(include_archived=True),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка проверки Excel",
                self._safe_workflow_error(exc),
            )
            return

        dialog = WorkflowImportPreviewDialog(
            preview,
            theme=self._theme,
            parent=self,
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        try:
            result = self.excel_importer.apply(
                preview,
                self.repository,
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка импорта",
                self._safe_workflow_error(exc),
            )
            return

        preferred_id = result.imported_ids[-1] if result.imported_ids else None
        self.refresh(preferred_record_id=preferred_id)
        self.workflow_changed.emit()

        if result.failures:
            tone = StatusTone.WARNING
            failure_text = f" Ошибок выполнения: {len(result.failures)}."
        else:
            tone = StatusTone.SUCCESS
            failure_text = ""

        self.status_banner.show_status(
            title="Импорт Excel завершён",
            message=(
                f"Создано: {result.created}; "
                f"обновлено: {result.updated}; "
                f"архивировано: {result.archived}; "
                f"пропущено: {result.skipped}."
                f"{failure_text}"
            ),
            tone=tone,
            auto_hide_ms=7000,
        )

    def _export_excel(self) -> None:
        records = self._visible_records()
        if not records:
            QMessageBox.information(
                self,
                "Нет данных для экспорта",
                "Текущий фильтр не содержит записей.",
            )
            return

        timestamp = datetime.now()
        default_name = f"CORTERIS_Реестр_КП_смет_проектов_{timestamp:%Y%m%d_%H%M}.xlsx"
        default_path = Path.home() / "Documents" / default_name

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Экспорт реестра и журнала в Excel",
            str(default_path),
            "Книга Excel (*.xlsx)",
        )
        if not filename:
            return

        target = Path(filename)
        if target.suffix.lower() != ".xlsx":
            target = target.with_suffix(".xlsx")

        try:
            events = [
                event for record in records for event in self.repository.list_history(record.id)
            ]
            result = self.excel_exporter.export(
                target,
                records=records,
                events=events,
                filter_description=self._export_filter_description(),
                exported_at=timestamp,
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка экспорта",
                self._safe_workflow_error(exc),
            )
            return

        self.status_banner.show_status(
            title="Excel-файл сформирован",
            message=(
                f"Записей: {result.record_count}; "
                f"событий: {result.event_count}. "
                "Excel-файл сохранён в выбранном расположении."
            ),
            tone=StatusTone.SUCCESS,
            auto_hide_ms=6000,
        )

    def _visible_records(self) -> list[BusinessWorkflowRecord]:
        """Return records currently visible after all UI filters."""
        records: list[BusinessWorkflowRecord] = []
        for proxy_row in range(self.proxy.rowCount()):
            proxy_index = self.proxy.index(proxy_row, 0)
            source_index = self.proxy.mapToSource(proxy_index)
            record = self.model.record_at(source_index.row())
            if record is not None:
                records.append(record)
        return records

    def _export_filter_description(self) -> str:
        parts = [
            f"Тип: {self.kind_filter.currentText()}",
            f"Статус: {self.status_filter.currentText()}",
            f"Архив: {self.archive_filter.currentText()}",
        ]
        search = self.search_edit.text().strip()
        if search:
            parts.append(f"Поиск: {search}")
        return "; ".join(parts)

    def _load_history(self, record_id: str) -> None:
        try:
            events = self.repository.list_history(
                record_id,
                limit=50,
            )
        except Exception as exc:
            self.history_list.clear()
            self.history_empty.setText(self._safe_workflow_error(exc))
            self.history_empty.show()
            return

        self.history_list.clear()
        self.history_empty.setText("История для выбранной записи пока отсутствует.")
        self.history_empty.setVisible(not events)
        self.history_list.setVisible(bool(events))

        for event in events:
            item = QListWidgetItem(self._history_event_text(event))
            item.setToolTip(self._history_event_tooltip(event))
            self.history_list.addItem(item)

    def _history_event_text(
        self,
        event: BusinessAuditEvent,
    ) -> str:
        timestamp = event.timestamp.strftime("%d.%m.%Y %H:%M")
        action = BusinessAuditAction(event.action)

        if action == BusinessAuditAction.CREATED:
            detail = "Создана запись"
        elif action == BusinessAuditAction.ARCHIVED:
            detail = "Запись перемещена в архив"
        elif action == BusinessAuditAction.RESTORED:
            detail = "Запись восстановлена из архива"
        elif action == BusinessAuditAction.STATUS_CHANGED:
            detail = (
                f"Статус: {self._history_value(event.field, event.old_value)}"
                f" → {self._history_value(event.field, event.new_value)}"
            )
        else:
            field_label = self._history_field_label(event.field)
            detail = (
                f"{field_label}: "
                f"{self._history_value(event.field, event.old_value)}"
                f" → {self._history_value(event.field, event.new_value)}"
            )

        return f"{timestamp}\n{detail}"

    def _history_event_tooltip(
        self,
        event: BusinessAuditEvent,
    ) -> str:
        return f"Событие: {event.action}\nПоле: {event.field or '—'}\nПользователь: {event.actor}"

    @staticmethod
    def _history_field_label(field: str) -> str:
        return {
            "title": "Название",
            "status": "Статус",
            "total": "Сумма",
            "profit": "Прибыль",
            "margin_percent": "Маржа",
            "file_path": "Файл",
            "due_date": "Срок",
            "archived_at": "Архив",
        }.get(field, field or "Запись")

    def _history_value(self, field: str, value: str) -> str:
        if value == "":
            return "не указано"

        if field == "status":
            try:
                return status_label(BusinessStatus(value))
            except ValueError:
                return value

        if field in {"total", "profit"}:
            try:
                return self._money(Decimal(value))
            except Exception:
                return value

        if field == "margin_percent":
            try:
                return f"{Decimal(value):.2f}%"
            except Exception:
                return value

        return value

    def _archive_selected(self) -> None:
        record = self._selected_record
        if record is None or record.is_archived:
            return

        answer = QMessageBox.question(
            self,
            "Переместить в архив?",
            (
                f"Запись «{record.title}» будет исключена из KPI "
                "и активных бизнес-процессов. Данные сохранятся "
                "и запись можно будет восстановить."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            archived = self.repository.archive_record(record.id)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка архивирования",
                self._safe_workflow_error(exc),
            )
            return

        archive_index = self.archive_filter.findData(WorkflowArchiveMode.ARCHIVED.value)
        if archive_index >= 0:
            self.archive_filter.setCurrentIndex(archive_index)

        self.status_banner.show_status(
            title="Запись перемещена в архив",
            message=archived.title,
            tone=StatusTone.SUCCESS,
            auto_hide_ms=3000,
        )
        self.refresh(preferred_record_id=archived.id)
        self.workflow_changed.emit()

    def _restore_selected(self) -> None:
        record = self._selected_record
        if record is None or not record.is_archived:
            return

        try:
            restored = self.repository.restore_record(record.id)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка восстановления",
                self._safe_workflow_error(exc),
            )
            return

        active_index = self.archive_filter.findData(WorkflowArchiveMode.ACTIVE.value)
        if active_index >= 0:
            self.archive_filter.setCurrentIndex(active_index)

        self.status_banner.show_status(
            title="Запись восстановлена",
            message=restored.title,
            tone=StatusTone.SUCCESS,
            auto_hide_ms=3000,
        )
        self.refresh(preferred_record_id=restored.id)
        self.workflow_changed.emit()

    def _edit_selected(self) -> None:
        record = self._selected_record
        if record is None:
            return

        dialog = BusinessRecordDialog(
            record=record,
            theme=self._theme,
            parent=self,
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        payload = dialog.payload()
        try:
            updated = self.repository.update_record(
                record.id,
                title=payload["title"],
                total=payload["total"],
                profit=payload["profit"],
                margin_percent=payload["margin_percent"],
                file_path=payload["file_path"],
                due_date=payload["due_date"],
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка редактирования",
                self._safe_workflow_error(exc),
            )
            return

        self.status_banner.show_status(
            title="Изменения сохранены",
            message=updated.title,
            tone=StatusTone.SUCCESS,
            auto_hide_ms=2500,
        )
        self.refresh(preferred_record_id=updated.id)
        self.workflow_changed.emit()

    def _create_record(self) -> None:
        initial_kind = (
            BusinessRecordKind(str(self.kind_filter.currentData()))
            if self.kind_filter.currentData()
            else self._initial_kind or BusinessRecordKind.PROPOSAL
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
                self._safe_workflow_error(exc),
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
                self._safe_workflow_error(exc),
            )
            return

        self.status_banner.show_status(
            title="Статус обновлён",
            message=(f"{record.title}: {status_label(target)}."),
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

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

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
        self._reconcile_visible_selection()

    def _on_kind_filter_changed(self) -> None:
        value = self.kind_filter.currentData()
        self.proxy.set_kind(value or None)
        self._reconcile_visible_selection()

    def _on_archive_filter_changed(self) -> None:
        value = str(self.archive_filter.currentData() or WorkflowArchiveMode.ACTIVE.value)
        self.proxy.set_archive_mode(value)
        self._reconcile_visible_selection()

    def _on_status_filter_changed(self) -> None:
        value = self.status_filter.currentData()
        self.proxy.set_status(value or None)
        self._reconcile_visible_selection()

    def _reset_filters(self) -> None:
        self.search_edit.clear()
        self.kind_filter.setCurrentIndex(0)
        self.status_filter.setCurrentIndex(0)
        self.archive_filter.setCurrentIndex(0)
        self.apply_dashboard_filter(None)

    @property
    def dashboard_filter(self) -> DashboardFilterId | None:
        return self._dashboard_filter

    def apply_dashboard_filter(self, dashboard_filter: str | None) -> None:
        """Apply one exact repository-owned workflow KPI scope."""
        if dashboard_filter is None:
            self._dashboard_filter = None
            self.proxy.set_record_scope(None)
            return
        filter_id = DashboardFilterId(dashboard_filter)
        if filter_id.route_id is not RouteId.WORKFLOW:
            raise ValueError("Dashboard filter does not belong to workflow")
        self._dashboard_filter = filter_id
        self._apply_dashboard_scope(self.repository.summary(activity_limit=0))

    def _apply_dashboard_scope(self, summary: BusinessMetricsSnapshot) -> None:
        if self._dashboard_filter is None:
            self.proxy.set_record_scope(None)
            return
        contributor_ids = {
            DashboardFilterId.WORKFLOW_PROFIT_CONTRIBUTORS: (summary.profit_contributor_ids),
            DashboardFilterId.WORKFLOW_ACTIVE_PROPOSALS: summary.proposal_ids,
            DashboardFilterId.WORKFLOW_ACTIVE_PROJECTS: summary.project_ids,
            DashboardFilterId.WORKFLOW_ATTENTION: summary.attention_ids,
        }[self._dashboard_filter]
        self.proxy.set_record_scope(contributor_ids)

    def _restore_initial_filter(self) -> None:
        if self._initial_kind is None:
            return
        if self.kind_filter.currentData():
            return

        index = self.kind_filter.findData(self._initial_kind.value)
        if index >= 0:
            self.kind_filter.setCurrentIndex(index)

    def _select_record_id(self, record_id: str) -> bool:
        for source_row, record in enumerate(self.model.records):
            if record.id != record_id:
                continue

            source_index = self.model.index(source_row, 0)
            proxy_index = self.proxy.mapFromSource(source_index)
            if not proxy_index.isValid():
                return False

            self.table.setCurrentIndex(proxy_index)
            self.table.selectRow(proxy_index.row())
            self.table.scrollTo(proxy_index)
            self._set_selected_record(record)
            return True
        return False

    def _select_first_visible(self) -> None:
        if self.proxy.rowCount() <= 0:
            self.table.clearSelection()
            self._set_selected_record(None)
            return

        index = self.proxy.index(0, 0)
        self.table.setCurrentIndex(index)
        self.table.selectRow(0)

    def _reconcile_visible_selection(self) -> None:
        record = self._selected_record
        if record is not None and self._select_record_id(record.id):
            return
        self.table.clearSelection()
        self._set_selected_record(None)

    def _restore_exact_selection_after_model_change(self) -> None:
        record = self._selected_record
        if record is not None and not self._select_record_id(record.id):
            self.table.clearSelection()
            self._set_selected_record(None)

    @staticmethod
    def _money(value: Decimal | float) -> str:
        amount = Decimal(str(value or 0))
        return format_money(MoneyAmount(amount))


__all__ = [
    "BusinessWorkflowLifecycleState",
    "BusinessWorkflowPage",
    "WorkflowNavigationState",
]
