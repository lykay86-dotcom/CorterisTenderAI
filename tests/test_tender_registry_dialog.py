"""Tests for the local tender-registry dialog."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.tenders.tender_registry import TenderRegistryRepository
from app.ui.tender_registry_dialog import TenderRegistryDialog
from tests.test_tender_registry import _evaluated_tender, _run


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _repository(tmp_path) -> TenderRegistryRepository:
    repository = TenderRegistryRepository(
        tmp_path / "tender_registry.sqlite3"
    )
    repository.record_profile_run(
        _run(_evaluated_tender()),
        run_id="run-1",
    )
    return repository


def test_registry_dialog_displays_saved_tender_and_history(
    tmp_path,
) -> None:
    app = _app()
    repository = _repository(tmp_path)

    dialog = TenderRegistryDialog(repository)

    assert dialog.table.rowCount() == 1
    assert dialog.records[0].relevance_score == 88
    assert dialog.history_table.rowCount() == 1
    assert dialog.total_metric.text() == "1"
    assert dialog.active_metric.text() == "1"
    app.processEvents()


def test_registry_dialog_search_can_show_empty_state(tmp_path) -> None:
    app = _app()
    dialog = TenderRegistryDialog(_repository(tmp_path))

    dialog.search_edit.setText("несуществующая закупка")
    dialog.refresh_records()

    assert dialog.table.rowCount() == 0
    assert dialog.records == ()
    assert "Показано 0" in dialog.status_label.text()
    app.processEvents()


def test_registry_dialog_archives_and_restores_record(tmp_path) -> None:
    app = _app()
    repository = _repository(tmp_path)
    dialog = TenderRegistryDialog(repository)

    dialog.table.selectRow(0)
    dialog._toggle_selected_archive()

    assert repository.count_tenders() == 0

    archive_index = dialog.state_combo.findData("archived")
    dialog.state_combo.setCurrentIndex(archive_index)
    dialog.refresh_records()

    assert dialog.table.rowCount() == 1
    assert dialog.records[0].archived
    assert dialog.archive_button.text() == "Вернуть из архива"

    dialog._toggle_selected_archive()
    assert repository.count_tenders() == 1
    app.processEvents()


def test_registry_dialog_builds_query_from_controls(tmp_path) -> None:
    app = _app()
    dialog = TenderRegistryDialog(_repository(tmp_path))

    dialog.search_edit.setText("Москва")
    dialog.minimum_score_spin.setValue(70)
    all_index = dialog.state_combo.findData("all")
    dialog.state_combo.setCurrentIndex(all_index)

    query = dialog.current_query()

    assert query.text == "Москва"
    assert query.minimum_score == 70
    assert query.include_archived
    assert not query.accepted_only
    app.processEvents()
