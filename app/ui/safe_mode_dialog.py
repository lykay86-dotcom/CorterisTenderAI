"""Safe-mode recovery dialog shown after repeated critical failures."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
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

from app.core.launch_guard import (
    LaunchGuardService,
    SafeModeDecision,
)
from app.ui.theme.colors import ThemeName, get_palette
from app.ui.theme.typography import Typography


@dataclass(frozen=True, slots=True)
class SafeModeSystemCheck:
    label: str
    status: str
    details: str


class SafeModeDialog(QDialog):
    """Minimal recovery UI that does not construct the main application."""

    NORMAL_EXIT_CODE = 101
    SAFE_EXIT_CODE = 0

    def __init__(
        self,
        *,
        decision: SafeModeDecision,
        launch_guard: LaunchGuardService,
        data_directory: str | Path,
        database_file: str | Path,
        backups_directory: str | Path,
        crash_reports_directory: str | Path,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.decision = decision
        self.launch_guard = launch_guard
        self.data_directory = Path(data_directory)
        self.database_file = Path(database_file)
        self.backups_directory = Path(backups_directory)
        self.crash_reports_directory = Path(
            crash_reports_directory
        )
        self._theme = ThemeName(theme)

        self.setWindowTitle(
            "Corteris Tender AI — безопасный режим"
        )
        self.setModal(True)
        self.resize(780, 610)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)

        title = QLabel("Безопасный режим", self)
        title.setObjectName("SafeModeTitle")
        root.addWidget(title)

        subtitle = QLabel(
            (
                f"{decision.reason}\n"
                "Основное окно и фоновые задачи не запущены. "
                "Можно проверить окружение, открыть отчёты, "
                "сбросить историю сбоев или продолжить обычный запуск."
            ),
            self,
        )
        subtitle.setObjectName("SafeModeSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        checks_frame = QFrame(self)
        checks_frame.setObjectName("SafeModeChecks")
        checks_layout = QVBoxLayout(checks_frame)
        checks_layout.setContentsMargins(14, 12, 14, 12)
        checks_layout.setSpacing(8)

        section = QLabel("Самодиагностика", checks_frame)
        section.setObjectName("SafeModeSection")
        checks_layout.addWidget(section)

        for check in self._run_checks():
            label = QLabel(
                f"{check.status}  {check.label}\n{check.details}",
                checks_frame,
            )
            label.setObjectName("SafeModeCheck")
            label.setWordWrap(True)
            label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            checks_layout.addWidget(label)

        root.addWidget(checks_frame)

        history = QLabel(
            self._history_text(),
            self,
        )
        history.setObjectName("SafeModeHistory")
        history.setWordWrap(True)
        history.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        root.addWidget(history)

        root.addStretch(1)

        actions = QHBoxLayout()
        actions.setSpacing(8)

        self.crash_reports_button = QPushButton(
            "Открыть crash-reports",
            self,
        )
        self.crash_reports_button.clicked.connect(
            self._open_crash_reports
        )

        self.backups_button = QPushButton(
            "Открыть резервные копии",
            self,
        )
        self.backups_button.clicked.connect(
            self._open_backups
        )

        self.reset_button = QPushButton(
            "Сбросить историю сбоев",
            self,
        )
        self.reset_button.setObjectName("SafeModeResetButton")
        self.reset_button.clicked.connect(
            self._reset_history
        )

        self.normal_button = QPushButton(
            "Продолжить обычный запуск",
            self,
        )
        self.normal_button.setObjectName("SafeModeNormalButton")
        self.normal_button.clicked.connect(
            lambda: self.done(self.NORMAL_EXIT_CODE)
        )

        actions.addWidget(self.crash_reports_button)
        actions.addWidget(self.backups_button)
        actions.addWidget(self.reset_button)
        actions.addStretch(1)
        actions.addWidget(self.normal_button)
        root.addLayout(actions)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close,
            self,
        )
        self.buttons.button(
            QDialogButtonBox.StandardButton.Close
        ).setText("Закрыть приложение")
        self.buttons.rejected.connect(
            lambda: self.done(self.SAFE_EXIT_CODE)
        )
        root.addWidget(self.buttons)

        self.apply_theme(self._theme)

    def _run_checks(self) -> tuple[SafeModeSystemCheck, ...]:
        checks: list[SafeModeSystemCheck] = []

        checks.append(
            SafeModeSystemCheck(
                "Папка данных",
                "✅" if self.data_directory.is_dir() else "❌",
                str(self.data_directory),
            )
        )

        if self.database_file.is_file():
            try:
                size = self.database_file.stat().st_size
                database_status = "✅"
                database_details = (
                    f"{self.database_file} · {size / 1024:.1f} КБ"
                )
            except OSError as exc:
                database_status = "❌"
                database_details = str(exc)
        else:
            database_status = "⚠"
            database_details = (
                f"{self.database_file} — файл ещё не создан"
            )
        checks.append(
            SafeModeSystemCheck(
                "Файл базы",
                database_status,
                database_details,
            )
        )

        backup_count = self._count_files(
            self.backups_directory,
            {".ctbackup"},
        )
        checks.append(
            SafeModeSystemCheck(
                "Резервные копии",
                "✅" if backup_count else "⚠",
                (
                    f"{self.backups_directory} · "
                    f"найдено: {backup_count}"
                ),
            )
        )

        crash_count = self._count_files(
            self.crash_reports_directory,
            {".ctcrash"},
        )
        checks.append(
            SafeModeSystemCheck(
                "Crash-reports",
                "⚠" if crash_count else "✅",
                (
                    f"{self.crash_reports_directory} · "
                    f"найдено: {crash_count}"
                ),
            )
        )

        try:
            usage = shutil.disk_usage(self.data_directory)
            free_gb = usage.free / 1024 / 1024 / 1024
            disk_status = "✅" if free_gb >= 1 else "⚠"
            disk_details = f"Свободно: {free_gb:.2f} ГБ"
        except OSError as exc:
            disk_status = "❌"
            disk_details = str(exc)
        checks.append(
            SafeModeSystemCheck(
                "Свободное место",
                disk_status,
                disk_details,
            )
        )

        return tuple(checks)

    def _history_text(self) -> str:
        lines = [
            (
                f"Последние аварийные запуски: "
                f"{self.decision.recent_crashes} из "
                f"{self.decision.threshold}"
            ),
            "",
            "История:",
        ]
        for record in self.decision.records[:5]:
            lines.append(
                f"• {record.started_at} — {record.outcome}"
            )
        return "\n".join(lines)

    def _open_crash_reports(self) -> None:
        self.crash_reports_directory.mkdir(
            parents=True,
            exist_ok=True,
        )
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(
                str(self.crash_reports_directory)
            )
        )

    def _open_backups(self) -> None:
        self.backups_directory.mkdir(
            parents=True,
            exist_ok=True,
        )
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(self.backups_directory))
        )

    def _reset_history(self) -> None:
        self.launch_guard.reset_history()
        self.reset_button.setEnabled(False)
        self.reset_button.setText("История сброшена")

    @staticmethod
    def _count_files(
        directory: Path,
        suffixes: set[str],
    ) -> int:
        if not directory.is_dir():
            return 0
        try:
            return sum(
                1
                for path in directory.iterdir()
                if path.is_file()
                and path.suffix.lower() in suffixes
            )
        except OSError:
            return 0

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)

        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {palette.app_background};
                color: {palette.text_primary};
            }}
            QLabel#SafeModeTitle {{
                color: {palette.warning};
                {Typography.H2.css()}
            }}
            QLabel#SafeModeSubtitle,
            QLabel#SafeModeHistory,
            QLabel#SafeModeCheck {{
                color: {palette.text_secondary};
                {Typography.BODY_S.css()}
            }}
            QLabel#SafeModeSection {{
                color: {palette.text_primary};
                {Typography.BUTTON.css()}
            }}
            QFrame#SafeModeChecks {{
                background-color: {palette.card_background};
                border: 1px solid {palette.warning};
                border-radius: 9px;
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
            QPushButton#SafeModeNormalButton {{
                color: {palette.text_on_brand};
                background-color: {palette.brand_primary};
                border-color: {palette.brand_primary};
            }}
            QPushButton#SafeModeResetButton {{
                color: {palette.warning};
                border-color: {palette.warning};
            }}
            """
        )


__all__ = [
    "SafeModeDialog",
    "SafeModeSystemCheck",
]
