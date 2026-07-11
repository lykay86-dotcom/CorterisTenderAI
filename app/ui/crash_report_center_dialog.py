"""Interactive center for local CORTERIS crash reports."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.crash_report_catalog import (
    CrashReportCatalogService,
    CrashReportEntry,
)
from app.ui.theme.colors import ThemeName, get_palette
from app.ui.theme.typography import Typography


SupportBundleProvider = Callable[[str | Path], Any]


class CrashReportCenterDialog(QDialog):
    """List, inspect and safely manage automatically captured crashes."""

    COLUMNS = (
        "Дата",
        "Ошибка",
        "Источник",
        "Сообщение",
        "Размер",
        "Проверка",
    )

    def __init__(
        self,
        *,
        catalog_service: CrashReportCatalogService,
        directories: list[Path],
        support_bundle_provider: SupportBundleProvider | None = None,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.catalog_service = catalog_service
        self.directories = self._unique_paths(directories)
        self.support_bundle_provider = support_bundle_provider
        self.external_files: list[Path] = []
        self.entries: list[CrashReportEntry] = []
        self._theme = ThemeName(theme)

        self.setWindowTitle("Центр crash-reports")
        self.setModal(True)
        self.resize(1180, 760)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        title = QLabel("Центр crash-reports", self)
        title.setObjectName("CrashCenterTitle")
        root.addWidget(title)

        subtitle = QLabel(
            (
                "Просмотр автоматически сохранённых критических ошибок. "
                "Crash-report содержит очищенный traceback и техническое "
                "окружение, но не включает рабочую базу и документы."
            ),
            self,
        )
        subtitle.setObjectName("CrashCenterSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.refresh_button = QPushButton("Обновить", self)
        self.refresh_button.clicked.connect(self.refresh)

        self.add_button = QPushButton(
            "Добавить внешний файл…",
            self,
        )
        self.add_button.clicked.connect(self._add_external_report)

        self.open_folder_button = QPushButton(
            "Открыть папку",
            self,
        )
        self.open_folder_button.clicked.connect(
            self._open_selected_folder
        )
        self.open_folder_button.setEnabled(False)

        toolbar.addWidget(self.refresh_button)
        toolbar.addWidget(self.add_button)
        toolbar.addWidget(self.open_folder_button)
        toolbar.addStretch(1)

        self.summary_label = QLabel("", self)
        self.summary_label.setObjectName("CrashCenterSummary")
        toolbar.addWidget(self.summary_label)

        root.addLayout(toolbar)

        self.table = QTableWidget(0, len(self.COLUMNS), self)
        self.table.setObjectName("CrashCenterTable")
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.verticalHeader().hide()
        self.table.itemSelectionChanged.connect(
            self._selection_changed
        )

        header = self.table.horizontalHeader()
        for column in (0, 2, 4, 5):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )
        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Stretch,
        )
        root.addWidget(self.table, 1)

        details_frame = QFrame(self)
        details_frame.setObjectName("CrashCenterDetails")
        details_layout = QVBoxLayout(details_frame)
        details_layout.setContentsMargins(14, 12, 14, 12)
        details_layout.setSpacing(7)

        self.details_title = QLabel(
            "Выберите crash-report.",
            details_frame,
        )
        self.details_title.setObjectName("CrashCenterDetailsTitle")
        self.details_title.setWordWrap(True)
        details_layout.addWidget(self.details_title)

        self.details_label = QLabel("", details_frame)
        self.details_label.setObjectName("CrashCenterDetailsText")
        self.details_label.setWordWrap(True)
        self.details_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        details_layout.addWidget(self.details_label)

        self.traceback_edit = QTextEdit(details_frame)
        self.traceback_edit.setObjectName("CrashCenterTraceback")
        self.traceback_edit.setReadOnly(True)
        self.traceback_edit.setPlaceholderText(
            "Traceback выбранного отчёта"
        )
        self.traceback_edit.setMinimumHeight(170)
        details_layout.addWidget(self.traceback_edit)

        root.addWidget(details_frame)

        actions = QHBoxLayout()
        actions.setSpacing(8)

        self.verify_button = QPushButton(
            "Проверить повторно",
            self,
        )
        self.verify_button.clicked.connect(
            self._verify_selected
        )
        self.verify_button.setEnabled(False)

        self.copy_button = QPushButton(
            "Копировать детали",
            self,
        )
        self.copy_button.clicked.connect(
            self._copy_selected_details
        )
        self.copy_button.setEnabled(False)

        self.save_copy_button = QPushButton(
            "Сохранить копию…",
            self,
        )
        self.save_copy_button.clicked.connect(
            self._save_selected_copy
        )
        self.save_copy_button.setEnabled(False)

        self.support_button = QPushButton(
            "Пакет диагностики…",
            self,
        )
        self.support_button.setObjectName(
            "CrashCenterSupportButton"
        )
        self.support_button.setEnabled(
            support_bundle_provider is not None
        )
        self.support_button.clicked.connect(
            self._save_support_bundle
        )

        self.delete_button = QPushButton("Удалить", self)
        self.delete_button.setObjectName(
            "CrashCenterDeleteButton"
        )
        self.delete_button.clicked.connect(
            self._delete_selected
        )
        self.delete_button.setEnabled(False)

        actions.addWidget(self.verify_button)
        actions.addWidget(self.copy_button)
        actions.addWidget(self.save_copy_button)
        actions.addWidget(self.support_button)
        actions.addStretch(1)
        actions.addWidget(self.delete_button)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close,
            self,
        )
        self.buttons.button(
            QDialogButtonBox.StandardButton.Close
        ).setText("Закрыть")
        self.buttons.rejected.connect(self.reject)
        actions.addWidget(self.buttons)

        root.addLayout(actions)

        self.apply_theme(self._theme)
        self.refresh()

    @property
    def selected_entry(self) -> CrashReportEntry | None:
        row = self.table.currentRow()
        if 0 <= row < len(self.entries):
            return self.entries[row]
        return None

    def refresh(self) -> None:
        selected_path = (
            self.selected_entry.path
            if self.selected_entry is not None
            else None
        )
        try:
            self.entries = self.catalog_service.list_reports(
                self.directories,
                external_files=self.external_files,
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка чтения crash-reports",
                str(exc),
            )
            return

        self.table.setRowCount(len(self.entries))
        for row, entry in enumerate(self.entries):
            details = entry.details
            values = (
                entry.created_timestamp.strftime(
                    "%d.%m.%Y %H:%M:%S"
                ),
                (
                    details.exception_type
                    if details is not None
                    else "Не удалось прочитать"
                ),
                (
                    details.origin
                    if details is not None
                    else "—"
                ),
                (
                    details.exception_message
                    if details is not None
                    else self._first_error(entry)
                ),
                self._size_text(entry.size_bytes),
                "Исправен" if entry.valid else "Повреждён",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(str(entry.path))
                item.setTextAlignment(
                    (
                        Qt.AlignmentFlag.AlignRight
                        if column in {0, 4}
                        else Qt.AlignmentFlag.AlignLeft
                    )
                    | Qt.AlignmentFlag.AlignVCenter
                )
                self.table.setItem(row, column, item)

        valid_count = sum(1 for item in self.entries if item.valid)
        invalid_count = len(self.entries) - valid_count
        self.summary_label.setText(
            f"Всего: {len(self.entries)} · "
            f"исправных: {valid_count} · "
            f"повреждённых: {invalid_count}"
        )

        selected_row = -1
        if selected_path is not None:
            for row, entry in enumerate(self.entries):
                if entry.path == selected_path:
                    selected_row = row
                    break
        if selected_row < 0 and self.entries:
            selected_row = 0

        if selected_row >= 0:
            self.table.setCurrentCell(selected_row, 0)
            self.table.selectRow(selected_row)
        else:
            self._selection_changed()

    def _selection_changed(self) -> None:
        entry = self.selected_entry
        selected = entry is not None
        valid = bool(entry and entry.valid)

        self.verify_button.setEnabled(selected)
        self.open_folder_button.setEnabled(selected)
        self.copy_button.setEnabled(valid)
        self.save_copy_button.setEnabled(selected)
        self.delete_button.setEnabled(selected)

        if entry is None:
            self.details_title.setText(
                "Выберите crash-report."
            )
            self.details_label.clear()
            self.traceback_edit.clear()
            return

        self.details_title.setText(entry.path.name)
        details = entry.details
        if details is None:
            self.details_label.setText(
                "\n".join(
                    (
                        f"Путь: {entry.path}",
                        "Состояние: файл повреждён или несовместим",
                        "",
                        "Ошибки:",
                        *(
                            f"• {error}"
                            for error in entry.inspection.errors
                        ),
                    )
                )
            )
            self.traceback_edit.clear()
            return

        created = details.created_timestamp
        created_text = (
            created.strftime("%d.%m.%Y %H:%M:%S")
            if created is not None
            else details.created_at
        )
        self.details_label.setText(
            "\n".join(
                (
                    f"Crash ID: {details.crash_id}",
                    f"Дата: {created_text}",
                    f"Источник: {details.origin}",
                    f"Поток: {details.thread_name or '—'}",
                    f"Тип: {details.exception_type}",
                    f"Сообщение: {details.exception_message or '—'}",
                    f"Файл: {details.path}",
                    f"Размер: {self._size_text(details.size_bytes)}",
                )
            )
        )
        self.traceback_edit.setPlainText(
            details.traceback_text
        )

    def _verify_selected(self) -> None:
        entry = self.selected_entry
        if entry is None:
            return

        current_row = self.table.currentRow()
        try:
            refreshed = self.catalog_service.refresh_entry(
                entry.path,
                managed_directories=self.directories,
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка проверки crash-report",
                str(exc),
            )
            return

        self.entries[current_row] = refreshed
        self.refresh()

    def _add_external_report(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Добавить внешний crash-report",
            str(Path.home() / "Documents"),
            "Crash-report CORTERIS (*.ctcrash)",
        )
        if not filename:
            return

        path = Path(filename)
        if path not in self.external_files:
            self.external_files.append(path)
        self.refresh()

    def _open_selected_folder(self) -> None:
        entry = self.selected_entry
        if entry is None:
            return
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(entry.path.parent))
        )

    def _copy_selected_details(self) -> None:
        entry = self.selected_entry
        if entry is None or entry.details is None:
            return

        application = QApplication.instance()
        if application is None:
            return

        details = entry.details
        application.clipboard().setText(
            (
                f"{details.exception_type}: "
                f"{details.exception_message}\n"
                f"Crash ID: {details.crash_id}\n"
                f"Источник: {details.origin}\n"
                f"Файл: {details.path}\n\n"
                f"{details.traceback_text}"
            )
        )

    def _save_selected_copy(self) -> None:
        entry = self.selected_entry
        if entry is None:
            return

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить копию crash-report",
            str(Path.home() / "Documents" / entry.path.name),
            "Crash-report CORTERIS (*.ctcrash)",
        )
        if not filename:
            return

        try:
            target = self.catalog_service.copy_report(
                entry.path,
                filename,
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка сохранения crash-report",
                str(exc),
            )
            return

        QMessageBox.information(
            self,
            "Копия crash-report сохранена",
            f"Файл:\n{target}",
        )

    def _save_support_bundle(self) -> None:
        provider = self.support_bundle_provider
        if provider is None:
            return

        default_name = (
            "CORTERIS_diagnostic_support_"
            f"{datetime.now():%Y%m%d_%H%M%S}.ctsupport"
        )
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить пакет технической диагностики",
            str(Path.home() / "Documents" / default_name),
            (
                "Пакет диагностики CORTERIS (*.ctsupport);;"
                "ZIP-архив (*.zip)"
            ),
        )
        if not filename:
            return

        self.support_button.setEnabled(False)
        try:
            result = provider(filename)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка создания пакета диагностики",
                str(exc),
            )
        else:
            path = getattr(result, "path", filename)
            QMessageBox.information(
                self,
                "Пакет диагностики сохранён",
                f"Файл:\n{path}",
            )
        finally:
            self.support_button.setEnabled(True)

    def _delete_selected(self) -> None:
        entry = self.selected_entry
        if entry is None:
            return

        external_note = (
            "\n\nЭто внешний файл, добавленный вручную."
            if not entry.managed
            else ""
        )
        answer = QMessageBox.warning(
            self,
            "Удалить crash-report?",
            (
                "Файл будет удалён без возможности восстановления:\n"
                f"{entry.path}"
                f"{external_note}"
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            deleted = self.catalog_service.delete_report(
                entry.path,
                managed_directories=self.directories,
                allow_external=not entry.managed,
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка удаления crash-report",
                str(exc),
            )
            return

        self.external_files = [
            path
            for path in self.external_files
            if path != deleted
        ]
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
            QLabel#CrashCenterTitle {{
                color: {palette.text_primary};
                {Typography.H2.css()}
            }}
            QLabel#CrashCenterSubtitle,
            QLabel#CrashCenterSummary,
            QLabel#CrashCenterDetailsText {{
                color: {palette.text_secondary};
                {Typography.BODY_S.css()}
            }}
            QFrame#CrashCenterDetails {{
                background-color: {palette.card_background};
                border: 1px solid {palette.border_subtle};
                border-radius: 9px;
            }}
            QLabel#CrashCenterDetailsTitle {{
                color: {palette.text_primary};
                {Typography.BUTTON.css()}
            }}
            QTableWidget#CrashCenterTable {{
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
            QTextEdit#CrashCenterTraceback {{
                color: {palette.text_primary};
                background-color: {palette.input_background};
                border: 1px solid {palette.border_subtle};
                border-radius: 8px;
                padding: 8px;
                font-family: Consolas, "Courier New", monospace;
                font-size: 12px;
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
                color: {palette.text_disabled};
            }}
            QPushButton#CrashCenterSupportButton {{
                color: {palette.text_on_brand};
                background-color: {palette.brand_primary};
                border-color: {palette.brand_primary};
            }}
            QPushButton#CrashCenterDeleteButton {{
                color: {palette.danger};
                border-color: {palette.danger};
            }}
            """
        )

    @staticmethod
    def _first_error(entry: CrashReportEntry) -> str:
        if entry.inspection.errors:
            return entry.inspection.errors[0]
        return "Неизвестная ошибка чтения"

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
            identity = str(
                path.expanduser().resolve(strict=False)
            ).casefold()
            if identity in seen:
                continue
            seen.add(identity)
            result.append(path.expanduser())
        return result


__all__ = ["CrashReportCenterDialog"]
