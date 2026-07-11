"""Application bootstrap for Corteris Tender AI."""

from __future__ import annotations

import sys
from typing import Callable, Any

from app.core.crash_reporting import (
    CrashReportService,
    GlobalCrashHandler,
)
from app.core.startup import initialize_core
from app.database.startup_pipeline import initialize_database_pipeline


def _find_support_bundle_provider(
    window: object,
) -> Callable[[str], Any] | None:
    """Find a workflow page capable of creating a support bundle."""
    for attribute in ("quotes_page", "estimates_page"):
        page = getattr(window, attribute, None)
        provider = getattr(
            page,
            "create_diagnostic_support_bundle",
            None,
        )
        if callable(provider):
            return provider
    return None


def bootstrap() -> None:
    """Initialize infrastructure, crash capture and the Qt application."""
    context = initialize_core()

    crash_service = CrashReportService(
        context.paths.data_dir / "crash_reports",
        log_file=context.paths.log_dir / "app.log",
    )
    crash_handler = GlobalCrashHandler(crash_service)
    crash_handler.install()

    initialize_database_pipeline(
        context.paths.database_file,
        context.paths.backups_dir,
    )

    try:
        from PySide6.QtWidgets import QApplication
        from app.ui.crash_report_dialog import QtCrashBridge
        from app.ui.modern_main_window import ModernMainWindow
    except ImportError as exc:
        raise SystemExit(
            "PySide6 или UI-модули не установлены.\n"
            "Выполните: pip install -r requirements.txt"
        ) from exc

    application = QApplication(sys.argv)
    application.setOrganizationName("Corteris")
    application.setApplicationName("Corteris Tender AI")
    application.setApplicationVersion("1.5.1")

    crash_bridge = QtCrashBridge(
        crash_handler,
        parent=application,
    )

    try:
        window = ModernMainWindow()
    except Exception:
        report = crash_handler.capture_current(
            origin="startup_window",
            notify=False,
        )
        if report is not None:
            crash_bridge.show_report_now(report)
        crash_handler.uninstall()
        raise SystemExit(1)

    crash_bridge.set_parent_window(window)
    crash_bridge.set_support_bundle_provider(
        _find_support_bundle_provider(window)
    )

    window.show()
    exit_code = application.exec()

    crash_handler.uninstall()
    raise SystemExit(exit_code)


__all__ = [
    "_find_support_bundle_provider",
    "bootstrap",
]
