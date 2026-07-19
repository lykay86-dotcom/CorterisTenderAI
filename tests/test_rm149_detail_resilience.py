from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.tenders.detail import validate_https_url
from app.tenders.tender_registry import TenderRegistryRepository
from app.ui.tender_registry_dialog import TenderRegistryDialog
from tests.test_tender_registry import _evaluated_tender, _run


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _dialog(tmp_path) -> tuple[TenderRegistryRepository, TenderRegistryDialog]:
    repository = TenderRegistryRepository(tmp_path / "registry.sqlite3")
    repository.record_profile_run(_run(_evaluated_tender()), run_id="run-1")
    return repository, TenderRegistryDialog(repository)


def test_stale_archive_action_does_not_mutate_again_or_fall_to_adjacent_row(tmp_path) -> None:
    _app()
    repository, dialog = _dialog(tmp_path)
    original = dialog.selected_record()
    assert original is not None
    assert repository.set_archived(original.registry_key, True)

    dialog._toggle_selected_archive()

    current = repository.get_record(original.registry_key)
    assert current is not None
    assert current.archived is True
    assert dialog.selected_record() is not None
    assert dialog.selected_record().registry_key == original.registry_key
    assert "Карточка изменилась" in dialog.status_label.text()


def test_detail_action_delegates_the_same_exact_key_to_existing_signal(tmp_path) -> None:
    app = _app()
    _, dialog = _dialog(tmp_path)
    selected = dialog.selected_record()
    assert selected is not None
    requested: list[str] = []
    dialog.documents_requested.connect(requested.append)

    dialog.details.action_requested.emit("download_documents")
    app.processEvents()

    assert requested == [selected.registry_key]
    assert dialog.selected_record() is not None
    assert dialog.selected_record().registry_key == selected.registry_key


def test_source_policy_has_no_fallback_for_unsafe_or_ambiguous_url() -> None:
    assert validate_https_url("https://example.test/tender?id=1") == (
        "https://example.test/tender?id=1"
    )
    assert validate_https_url("//example.test/tender") is None
    assert validate_https_url("HTTPS://example.test/tender#fragment") is None


def test_repeated_snapshot_publication_preserves_widget_and_action_identity(tmp_path) -> None:
    app = _app()
    _, dialog = _dialog(tmp_path)
    panel_id = id(dialog.details)
    button_ids = {
        item.action_id: id(button)
        for item, button in (
            (action, dialog.details._secondary_buttons[action.action_id])
            for action in dialog.details.snapshot.actions
            if action.action_id in dialog.details._secondary_buttons
        )
    }

    for _ in range(3):
        dialog._show_selected_record()
        app.processEvents()

    assert id(dialog.details) == panel_id
    assert button_ids == {
        action_id: id(dialog.details._secondary_buttons[action_id]) for action_id in button_ids
    }
