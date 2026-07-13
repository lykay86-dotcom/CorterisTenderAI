"""Qt presentation layer for automatically captured crash reports."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Any

from PySide6.QtCore import QObject, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.crash_reporting import (
    CrashReportResult,
    GlobalCrashHandler,
)
from app.ui.theme.colors import ThemeName, get_palette
from app.ui.theme.typography import Typography


SupportBundleProvider = Callable[[str | Path], Any]


class CrashReportDialog(QDialog):
    """Explain the crash and offer local recovery/support actions."""

    def __init__(
        self,
        report: CrashReportResult,
        *,
        support_bundle_provider: (SupportBundleProvider | None) = None,
        theme: ThemeName | str = ThemeName.DARK,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.report = report
        self.support_bundle_provider = support_bundle_provider
        self._theme = ThemeName(theme)

        self.setWindowTitle("Corteris Tender AI — критическая ошибка")
        self.setModal(True)
        self.resize(820, 650)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)

        title = QLabel(
            "Произошла непредвиденная ошибка",
            self,
        )
        title.setObjectName("CrashReportTitle")
        title.setWordWrap(True)
        root.addWidget(title)

        subtitle = QLabel(
            (
                "Crash-report уже сохранён автоматически. "
                "Рабочая база и документы в него не включаются. "
                "Перед продолжением рекомендуется сохранить пакет "
                "диагностики и перезапустить приложение."
            ),
            self,
        )
        subtitle.setObjectName("CrashReportSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        info = QFrame(self)
        info.setObjectName("CrashReportInfo")
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(14, 12, 14, 12)
        info_layout.setSpacing(6)

        self.error_label = QLabel(
            (f"{report.exception_type}: {report.exception_message or 'без сообщения'}"),
            info,
        )
        self.error_label.setObjectName("CrashReportError")
        self.error_label.setWordWrap(True)
        self.error_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        info_layout.addWidget(self.error_label)

        self.path_label = QLabel(
            f"Crash-report: {report.path}",
            info,
        )
        self.path_label.setObjectName("CrashReportPath")
        self.path_label.setWordWrap(True)
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        info_layout.addWidget(self.path_label)

        root.addWidget(info)

        details_title = QLabel(
            "Технические подробности",
            self,
        )
        details_title.setObjectName("CrashReportSectionTitle")
        root.addWidget(details_title)

        self.details = QTextEdit(self)
        self.details.setObjectName("CrashReportDetails")
        self.details.setReadOnly(True)
        self.details.setPlainText(report.traceback_text)
        root.addWidget(self.details, 1)

        actions = QHBoxLayout()
        actions.setSpacing(8)

        self.copy_button = QPushButton(
            "Копировать детали",
            self,
        )
        self.copy_button.clicked.connect(self._copy_details)

        self.open_folder_button = QPushButton(
            "Открыть папку отчёта",
            self,
        )
        self.open_folder_button.clicked.connect(self._open_report_folder)

        self.save_bundle_button = QPushButton(
            "Сохранить пакет диагностики…",
            self,
        )
        self.save_bundle_button.setObjectName("CrashReportBundleButton")
        self.save_bundle_button.setEnabled(support_bundle_provider is not None)
        self.save_bundle_button.clicked.connect(self._save_support_bundle)

        actions.addWidget(self.copy_button)
        actions.addWidget(self.open_folder_button)
        actions.addStretch(1)
        actions.addWidget(self.save_bundle_button)
        root.addLayout(actions)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close,
            self,
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Close).setText("Закрыть")
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        self.apply_theme(self._theme)

    def _copy_details(self) -> None:
        application = QApplication.instance()
        if application is None:
            return
        application.clipboard().setText(
            (f"{self.error_label.text()}\n{self.path_label.text()}\n\n{self.report.traceback_text}")
        )

    def _open_report_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.report.path.parent)))

    def _save_support_bundle(self) -> None:
        provider = self.support_bundle_provider
        if provider is None:
            return

        default_name = (
            "CORTERIS_diagnostic_after_crash_"
            f"{self.report.created_at.replace(':', '').replace('-', '')}"
            ".ctsupport"
        )
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить пакет технической диагностики",
            str(Path.home() / "Documents" / default_name),
            ("Пакет диагностики CORTERIS (*.ctsupport);;ZIP-архив (*.zip)"),
        )
        if not filename:
            return

        self.save_bundle_button.setEnabled(False)
        try:
            result = provider(filename)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка создания пакета диагностики",
                str(exc),
            )
        else:
            result_path = getattr(result, "path", filename)
            QMessageBox.information(
                self,
                "Пакет диагностики сохранён",
                f"Файл:\n{result_path}",
            )
        finally:
            self.save_bundle_button.setEnabled(True)

    def apply_theme(self, theme: ThemeName | str) -> None:
        self._theme = ThemeName(theme)
        palette = get_palette(self._theme)

        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {palette.app_background};
                color: {palette.text_primary};
            }}
            QLabel#CrashReportTitle {{
                color: {palette.danger};
                {Typography.H2.css()}
            }}
            QLabel#CrashReportSubtitle,
            QLabel#CrashReportPath {{
                color: {palette.text_secondary};
                {Typography.BODY_S.css()}
            }}
            QLabel#CrashReportSectionTitle {{
                color: {palette.text_secondary};
                {Typography.BUTTON.css()}
            }}
            QFrame#CrashReportInfo {{
                background-color: {palette.danger_background};
                border: 1px solid {palette.danger};
                border-radius: 9px;
            }}
            QLabel#CrashReportError {{
                color: {palette.danger};
                {Typography.BUTTON.css()}
            }}
            QTextEdit#CrashReportDetails {{
                color: {palette.text_primary};
                background-color: {palette.card_background};
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
            QPushButton#CrashReportBundleButton {{
                color: {palette.text_on_brand};
                background-color: {palette.brand_primary};
                border-color: {palette.brand_primary};
            }}
            """
        )


class QtCrashBridge(QObject):
    """Thread-safe bridge between pure-Python hooks and the Qt UI."""

    report_requested = Signal(object)

    def __init__(
        self,
        handler: GlobalCrashHandler,
        *,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self.handler = handler
        self.parent_window: QWidget | None = None
        self.support_bundle_provider: SupportBundleProvider | None = None
        self._dialog_open = False

        self.report_requested.connect(
            self._show_report,
            Qt.ConnectionType.QueuedConnection,
        )
        self.handler.set_report_callback(self.notify)

    def set_parent_window(
        self,
        window: QWidget | None,
    ) -> None:
        self.parent_window = window

    def set_support_bundle_provider(
        self,
        provider: SupportBundleProvider | None,
    ) -> None:
        self.support_bundle_provider = provider

    def notify(self, report: CrashReportResult) -> None:
        self.report_requested.emit(report)

    def show_report_now(
        self,
        report: CrashReportResult,
    ) -> None:
        self._show_report(report)

    @Slot(object)
    def _show_report(self, report: CrashReportResult) -> None:
        if self._dialog_open:
            return

        application = QApplication.instance()
        if application is None:
            return

        self._dialog_open = True
        try:
            parent = self.parent_window
            theme = getattr(
                parent,
                "_theme",
                ThemeName.DARK,
            )
            dialog = CrashReportDialog(
                report,
                support_bundle_provider=(self.support_bundle_provider),
                theme=theme,
                parent=parent,
            )
            dialog.exec()
        finally:
            self._dialog_open = False


__all__ = [
    "CrashReportDialog",
    "QtCrashBridge",
    "SupportBundleProvider",
]
