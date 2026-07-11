"""Settings dialog for scheduled workflow backups."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.workflow_auto_backup import (
    WorkflowAutoBackupService,
    WorkflowAutoBackupSettings,
)
from app.ui.theme.colors import ThemeName, get_palette
from app.ui.theme.typography import Typography


class WorkflowBackupSettingsDialog(QDialog):
    """Edit automatic backup schedule without touching stored data."""

    INTERVALS = (
        ("Каждый час", 1),
        ("Каждые 3 часа", 3),
        ("Каждые 6 часов", 6),
        ("Каждые 12 часов", 12),
        ("Каждые сутки", 24),
        ("Каждые 3 дня", 72),
        ("Раз в неделю", 168),
    )

    def __init__(
        self,
        settings: WorkflowAutoBackupSettings,
        *,
        default_directory: str | Path,
        auto_backup_service: WorkflowAutoBackupService,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._theme = ThemeName(theme)
        self._service = auto_backup_service
        self._default_directory = Path(default_directory)

        self.setWindowTitle("Автоматическое резервное копирование")
        self.setModal(True)
        self.setMinimumWidth(610)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(16)

        title = QLabel("Автоматические резервные копии", self)
        title.setObjectName("AutoBackupTitle")
        root.addWidget(title)

        subtitle = QLabel(
            "Приложение проверяет расписание при запуске и затем "
            "каждые 15 минут. Хранятся только автоматические копии; "
            "ручные и страховочные файлы не удаляются.",
            self,
        )
        subtitle.setObjectName("AutoBackupSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        self.enabled_check = QCheckBox(
            "Включить автоматическое резервное копирование",
            self,
        )
        self.enabled_check.setChecked(settings.enabled)
        self.enabled_check.toggled.connect(
            self._sync_enabled_state
        )
        root.addWidget(self.enabled_check)

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(13)
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter
        )

        self.interval_combo = QComboBox(self)
        for label, hours in self.INTERVALS:
            self.interval_combo.addItem(label, hours)
        index = self.interval_combo.findData(settings.interval_hours)
        if index < 0:
            self.interval_combo.addItem(
                f"Каждые {settings.interval_hours} ч.",
                settings.interval_hours,
            )
            index = self.interval_combo.count() - 1
        self.interval_combo.setCurrentIndex(index)
        form.addRow("Периодичность", self.interval_combo)

        self.retention_spin = QSpinBox(self)
        self.retention_spin.setRange(
            WorkflowAutoBackupService.MIN_RETENTION,
            WorkflowAutoBackupService.MAX_RETENTION,
        )
        self.retention_spin.setValue(settings.retention_count)
        self.retention_spin.setSuffix(" копий")
        form.addRow("Хранить последние", self.retention_spin)

        directory_row = QHBoxLayout()
        directory_row.setSpacing(8)
        self.directory_edit = QLineEdit(self)
        self.directory_edit.setText(settings.directory)
        self.directory_edit.setPlaceholderText(
            str(self._default_directory)
        )
        self.browse_button = QPushButton("Выбрать…", self)
        self.browse_button.clicked.connect(self._browse_directory)
        directory_row.addWidget(self.directory_edit, 1)
        directory_row.addWidget(self.browse_button)
        form.addRow("Папка", directory_row)

        root.addLayout(form)

        self.status_label = QLabel(
            self._status_text(settings),
            self,
        )
        self.status_label.setObjectName("AutoBackupStatus")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.buttons.button(
            QDialogButtonBox.StandardButton.Save
        ).setText("Сохранить")
        self.buttons.button(
            QDialogButtonBox.StandardButton.Cancel
        ).setText("Отмена")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        self._sync_enabled_state(settings.enabled)
        self.apply_theme(self._theme)

    def settings(self) -> WorkflowAutoBackupSettings:
        return WorkflowAutoBackupSettings(
            enabled=self.enabled_check.isChecked(),
            interval_hours=int(
                self.interval_combo.currentData() or 24
            ),
            retention_count=self.retention_spin.value(),
            directory=self.directory_edit.text().strip(),
        )

    def _browse_directory(self) -> None:
        initial = (
            self.directory_edit.text().strip()
            or str(self._default_directory)
        )
        selected = QFileDialog.getExistingDirectory(
            self,
            "Папка автоматических резервных копий",
            initial,
        )
        if selected:
            self.directory_edit.setText(selected)

    def _sync_enabled_state(self, enabled: bool) -> None:
        self.interval_combo.setEnabled(enabled)
        self.retention_spin.setEnabled(enabled)
        self.directory_edit.setEnabled(enabled)
        self.browse_button.setEnabled(enabled)

    def _status_text(
        self,
        settings: WorkflowAutoBackupSettings,
    ) -> str:
        parts: list[str] = []
        if settings.last_success_timestamp is not None:
            parts.append(
                "Последняя успешная копия: "
                + settings.last_success_timestamp.strftime(
                    "%d.%m.%Y %H:%M:%S"
                )
            )
        else:
            parts.append("Успешные автоматические копии ещё не создавались.")

        next_run = self._service.next_run_at(settings)
        if next_run is not None:
            parts.append(
                "Следующая проверка по расписанию: "
                + next_run.strftime("%d.%m.%Y %H:%M:%S")
            )
        if settings.last_error:
            parts.append("Последняя ошибка: " + settings.last_error)
        return "\n".join(parts)

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)
        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {palette.app_background};
                color: {palette.text_primary};
            }}
            QLabel#AutoBackupTitle {{
                color: {palette.text_primary};
                {Typography.H2.css()}
            }}
            QLabel#AutoBackupSubtitle,
            QLabel#AutoBackupStatus {{
                color: {palette.text_secondary};
                {Typography.BODY_S.css()}
            }}
            QCheckBox {{
                color: {palette.text_primary};
                spacing: 8px;
                {Typography.BODY_M.css()}
            }}
            QLineEdit, QComboBox, QSpinBox {{
                min-height: 34px;
                color: {palette.text_primary};
                background-color: {palette.input_background};
                border: 1px solid {palette.border_default};
                border-radius: 7px;
                padding: 4px 8px;
                {Typography.BODY_S.css()}
            }}
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
                border: 2px solid {palette.focus_ring};
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
            """
        )


__all__ = ["WorkflowBackupSettingsDialog"]
