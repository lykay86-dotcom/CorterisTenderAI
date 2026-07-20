"""Interactive center for workflow backup files."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
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

from app.core.workflow_backup import (
    WorkflowBackupService,
)
from app.core.workflow_backup_catalog import (
    WorkflowBackupCatalogService,
    WorkflowBackupEntry,
)
from app.repositories.business_metrics import (
    BusinessMetricsRepository,
)
from app.ui.theme.colors import ThemeName, get_palette
from app.ui.tables import (
    TableActionToken,
    TableCell,
    TableColumn,
    TableColumnId,
    TableRevision,
    TableRole,
    TableRow,
    TableRowId,
    TableSnapshot,
    TableState,
    TableSurfaceId,
    validate_action_token,
)
from app.ui.theme.typography import Typography


class WorkflowBackupCenterDialog(QDialog):
    """List, validate, restore and delete workflow backups."""

    backup_restored = Signal(object)

    COLUMNS = (
        "Дата копии",
        "Тип",
        "Файл",
        "Записи",
        "События",
        "Размер",
        "Проверка",
    )

    def __init__(
        self,
        *,
        repository: BusinessMetricsRepository,
        backup_service: WorkflowBackupService,
        catalog_service: WorkflowBackupCatalogService,
        directories: list[Path],
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.repository = repository
        self.backup_service = backup_service
        self.catalog_service = catalog_service
        self.directories = self._unique_paths(directories)
        self.external_files: list[Path] = []
        self.entries: list[WorkflowBackupEntry] = []
        self._theme = ThemeName(theme)

        self.setWindowTitle("Центр резервных копий")
        self.setModal(True)
        self.resize(1180, 720)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        title = QLabel("Центр резервных копий", self)
        title.setObjectName("BackupCenterTitle")
        root.addWidget(title)

        subtitle = QLabel(
            "Проверяйте целостность, восстанавливайте и удаляйте "
            "резервные копии КП, смет, проектов и журнала изменений.",
            self,
        )
        subtitle.setObjectName("BackupCenterSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.refresh_button = QPushButton("Обновить", self)
        self.refresh_button.clicked.connect(self.refresh)

        self.add_file_button = QPushButton(
            "Добавить внешний файл…",
            self,
        )
        self.add_file_button.clicked.connect(self._add_external_file)

        self.open_folder_button = QPushButton(
            "Открыть папку",
            self,
        )
        self.open_folder_button.clicked.connect(self._open_selected_folder)
        self.open_folder_button.setEnabled(False)

        toolbar.addWidget(self.refresh_button)
        toolbar.addWidget(self.add_file_button)
        toolbar.addWidget(self.open_folder_button)
        toolbar.addStretch(1)

        self.summary_label = QLabel("", self)
        self.summary_label.setObjectName("BackupCenterSummary")
        toolbar.addWidget(self.summary_label)

        root.addLayout(toolbar)

        self.table = QTableWidget(0, len(self.COLUMNS), self)
        self.table.setObjectName("BackupCenterTable")
        self.table.setAccessibleName("Workflow backups")
        self.table.setAccessibleDescription(
            "Backup files with exact path identity; restore and delete are revalidated after confirmation."
        )
        self.table.setTabKeyNavigation(False)
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.verticalHeader().hide()
        self.table.itemSelectionChanged.connect(self._selection_changed)

        header = self.table.horizontalHeader()
        for column in (0, 1, 3, 4, 5, 6):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )
        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.Stretch,
        )
        root.addWidget(self.table, 1)

        self.details_frame = QFrame(self)
        self.details_frame.setObjectName("BackupCenterDetails")
        details_layout = QVBoxLayout(self.details_frame)
        details_layout.setContentsMargins(14, 12, 14, 12)
        details_layout.setSpacing(6)

        self.details_title = QLabel(
            "Выберите резервную копию.",
            self.details_frame,
        )
        self.details_title.setObjectName("BackupCenterDetailsTitle")
        self.details_title.setWordWrap(True)
        details_layout.addWidget(self.details_title)

        self.details_label = QLabel("", self.details_frame)
        self.details_label.setObjectName("BackupCenterDetailsText")
        self.details_label.setWordWrap(True)
        self.details_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        details_layout.addWidget(self.details_label)

        root.addWidget(self.details_frame)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self.verify_button = QPushButton(
            "Проверить повторно",
            self,
        )
        self.verify_button.clicked.connect(self._verify_selected)
        self.verify_button.setEnabled(False)

        self.restore_button = QPushButton(
            "Восстановить",
            self,
        )
        self.restore_button.setObjectName("BackupCenterRestoreButton")
        self.restore_button.clicked.connect(self._restore_selected)
        self.restore_button.setEnabled(False)

        self.delete_button = QPushButton(
            "Удалить",
            self,
        )
        self.delete_button.setObjectName("BackupCenterDeleteButton")
        self.delete_button.clicked.connect(self._delete_selected)
        self.delete_button.setEnabled(False)

        action_row.addWidget(self.verify_button)
        action_row.addStretch(1)
        action_row.addWidget(self.restore_button)
        action_row.addWidget(self.delete_button)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close,
            self,
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Close).setText("Закрыть")
        self.buttons.rejected.connect(self.reject)
        action_row.addWidget(self.buttons)

        root.addLayout(action_row)

        self.apply_theme(self._theme)
        self.refresh()

    @property
    def selected_entry(self) -> WorkflowBackupEntry | None:
        row = self.table.currentRow()
        if 0 <= row < len(self.entries):
            item = self.table.item(row, 0)
            row_id = item.data(TableRole.ROW_ID) if item is not None else None
            if isinstance(row_id, TableRowId):
                return next(
                    (entry for entry in self.entries if str(entry.path) == row_id.value),
                    None,
                )
        return None

    def refresh(self) -> None:
        current_path = self.selected_entry.path if self.selected_entry is not None else None
        try:
            self.entries = self.catalog_service.list_backups(
                self.directories,
                external_files=self.external_files,
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка чтения резервных копий",
                str(exc),
            )
            return

        self.table.setRowCount(len(self.entries))
        for row, entry in enumerate(self.entries):
            values = (
                entry.created_timestamp.strftime("%d.%m.%Y %H:%M:%S"),
                entry.display_kind,
                entry.path.name,
                str(entry.inspection.record_count),
                str(entry.inspection.event_count),
                self._size_text(entry.size_bytes),
                "Исправна" if entry.valid else "Повреждена",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in {0, 3, 4, 5}:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                else:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                    )
                item.setToolTip(str(entry.path))
                if column == 0:
                    item.setData(TableRole.ROW_ID, self._entry_row_id(entry))
                    item.setData(TableRole.ROW_REVISION, self._entry_revision(entry))
                    item.setData(TableRole.ACTION_IDS, self._entry_action_ids(entry))
                    item.setData(
                        TableRole.STATE,
                        TableState.READY if entry.valid else TableState.PARTIAL,
                    )
                    item.setData(
                        Qt.ItemDataRole.AccessibleTextRole,
                        f"{entry.path.name}; {entry.display_kind}; "
                        f"{'valid' if entry.valid else 'damaged'}",
                    )
                self.table.setItem(row, column, item)

        valid_count = sum(1 for entry in self.entries if entry.valid)
        invalid_count = len(self.entries) - valid_count
        self.summary_label.setText(
            f"Найдено: {len(self.entries)} · "
            f"исправных: {valid_count} · "
            f"повреждённых: {invalid_count}"
        )

        selected_row = -1
        if current_path is not None:
            for row, entry in enumerate(self.entries):
                if entry.path == current_path:
                    selected_row = row
                    break
        if selected_row < 0 and self.entries and current_path is None:
            selected_row = 0

        if selected_row >= 0:
            self.table.selectRow(selected_row)
            self.table.setCurrentCell(selected_row, 0)
        else:
            self.table.clearSelection()
            self.table.setCurrentCell(-1, -1)
            self._selection_changed()

    def _selection_changed(self) -> None:
        entry = self.selected_entry
        selected = entry is not None

        self.verify_button.setEnabled(selected)
        self.open_folder_button.setEnabled(selected)
        self.restore_button.setEnabled(bool(entry and entry.valid))
        self.delete_button.setEnabled(selected)

        if entry is None:
            self.details_title.setText("Выберите резервную копию.")
            self.details_label.clear()
            return

        self.details_title.setText(entry.path.name)
        created = entry.created_timestamp.strftime("%d.%m.%Y %H:%M:%S")
        details = [
            f"Путь: {entry.path}",
            f"Тип: {entry.display_kind}",
            f"Дата копии: {created}",
            f"Размер: {self._size_text(entry.size_bytes)}",
            f"Схема данных: {entry.inspection.schema_version}",
            f"Записей: {entry.inspection.record_count}",
            f"Архивных записей: {entry.inspection.archived_count}",
            f"Событий журнала: {entry.inspection.event_count}",
            (
                "Проверка: файл исправен"
                if entry.valid
                else "Проверка: файл повреждён или несовместим"
            ),
        ]
        if entry.inspection.errors:
            details.append("")
            details.append("Ошибки:")
            details.extend(f"• {error}" for error in entry.inspection.errors)
        self.details_label.setText("\n".join(details))

    def _add_external_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Добавить резервную копию",
            str(Path.home() / "Documents"),
            ("Резервная копия CORTERIS (*.ctbackup *.zip);;Все файлы (*)"),
        )
        if not filename:
            return

        path = Path(filename)
        if path not in self.external_files:
            self.external_files.append(path)
        self.refresh()

    def _verify_selected(self) -> None:
        entry = self.selected_entry
        if entry is None:
            return

        refreshed = self.catalog_service.refresh_entry(
            entry.path,
            managed_directories=self.directories,
        )
        self.entries[self.table.currentRow()] = refreshed
        self.refresh()

    def _open_selected_folder(self) -> None:
        entry = self.selected_entry
        if entry is None:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(entry.path.parent)))

    def _restore_selected(self) -> None:
        entry = self.selected_entry
        if entry is None or not entry.valid:
            return
        token = self._action_token(entry, "restore")

        answer = QMessageBox.warning(
            self,
            "Восстановить выбранную копию?",
            (
                "Текущая база бизнес-процессов будет заменена.\n\n"
                f"Файл: {entry.path.name}\n"
                f"Записей: {entry.inspection.record_count}\n"
                f"Архивных: {entry.inspection.archived_count}\n"
                f"Событий: {entry.inspection.event_count}\n\n"
                "Перед восстановлением автоматически создаётся "
                "страховочная копия текущих данных."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        entry = self._revalidate_action(token)
        if entry is None:
            return

        try:
            result = self.backup_service.restore_backup(
                entry.path,
                self.repository,
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка восстановления",
                str(exc),
            )
            return

        self.backup_restored.emit(result)
        self.refresh()

    def _delete_selected(self) -> None:
        entry = self.selected_entry
        if entry is None:
            return
        token = self._action_token(entry, "delete")

        external_text = "\n\nЭто внешний файл, добавленный вручную." if not entry.managed else ""
        answer = QMessageBox.warning(
            self,
            "Удалить резервную копию?",
            (f"Файл будет удалён без возможности восстановления:\n{entry.path}{external_text}"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        entry = self._revalidate_action(token)
        if entry is None:
            return

        try:
            deleted = self.catalog_service.delete_backup(
                entry.path,
                managed_directories=self.directories,
                allow_external=not entry.managed,
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка удаления",
                str(exc),
            )
            return

        self.external_files = [path for path in self.external_files if path != deleted]
        self.refresh()

    @staticmethod
    def _entry_row_id(entry: WorkflowBackupEntry) -> TableRowId:
        return TableRowId("backup", str(entry.path))

    @staticmethod
    def _entry_revision(entry: WorkflowBackupEntry) -> TableRevision:
        return TableRevision(
            f"{entry.modified_at.isoformat()}:{entry.size_bytes}:{int(entry.valid)}:"
            f"{entry.inspection.schema_version}"
        )

    @staticmethod
    def _entry_action_ids(entry: WorkflowBackupEntry) -> tuple[str, ...]:
        return ("verify", "delete", "restore") if entry.valid else ("verify", "delete")

    def _entry_snapshot(self, entry: WorkflowBackupEntry) -> TableSnapshot:
        revision = self._entry_revision(entry)
        return TableSnapshot(
            TableSurfaceId("TBL-150-003"),
            revision.value,
            TableState.READY,
            (TableColumn(TableColumnId("file"), "File", filterable=True),),
            (
                TableRow(
                    self._entry_row_id(entry),
                    revision,
                    (
                        TableCell(
                            entry.path.name,
                            sort_value=entry.path.name,
                            export_value=str(entry.path),
                            accessible_text=str(entry.path),
                        ),
                    ),
                    self._entry_action_ids(entry),
                ),
            ),
        )

    def _action_token(self, entry: WorkflowBackupEntry, action_id: str) -> TableActionToken:
        snapshot = self._entry_snapshot(entry)
        return TableActionToken(
            snapshot.surface_id,
            action_id,
            self._entry_row_id(entry),
            self._entry_revision(entry),
            snapshot.fingerprint,
        )

    def _revalidate_action(self, token: TableActionToken) -> WorkflowBackupEntry | None:
        try:
            current = self.catalog_service.refresh_entry(
                Path(token.row_id.value),
                managed_directories=self.directories,
            )
        except Exception:
            self.refresh()
            return None
        validation = validate_action_token(token, self._entry_snapshot(current))
        if not validation.allowed:
            self.refresh()
            return None
        return current

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)

        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {palette.app_background};
                color: {palette.text_primary};
            }}
            QLabel#BackupCenterTitle {{
                color: {palette.text_primary};
                {Typography.H2.css()}
            }}
            QLabel#BackupCenterSubtitle,
            QLabel#BackupCenterSummary,
            QLabel#BackupCenterDetailsText {{
                color: {palette.text_secondary};
                {Typography.BODY_S.css()}
            }}
            QFrame#BackupCenterDetails {{
                background-color: {palette.card_background};
                border: 1px solid {palette.border_subtle};
                border-radius: 9px;
            }}
            QLabel#BackupCenterDetailsTitle {{
                color: {palette.text_primary};
                {Typography.BUTTON.css()}
            }}
            QTableWidget#BackupCenterTable {{
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
            QPushButton:disabled {{
                color: {palette.text_muted};
            }}
            QPushButton#BackupCenterRestoreButton {{
                background-color: {palette.brand_primary};
                border-color: {palette.brand_primary};
                color: {palette.text_on_brand};
            }}
            QPushButton#BackupCenterDeleteButton {{
                color: {palette.danger};
                border-color: {palette.danger};
            }}
            """
        )

    @staticmethod
    def _size_text(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} Б"
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} КБ"
        return f"{size_bytes / 1024 / 1024:.1f} МБ"

    @staticmethod
    def _unique_paths(paths: list[Path]) -> list[Path]:
        result: list[Path] = []
        seen: set[str] = set()
        for path in paths:
            identity = str(path.expanduser().resolve(strict=False)).casefold()
            if identity in seen:
                continue
            seen.add(identity)
            result.append(path.expanduser())
        return result


__all__ = ["WorkflowBackupCenterDialog"]
