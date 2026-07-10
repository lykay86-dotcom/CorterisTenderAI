from __future__ import annotations

import sys

from app.core.startup import initialize_core
from app.database.startup_pipeline import initialize_database_pipeline


def bootstrap() -> None:
    context = initialize_core()
    initialize_database_pipeline(
        context.paths.database_file,
        context.paths.backups_dir,
    )

    try:
        from PySide6.QtWidgets import QApplication
        from app.ui.main_window import MainWindow
    except ImportError as exc:
        raise SystemExit(
            "PySide6 не установлен. Выполните: pip install -r requirements.txt"
        ) from exc

    app = QApplication(sys.argv)
    app.setApplicationName("AIBOS Security")
    app.setApplicationVersion("1.2.1")
    window = MainWindow()
    window.show()
    raise SystemExit(app.exec())
