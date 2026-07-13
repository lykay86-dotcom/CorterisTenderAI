"""Application bootstrap for Corteris Tender AI."""

from __future__ import annotations

import sys
from typing import Callable, Any

from app.core.launch_guard import LaunchGuardService
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

    if "--self-test" in sys.argv:
        from app.core.frozen_self_test import (
            run_frozen_self_test_from_argv,
        )

        raise SystemExit(
            run_frozen_self_test_from_argv(
                context,
                sys.argv[1:],
            )
        )

    launch_guard = LaunchGuardService(context.paths.data_dir / "launch_history.json")
    force_safe_mode = "--safe-mode" in sys.argv
    safe_mode_decision = launch_guard.evaluate(force_safe_mode=force_safe_mode)
    launch_guard.begin_launch()

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
        from app.ui.safe_mode_dialog import SafeModeDialog
        from app.ui.tender_search_ui_controller import (
            TenderSearchUiController,
        )
        from app.ui.modern_main_window import ModernMainWindow
    except ImportError as exc:
        raise SystemExit(
            "PySide6 или UI-модули не установлены.\nВыполните: pip install -r requirements.txt"
        ) from exc

    application = QApplication(sys.argv)
    application.setOrganizationName("Corteris")
    application.setApplicationName("Corteris Tender AI")
    application.setApplicationVersion("1.5.1")

    crash_bridge = QtCrashBridge(
        crash_handler,
        parent=application,
    )

    def handle_crash(report) -> None:
        launch_guard.mark_crash(
            crash_report=report.path,
            details=(f"{report.exception_type}: {report.exception_message}"),
        )
        crash_bridge.notify(report)

    crash_handler.set_report_callback(handle_crash)

    if safe_mode_decision.enabled:
        safe_dialog = SafeModeDialog(
            decision=safe_mode_decision,
            launch_guard=launch_guard,
            data_directory=context.paths.data_dir,
            database_file=context.paths.database_file,
            backups_directory=context.paths.backups_dir,
            crash_reports_directory=(context.paths.data_dir / "crash_reports"),
        )
        safe_result = safe_dialog.exec()
        if safe_result != SafeModeDialog.NORMAL_EXIT_CODE:
            launch_guard.mark_safe_mode_exit(details="Пользователь завершил безопасный режим.")
            crash_handler.uninstall()
            raise SystemExit(0)

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
    crash_bridge.set_support_bundle_provider(_find_support_bundle_provider(window))

    tender_search_controller = TenderSearchUiController(
        context.paths.data_dir,
        theme=getattr(window, "_theme", "dark") or "dark",
        parent=window,
    )
    tender_search_controller.install_on_main_window(window)

    window.show()
    exit_code = application.exec()

    launch_guard.mark_clean_exit(details=f"Qt exit code: {exit_code}")
    crash_handler.uninstall()
    raise SystemExit(exit_code)


__all__ = [
    "_find_support_bundle_provider",
    "bootstrap",
]
