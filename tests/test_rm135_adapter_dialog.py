"""RM-135 canonical provider-manager wizard surface."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton

from app.ui.tender_provider_manager_dialog import (
    ManualAdapterWizardDialog,
    TenderProviderManagerDialog,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_manager_exposes_adapter_action_and_wizard_has_no_connection_claim() -> None:
    _app()
    assert hasattr(TenderProviderManagerDialog, "manual_adapter_requested")
    assert ManualAdapterWizardDialog.SUCCESS_MESSAGE == (
        "Адаптер настроен. Требуется проверка подключения."
    )
    dialog = ManualAdapterWizardDialog.empty_for_test()
    labels = " ".join(button.text().casefold() for button in dialog.findChildren(QPushButton))
    assert "проверить подключение" not in labels
    assert "offline" in dialog.preview_notice.text().casefold()
