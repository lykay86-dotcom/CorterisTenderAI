"""Recovery dialog for a damaged business workflow database."""

from __future__ import annotations

from enum import StrEnum

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.workflow_database_health import (
    WorkflowDatabaseHealthReport,
)
from app.ui.theme.colors import ThemeName, get_palette
from app.ui.theme.typography import Typography


class WorkflowDatabaseRecoveryAction(StrEnum):
    CANCEL = "cancel"
    RESTORE_LATEST = "restore_latest"
    OPEN_BACKUP_CENTER = "open_backup_center"
    INITIALIZE_EMPTY = "initialize_empty"


class WorkflowDatabaseRecoveryDialog(QDialog):
    """Explain the diagnosis and let the user choose a safe action."""

    def __init__(
        self,
        report: WorkflowDatabaseHealthReport,
        *,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.report = report
        self.selected_action = WorkflowDatabaseRecoveryAction.CANCEL
        self._theme = ThemeName(theme)

        self.setWindowTitle("Диагностика базы бизнес-процессов")
        self.setModal(True)
        self.resize(720, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)

        title = QLabel(
            "Обнаружена проблема с базой бизнес-процессов",
            self,
        )
        title.setObjectName("DatabaseRecoveryTitle")
        title.setWordWrap(True)
        root.addWidget(title)

        subtitle = QLabel(
            (
                "Приложение не будет автоматически создавать "
                "резервную копию повреждённого файла. "
                "Выберите способ восстановления."
            ),
            self,
        )
        subtitle.setObjectName("DatabaseRecoverySubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        info = QFrame(self)
        info.setObjectName("DatabaseRecoveryInfo")
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(14, 12, 14, 12)
        info_layout.setSpacing(6)

        self.status_label = QLabel(
            f"Состояние: {report.status_label}",
            info,
        )
        self.status_label.setObjectName("DatabaseRecoveryStatus")
        info_layout.addWidget(self.status_label)

        self.path_label = QLabel(
            f"Файл: {report.path}",
            info,
        )
        self.path_label.setWordWrap(True)
        self.path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        info_layout.addWidget(self.path_label)

        details = QLabel(
            (
                f"Схема: {report.schema_version or 'не определена'} · "
                f"записей: {report.record_count} · "
                f"событий: {report.event_count}"
            ),
            info,
        )
        info_layout.addWidget(details)

        root.addWidget(info)

        issue_title = QLabel("Результат диагностики", self)
        issue_title.setObjectName("DatabaseRecoverySectionTitle")
        root.addWidget(issue_title)

        self.issues_label = QLabel(
            self._issues_text(report),
            self,
        )
        self.issues_label.setObjectName("DatabaseRecoveryIssues")
        self.issues_label.setWordWrap(True)
        self.issues_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        root.addWidget(self.issues_label)

        backup_title = QLabel(
            "Рекомендуемая резервная копия",
            self,
        )
        backup_title.setObjectName("DatabaseRecoverySectionTitle")
        root.addWidget(backup_title)

        self.backup_label = QLabel(
            self._backup_text(report),
            self,
        )
        self.backup_label.setObjectName("DatabaseRecoveryBackup")
        self.backup_label.setWordWrap(True)
        root.addWidget(self.backup_label)

        root.addStretch(1)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self.backup_center_button = QPushButton(
            "Открыть центр копий",
            self,
        )
        self.backup_center_button.clicked.connect(
            self._open_backup_center
        )

        self.empty_button = QPushButton(
            "Создать пустую базу",
            self,
        )
        self.empty_button.setObjectName(
            "DatabaseRecoveryEmptyButton"
        )
        self.empty_button.clicked.connect(
            self._initialize_empty
        )

        self.restore_button = QPushButton(
            "Восстановить последнюю копию",
            self,
        )
        self.restore_button.setObjectName(
            "DatabaseRecoveryRestoreButton"
        )
        self.restore_button.setEnabled(
            report.latest_valid_backup is not None
        )
        self.restore_button.clicked.connect(
            self._restore_latest
        )

        action_row.addWidget(self.backup_center_button)
        action_row.addWidget(self.empty_button)
        action_row.addStretch(1)
        action_row.addWidget(self.restore_button)
        root.addLayout(action_row)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.buttons.button(
            QDialogButtonBox.StandardButton.Cancel
        ).setText("Закрыть без изменений")
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        self.apply_theme(self._theme)

    def _restore_latest(self) -> None:
        self.selected_action = (
            WorkflowDatabaseRecoveryAction.RESTORE_LATEST
        )
        self.accept()

    def _open_backup_center(self) -> None:
        self.selected_action = (
            WorkflowDatabaseRecoveryAction.OPEN_BACKUP_CENTER
        )
        self.accept()

    def _initialize_empty(self) -> None:
        self.selected_action = (
            WorkflowDatabaseRecoveryAction.INITIALIZE_EMPTY
        )
        self.accept()

    @staticmethod
    def _issues_text(
        report: WorkflowDatabaseHealthReport,
    ) -> str:
        if not report.issues:
            return "Структурных ошибок не обнаружено."
        return "\n".join(
            f"• {issue.message}"
            for issue in report.issues
        )

    @staticmethod
    def _backup_text(
        report: WorkflowDatabaseHealthReport,
    ) -> str:
        entry = report.latest_valid_backup
        if entry is None:
            return (
                "Исправная резервная копия не найдена. "
                "Можно открыть Центр резервных копий и добавить "
                "внешний файл либо создать пустую базу."
            )

        return (
            f"{entry.path.name}\n"
            f"Дата: {entry.created_timestamp:%d.%m.%Y %H:%M:%S} · "
            f"записей: {entry.inspection.record_count} · "
            f"событий: {entry.inspection.event_count}\n"
            f"Путь: {entry.path}"
        )

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)

        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {palette.app_background};
                color: {palette.text_primary};
            }}
            QLabel#DatabaseRecoveryTitle {{
                color: {palette.text_primary};
                {Typography.H2.css()}
            }}
            QLabel#DatabaseRecoverySubtitle,
            QLabel#DatabaseRecoveryBackup {{
                color: {palette.text_secondary};
                {Typography.BODY_S.css()}
            }}
            QLabel#DatabaseRecoverySectionTitle {{
                color: {palette.text_secondary};
                {Typography.BUTTON.css()}
            }}
            QFrame#DatabaseRecoveryInfo {{
                background-color: {palette.danger_background};
                border: 1px solid {palette.danger};
                border-radius: 9px;
            }}
            QLabel#DatabaseRecoveryStatus {{
                color: {palette.danger};
                {Typography.BUTTON.css()}
            }}
            QLabel#DatabaseRecoveryIssues {{
                color: {palette.text_primary};
                background-color: {palette.card_background};
                border: 1px solid {palette.border_subtle};
                border-radius: 8px;
                padding: 10px;
                {Typography.BODY_S.css()}
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
                border-color: {palette.border_subtle};
            }}
            QPushButton#DatabaseRecoveryRestoreButton {{
                color: {palette.text_on_brand};
                background-color: {palette.brand_primary};
                border-color: {palette.brand_primary};
            }}
            QPushButton#DatabaseRecoveryEmptyButton {{
                color: {palette.danger};
                border-color: {palette.danger};
            }}
            """
        )


__all__ = [
    "WorkflowDatabaseRecoveryAction",
    "WorkflowDatabaseRecoveryDialog",
]
