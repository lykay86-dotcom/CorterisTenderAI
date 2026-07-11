"""Application bootstrap for Corteris Tender AI."""

from __future__ import annotations

import sys

from app.core.startup import initialize_core
from app.database.startup_pipeline import initialize_database_pipeline


def bootstrap() -> None:
    """Initialize infrastructure and start the Qt application."""
    context = initialize_core()
    initialize_database_pipeline(
        context.paths.database_file,
        context.paths.backups_dir,
    )

    try:
        from PySide6.QtWidgets import QApplication
        from app.ui.modern_main_window import ModernMainWindow
    except ImportError as exc:
        raise SystemExit(
            "PySide6 или UI-модули не установлены.\n"
            "Выполните: pip install -r requirements.txt"
        ) from exc

    application = QApplication(sys.argv)
    application.setOrganizationName("Corteris")
    application.setApplicationName("Corteris Tender AI")
    application.setApplicationVersion("1.3.0-alpha")

    window = ModernMainWindow()
    window.show()

    raise SystemExit(application.exec())


__all__ = ["bootstrap"]
