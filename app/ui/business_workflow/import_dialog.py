"""Preview dialog for validated workflow Excel import."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.reporting.workflow_excel_import import (
    WorkflowImportPreview,
    WorkflowImportRow,
)
from app.ui.theme.colors import ThemeName, get_palette
from app.ui.theme.typography import Typography


class WorkflowImportPreviewDialog(QDialog):
    """Show row-level validation before changing local data."""

    def __init__(
        self,
        preview: WorkflowImportPreview,
        *,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.preview = preview
        self._theme = ThemeName(theme)

        self.setWindowTitle("Предварительная проверка импорта")
        self.setModal(True)
        self.resize(1180, 700)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        title = QLabel("Импорт КП, смет и проектов", self)
        title.setObjectName("WorkflowImportTitle")
        root.addWidget(title)

        self.summary_label = QLabel(
            self._summary_text(),
            self,
        )
        self.summary_label.setObjectName("WorkflowImportSummary")
        self.summary_label.setWordWrap(True)
        root.addWidget(self.summary_label)

        self.fatal_label = QLabel(
            self._fatal_text(),
            self,
        )
        self.fatal_label.setObjectName("WorkflowImportFatal")
        self.fatal_label.setWordWrap(True)
        self.fatal_label.setVisible(bool(preview.fatal_issues))
        root.addWidget(self.fatal_label)

        self.table = QTableWidget(len(preview.rows), 8, self)
        self.table.setObjectName("WorkflowImportTable")
        self.table.setHorizontalHeaderLabels(
            (
                "Строка",
                "Проверка",
                "Тип",
                "Тендер",
                "Наименование",
                "Статус",
                "Сумма",
                "Комментарии",
            )
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
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
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            4,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            5,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            6,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            7,
            QHeaderView.ResizeMode.Stretch,
        )

        for table_row, row in enumerate(preview.rows):
            self._populate_row(table_row, row)
            self.table.resizeRowToContents(table_row)

        root.addWidget(self.table, 1)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.import_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.import_button.setText(f"Импортировать {len(preview.valid_rows)}")
        self.import_button.setEnabled(preview.can_import)
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        self.apply_theme(self._theme)

    def _populate_row(
        self,
        table_row: int,
        row: WorkflowImportRow,
    ) -> None:
        if not row.is_valid:
            check = "Ошибка"
        elif row.has_warnings:
            check = "Предупреждение"
        else:
            check = "Готово"

        values = (
            str(row.source_row),
            check,
            row.kind.value if row.kind is not None else "—",
            row.tender_id or "—",
            row.title or "—",
            row.status.value if row.status is not None else "—",
            self._money(row.total),
            self._issues_text(row),
        )

        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            alignment = Qt.AlignmentFlag.AlignTop | (
                Qt.AlignmentFlag.AlignRight if column in {0, 6} else Qt.AlignmentFlag.AlignLeft
            )
            item.setTextAlignment(alignment)
            self.table.setItem(table_row, column, item)

    def _summary_text(self) -> str:
        return (
            f"Файл: {self.preview.path.name} · "
            f"лист: {self.preview.sheet_name or 'не определён'} · "
            f"строк: {len(self.preview.rows)} · "
            f"готовы: {len(self.preview.valid_rows)} · "
            f"с предупреждениями: "
            f"{len(self.preview.warning_rows)} · "
            f"ошибок: {len(self.preview.invalid_rows)}"
        )

    def _fatal_text(self) -> str:
        return "\n".join(f"• {issue.message}" for issue in self.preview.fatal_issues)

    @staticmethod
    def _issues_text(row: WorkflowImportRow) -> str:
        if not row.issues:
            return "Проверка пройдена"
        return "\n".join(f"• {issue.message}" for issue in row.issues)

    @staticmethod
    def _money(value: Decimal) -> str:
        return f"{value:,.2f} ₽".replace(",", " ")

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)

        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {palette.app_background};
                color: {palette.text_primary};
            }}
            QLabel#WorkflowImportTitle {{
                color: {palette.text_primary};
                {Typography.H2.css()}
            }}
            QLabel#WorkflowImportSummary {{
                color: {palette.text_secondary};
                {Typography.BODY_S.css()}
            }}
            QLabel#WorkflowImportFatal {{
                color: {palette.danger};
                background-color: {palette.input_background};
                border: 1px solid {palette.danger};
                border-radius: 8px;
                padding: 10px;
                {Typography.BODY_S.css()}
            }}
            QTableWidget#WorkflowImportTable {{
                color: {palette.text_primary};
                background-color: {palette.card_background};
                alternate-background-color: {palette.panel_background};
                gridline-color: {palette.border_subtle};
                border: 1px solid {palette.border_subtle};
                border-radius: 9px;
                selection-background-color: {palette.selected_background};
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
            QDialogButtonBox QPushButton {{
                min-height: 34px;
                padding: 4px 14px;
            }}
            """
        )


__all__ = ["WorkflowImportPreviewDialog"]
