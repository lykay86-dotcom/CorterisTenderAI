"""PySide6 test for the C13 verification progress phase."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.tenders.collector.progress import (
    CollectorProgressEvent,
    CollectorProgressPhase,
)
from app.ui.tender_collector_dialog import TenderCollectorDialog


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_dialog_displays_verification_phase() -> None:
    app = _app()
    dialog = TenderCollectorDialog()

    dialog.apply_progress(
        CollectorProgressEvent(
            phase=CollectorProgressPhase.VERIFYING,
            raw_count=5,
            merged_count=4,
            duplicate_count=1,
            progress_percent=86,
            message=("Проверка критичных полей и происхождения данных…"),
        )
    )

    assert dialog.progress_bar.value() >= 86
    assert "происхождения" in dialog.status_label.text().casefold()
    app.processEvents()


def test_dialog_displays_freshness_phase() -> None:
    app = _app()
    dialog = TenderCollectorDialog()

    dialog.apply_progress(
        CollectorProgressEvent(
            phase=CollectorProgressPhase.CHECKING_FRESHNESS,
            raw_count=5,
            merged_count=4,
            duplicate_count=1,
            progress_percent=89,
            message="Нормализация сроков и расчёт повторной проверки…",
        )
    )

    assert dialog.progress_bar.value() >= 89
    assert "повторной проверки" in dialog.status_label.text().casefold()
    app.processEvents()
