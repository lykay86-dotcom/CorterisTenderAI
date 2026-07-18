"""Application bootstrap for Corteris Tender AI."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Any

from app.core.ai.provider_selection import (
    AiConfigStore,
    AiKeyringSecretStore,
    AiProviderResolution,
    AiProviderSelectionService,
    AiSecretStore,
    LegacyAiProviderSettings,
)
from app.core.launch_guard import LaunchGuardService
from app.core.crash_reporting import (
    CrashReportResult,
    CrashReportService,
    GlobalCrashHandler,
)
from app.core.startup import initialize_core
from app.config.user_settings import UserSettingsStore
from app.database.startup_pipeline import initialize_database_pipeline
from app.tenders.search_runtime import TenderSearchRuntime, create_tender_search_runtime


def _find_support_bundle_provider(
    window: object,
) -> Callable[[str | Path], Any] | None:
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


def _load_legacy_ai_settings(data_directory: str | Path) -> LegacyAiProviderSettings | None:
    """Read only non-secret legacy drafts; a damaged legacy file is ignored."""

    try:
        preferences = UserSettingsStore(Path(data_directory) / "user_settings.json").load()
    except Exception:
        return None
    return LegacyAiProviderSettings(
        provider_label=preferences.ai_provider,
        model=preferences.ai_model,
        base_url=preferences.ai_base_url,
    )


def _create_ai_runtime(
    data_directory: str | Path,
    config: AiConfigStore,
    *,
    secret_store: AiSecretStore | None = None,
    legacy_settings: LegacyAiProviderSettings | None = None,
) -> tuple[AiProviderSelectionService, TenderSearchRuntime, AiProviderResolution]:
    """Resolve an AI provider and inject it without running provider network code."""

    service = AiProviderSelectionService(
        config,
        secret_store if secret_store is not None else AiKeyringSecretStore(),
    )
    try:
        service.migrate_legacy_settings(legacy_settings)
    except Exception:
        # A write-protected legacy migration must not prevent safe startup.
        pass
    resolution = service.resolve_provider()
    runtime = create_tender_search_runtime(
        data_directory,
        ai_provider=resolution.provider,
    )
    return service, runtime, resolution


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

    ai_provider_selection_service, tender_search_runtime, ai_provider_resolution = (
        _create_ai_runtime(
            context.paths.data_dir,
            context.config,
            legacy_settings=_load_legacy_ai_settings(context.paths.data_dir),
        )
    )

    application = QApplication(sys.argv)
    application.setOrganizationName("Corteris")
    application.setApplicationName("Corteris Tender AI")
    application.setApplicationVersion("1.5.1")

    crash_bridge = QtCrashBridge(
        crash_handler,
        parent=application,
    )

    def handle_crash(report: CrashReportResult) -> None:
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
        window = ModernMainWindow(
            ai_provider_selection_service=ai_provider_selection_service,
        )
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
        runtime=tender_search_runtime,
        theme=getattr(window, "_theme", "dark") or "dark",
        parent=window,
    )
    tender_search_controller.install_on_main_window(window)
    tender_search_controller.install_on_tender_workspace(window.tender_workspace_page)

    if ai_provider_resolution.warnings:
        window.statusBar().showMessage(ai_provider_resolution.warnings[0], 8000)

    window.show()
    exit_code = application.exec()

    tender_search_controller.shutdown()

    launch_guard.mark_clean_exit(details=f"Qt exit code: {exit_code}")
    crash_handler.uninstall()
    raise SystemExit(exit_code)


__all__ = [
    "_find_support_bundle_provider",
    "_create_ai_runtime",
    "_load_legacy_ai_settings",
    "bootstrap",
]
