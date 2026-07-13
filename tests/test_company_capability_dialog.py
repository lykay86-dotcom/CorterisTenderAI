"""UI tests for editing the confirmed company capability profile."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.tenders.collector.company_capability import (
    CompanyCapabilityProfileRepository,
)
from app.ui.company_capability_dialog import CompanyCapabilityDialog


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_dialog_builds_and_saves_confirmed_profile(tmp_path) -> None:
    app = _app()
    repository = CompanyCapabilityProfileRepository(tmp_path / "company_capability_profile.json")
    dialog = CompanyCapabilityDialog(repository)
    dialog.company_name.setText("ООО КОРТЕРИС")
    dialog.text_fields["business_directions"].setText("видеонаблюдение; СКУД")
    dialog.text_fields["self_install_regions"].setText("Москва")
    dialog.text_fields["confirmed_experience"].setText("Контракт №1")
    dialog.text_fields["equipment"].setText("IP-камера")
    dialog.text_fields["suppliers"].setText("Поставщик 1")
    dialog.money_fields["max_project_amount"].setText("30000000.01")
    dialog.money_fields["working_capital"].setText("5000000.50")
    dialog.crew_count.setValue(2)
    dialog.confirmed_by.setText("Директор")
    dialog.confirmation.setChecked(True)

    dialog.save_profile()
    restored = repository.load()

    assert restored.is_configured
    assert restored.business_directions == ("видеонаблюдение", "СКУД")
    assert restored.installation_crew_count == 2
    assert str(restored.max_project_amount) == "30000000.01"
    assert "Профиль подтверждён" in dialog.status.text()
    app.processEvents()
