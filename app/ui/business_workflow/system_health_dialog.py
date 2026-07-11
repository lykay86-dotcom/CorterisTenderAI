"""Unified system health center for workflow services."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.diagnostic_support_bundle import (
    DiagnosticSupportBundleService,
)
from app.core.system_health import (
    SystemHealthEvent,
    SystemHealthJournal,
    SystemHealthService,
    SystemHealthSeverity,
    SystemHealthSnapshot,
)
from app.core.workflow_auto_backup import WorkflowAutoBackupService
from app.core.workflow_backup_catalog import WorkflowBackupCatalogService
from app.core.workflow_database_health import WorkflowDatabaseHealthService
from app.repositories.business_metrics import BusinessMetricsRepository
from app.ui.theme.colors import ThemeName, get_palette
from app.ui.theme.typography import Typography


class SystemHealthCenterDialog(QDialog):
    """Display current health and a persistent diagnostic journal."""

    database_diagnostics_requested = Signal()
    backup_center_requested = Signal()

    def __init__(
        self,
        *,
        repository: BusinessMetricsRepository,
        health_service: SystemHealthService,
        journal: SystemHealthJournal,
        database_health_service: WorkflowDatabaseHealthService,
        auto_backup_service: WorkflowAutoBackupService,
        backup_catalog_service: WorkflowBackupCatalogService,
        backup_directories: list[Path],
        support_bundle_service: (
            DiagnosticSupportBundleService | None
        ) = None,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.repository = repository
        self.health_service = health_service
        self.journal = journal
        self.database_health_service = database_health_service
        self.auto_backup_service = auto_backup_service
        self.backup_catalog_service = backup_catalog_service
        self.backup_directories = backup_directories
        self.support_bundle_service = (
            support_bundle_service
            or DiagnosticSupportBundleService()
        )
        self.snapshot: SystemHealthSnapshot | None = None
        self._theme = ThemeName(theme)

        self.setWindowTitle("Состояние системы")
        self.setModal(True)
        self.resize(1120, 760)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        title = QLabel("Состояние системы", self)
        title.setObjectName("SystemHealthTitle")
        root.addWidget(title)

        subtitle = QLabel(
            "Диагностика базы, резервного копирования "
            "и журнал системных событий CORTERIS Tender AI.",
            self,
        )
        subtitle.setObjectName("SystemHealthSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.refresh_button = QPushButton("Обновить", self)
        self.refresh_button.clicked.connect(self.refresh)

        self.database_button = QPushButton(
            "Диагностика базы…",
            self,
        )
        self.database_button.clicked.connect(
            self._request_database_diagnostics
        )

        self.backup_button = QPushButton(
            "Центр резервных копий…",
            self,
        )
        self.backup_button.clicked.connect(
            self._request_backup_center
        )

        self.support_bundle_button = QPushButton(
            "Пакет диагностики…",
            self,
        )
        self.support_bundle_button.clicked.connect(
            self._export_support_bundle
        )

        toolbar.addWidget(self.refresh_button)
        toolbar.addWidget(self.database_button)
        toolbar.addWidget(self.backup_button)
        toolbar.addWidget(self.support_bundle_button)
        toolbar.addStretch(1)

        self.checked_label = QLabel("", self)
        self.checked_label.setObjectName("SystemHealthChecked")
        toolbar.addWidget(self.checked_label)

        root.addLayout(toolbar)

        cards = QGridLayout()
        cards.setHorizontalSpacing(10)
        cards.setVerticalSpacing(10)

        self.overall_card, self.overall_value, self.overall_details = (
            self._create_card("Общее состояние")
        )
        self.database_card, self.database_value, self.database_details = (
            self._create_card("База бизнес-процессов")
        )
        self.backup_card, self.backup_value, self.backup_details = (
            self._create_card("Резервные копии")
        )
        self.auto_card, self.auto_value, self.auto_details = (
            self._create_card("Автокопирование")
        )

        cards.addWidget(self.overall_card, 0, 0)
        cards.addWidget(self.database_card, 0, 1)
        cards.addWidget(self.backup_card, 1, 0)
        cards.addWidget(self.auto_card, 1, 1)
        root.addLayout(cards)

        self.issues_label = QLabel("", self)
        self.issues_label.setObjectName("SystemHealthIssues")
        self.issues_label.setWordWrap(True)
        self.issues_label.setVisible(False)
        root.addWidget(self.issues_label)

        journal_title_row = QHBoxLayout()
        journal_title = QLabel("Журнал системных событий", self)
        journal_title.setObjectName("SystemHealthSectionTitle")
        journal_title_row.addWidget(journal_title)
        journal_title_row.addStretch(1)

        self.export_button = QPushButton("Экспорт журнала…", self)
        self.export_button.clicked.connect(self._export_journal)
        journal_title_row.addWidget(self.export_button)

        self.clear_button = QPushButton("Очистить журнал", self)
        self.clear_button.setObjectName("SystemHealthClearButton")
        self.clear_button.clicked.connect(self._clear_journal)
        journal_title_row.addWidget(self.clear_button)

        root.addLayout(journal_title_row)

        self.table = QTableWidget(0, 5, self)
        self.table.setObjectName("SystemHealthTable")
        self.table.setHorizontalHeaderLabels(
            (
                "Дата",
                "Уровень",
                "Компонент",
                "Событие",
                "Подробности",
            )
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(True)
        self.table.verticalHeader().hide()

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            4,
            QHeaderView.ResizeMode.Stretch,
        )
        root.addWidget(self.table, 1)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close,
            self,
        )
        self.buttons.button(
            QDialogButtonBox.StandardButton.Close
        ).setText("Закрыть")
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        self.apply_theme(self._theme)
        self.refresh()

    def _create_card(
        self,
        title: str,
    ) -> tuple[QFrame, QLabel, QLabel]:
        card = QFrame(self)
        card.setObjectName("SystemHealthCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(5)

        title_label = QLabel(title, card)
        title_label.setObjectName("SystemHealthCardTitle")
        layout.addWidget(title_label)

        value_label = QLabel("—", card)
        value_label.setObjectName("SystemHealthCardValue")
        value_label.setWordWrap(True)
        layout.addWidget(value_label)

        details_label = QLabel("", card)
        details_label.setObjectName("SystemHealthCardDetails")
        details_label.setWordWrap(True)
        layout.addWidget(details_label)

        return card, value_label, details_label

    def refresh(self) -> None:
        try:
            self.snapshot = self.health_service.collect(
                repository=self.repository,
                database_health_service=self.database_health_service,
                auto_backup_service=self.auto_backup_service,
                backup_catalog_service=self.backup_catalog_service,
                journal=self.journal,
                backup_directories=self.backup_directories,
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка проверки состояния системы",
                str(exc),
            )
            return

        snapshot = self.snapshot
        self.checked_label.setText(
            "Проверено: "
            f"{snapshot.checked_at:%d.%m.%Y %H:%M:%S}"
        )
        self.overall_value.setText(snapshot.status_label)
        self.overall_details.setText(
            f"Событий в журнале: {snapshot.journal_count}"
        )

        self.database_value.setText(
            snapshot.database.status_label
        )
        self.database_details.setText(
            f"Записей: {snapshot.database.record_count} · "
            f"событий: {snapshot.database.event_count} · "
            f"схема: {snapshot.database.schema_version or '—'}"
        )

        self.backup_value.setText(
            f"Исправных: {snapshot.backup_valid}"
        )
        latest_text = (
            snapshot.latest_backup_at.strftime(
                "%d.%m.%Y %H:%M"
            )
            if snapshot.latest_backup_at is not None
            else "нет"
        )
        self.backup_details.setText(
            f"Всего: {snapshot.backup_total} · "
            f"повреждённых: {snapshot.backup_invalid} · "
            f"последняя: {latest_text}"
        )

        self.auto_value.setText(
            "Включено"
            if snapshot.auto_backup_enabled
            else "Отключено"
        )
        last_success = self._datetime_text(
            snapshot.auto_backup_last_success_at
        )
        self.auto_details.setText(
            f"Интервал: {snapshot.auto_backup_interval_hours} ч. · "
            f"хранить: {snapshot.auto_backup_retention_count} · "
            f"последняя: {last_success}"
        )

        self.issues_label.setVisible(bool(snapshot.issues))
        self.issues_label.setText(
            "\n".join(
                f"• {issue}"
                for issue in snapshot.issues
            )
        )

        self._populate_events(
            self.journal.list_events(limit=200)
        )
        self._apply_snapshot_colors(snapshot)

    def _populate_events(
        self,
        events: tuple[SystemHealthEvent, ...],
    ) -> None:
        self.table.setRowCount(len(events))
        for row, event in enumerate(events):
            timestamp = event.timestamp
            time_text = (
                timestamp.strftime("%d.%m.%Y %H:%M:%S")
                if timestamp is not None
                else event.occurred_at
            )
            values = (
                time_text,
                self._severity_label(event.severity),
                event.component,
                event.title,
                event.details,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignTop
                    | Qt.AlignmentFlag.AlignLeft
                )
                self.table.setItem(row, column, item)
            self.table.resizeRowToContents(row)

    def _apply_snapshot_colors(
        self,
        snapshot: SystemHealthSnapshot,
    ) -> None:
        palette = get_palette(self._theme)
        color = {
            SystemHealthSeverity.SUCCESS: palette.success,
            SystemHealthSeverity.INFO: palette.info,
            SystemHealthSeverity.WARNING: palette.warning,
            SystemHealthSeverity.ERROR: palette.danger,
        }[snapshot.severity]
        self.overall_value.setStyleSheet(
            f"color: {color}; {Typography.H3.css()}"
        )

    def _request_database_diagnostics(self) -> None:
        self.accept()
        self.database_diagnostics_requested.emit()

    def _request_backup_center(self) -> None:
        self.accept()
        self.backup_center_requested.emit()

    def _export_support_bundle(self) -> None:
        if self.snapshot is None:
            self.refresh()
        if self.snapshot is None:
            return

        default_name = (
            "CORTERIS_diagnostic_support_"
            f"{datetime.now():%Y%m%d_%H%M%S}.ctsupport"
        )
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Создать пакет технической диагностики",
            str(Path.home() / "Documents" / default_name),
            (
                "Пакет диагностики CORTERIS (*.ctsupport);;"
                "ZIP-архив (*.zip)"
            ),
        )
        if not filename:
            return

        try:
            result = self.support_bundle_service.create_bundle(
                filename,
                repository=self.repository,
                snapshot=self.snapshot,
                journal=self.journal,
                auto_backup_service=self.auto_backup_service,
                backup_catalog_service=(
                    self.backup_catalog_service
                ),
                backup_directories=self.backup_directories,
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка создания пакета диагностики",
                str(exc),
            )
            return

        try:
            self.journal.record(
                severity=SystemHealthSeverity.SUCCESS,
                component="support",
                title="Создан пакет технической диагностики",
                details=str(result.path),
            )
        except Exception:
            pass

        self.refresh()
        QMessageBox.information(
            self,
            "Пакет диагностики создан",
            (
                f"Файл: {result.path}\n"
                f"Размер: {result.size_bytes / 1024:.1f} КБ\n"
                f"Файлов внутри: {result.file_count}\n\n"
                "Пакет не содержит рабочую базу, документы КП, "
                "сметы, проекты или содержимое резервных копий."
            ),
        )

    def _export_journal(self) -> None:
        default_name = (
            "CORTERIS_system_health_"
            f"{datetime.now():%Y%m%d_%H%M%S}.txt"
        )
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Экспорт журнала состояния",
            str(Path.home() / "Documents" / default_name),
            "Текстовый файл (*.txt)",
        )
        if not filename:
            return

        try:
            path = self.journal.export_text(filename)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка экспорта журнала",
                str(exc),
            )
            return

        QMessageBox.information(
            self,
            "Журнал экспортирован",
            f"Файл сохранён:\n{path}",
        )

    def _clear_journal(self) -> None:
        answer = QMessageBox.warning(
            self,
            "Очистить журнал?",
            (
                "Все сохранённые системные события будут удалены. "
                "Это не влияет на рабочую базу и резервные копии."
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self.journal.clear()
        self.refresh()

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)

        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {palette.app_background};
                color: {palette.text_primary};
            }}
            QLabel#SystemHealthTitle {{
                color: {palette.text_primary};
                {Typography.H2.css()}
            }}
            QLabel#SystemHealthSubtitle,
            QLabel#SystemHealthChecked,
            QLabel#SystemHealthCardDetails {{
                color: {palette.text_secondary};
                {Typography.BODY_S.css()}
            }}
            QLabel#SystemHealthSectionTitle,
            QLabel#SystemHealthCardTitle {{
                color: {palette.text_secondary};
                {Typography.BUTTON.css()}
            }}
            QFrame#SystemHealthCard {{
                background-color: {palette.card_background};
                border: 1px solid {palette.border_subtle};
                border-radius: 9px;
            }}
            QLabel#SystemHealthCardValue {{
                color: {palette.text_primary};
                {Typography.H3.css()}
            }}
            QLabel#SystemHealthIssues {{
                color: {palette.warning};
                background-color: {palette.warning_background};
                border: 1px solid {palette.warning};
                border-radius: 8px;
                padding: 10px;
                {Typography.BODY_S.css()}
            }}
            QTableWidget#SystemHealthTable {{
                color: {palette.text_primary};
                background-color: {palette.card_background};
                alternate-background-color: {palette.panel_background};
                gridline-color: {palette.border_subtle};
                border: 1px solid {palette.border_subtle};
                border-radius: 9px;
                selection-background-color: {palette.selected_background};
                selection-color: {palette.text_primary};
                {Typography.BODY_S.css()}
            }}
            QHeaderView::section {{
                color: {palette.text_secondary};
                background-color: {palette.elevated_background};
                border: none;
                border-bottom: 1px solid {palette.border_default};
                padding: 8px;
                {Typography.CAPTION.css()}
            }}
            QPushButton {{
                min-height: 34px;
                color: {palette.text_primary};
                background-color: {palette.elevated_background};
                border: 1px solid {palette.border_default};
                border-radius: 7px;
                padding: 4px 12px;
                {Typography.BUTTON.css()}
            }}
            QPushButton:hover {{
                background-color: {palette.hover_background};
            }}
            QPushButton#SystemHealthClearButton {{
                color: {palette.danger};
                border-color: {palette.danger};
            }}
            """
        )

    @staticmethod
    def _severity_label(
        severity: SystemHealthSeverity,
    ) -> str:
        return {
            SystemHealthSeverity.SUCCESS: "Успешно",
            SystemHealthSeverity.INFO: "Информация",
            SystemHealthSeverity.WARNING: "Предупреждение",
            SystemHealthSeverity.ERROR: "Ошибка",
        }[severity]

    @staticmethod
    def _datetime_text(value: str) -> str:
        if not value:
            return "нет"
        try:
            return datetime.fromisoformat(value).strftime(
                "%d.%m.%Y %H:%M"
            )
        except ValueError:
            return value


__all__ = ["SystemHealthCenterDialog"]
