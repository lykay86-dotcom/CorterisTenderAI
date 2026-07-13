"""Tests for search profile management panel and dialog."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.tenders.search_profile_repository import (
    TenderSearchProfileRepository,
)
from app.tenders.search_profiles import (
    create_builtin_search_profiles,
)
from app.ui.tender_search_profiles_dialog import (
    TenderSearchProfilesDialog,
    TenderSearchProfilesPanel,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _repository(tmp_path) -> TenderSearchProfileRepository:
    return TenderSearchProfileRepository(tmp_path / "search_profiles.json")


def test_panel_initializes_builtin_profile_list(tmp_path) -> None:
    _application = _app()
    repository = _repository(tmp_path)

    panel = TenderSearchProfilesPanel(repository)

    assert panel.profile_list.count() == 7
    assert panel.selected_profile_id() == "all-corteris"
    assert panel.editor.profile is not None


def test_panel_creates_and_saves_custom_copy(tmp_path) -> None:
    _application = _app()
    repository = _repository(tmp_path)
    panel = TenderSearchProfilesPanel(repository)

    panel._create_copy()
    panel.editor.name_edit.setText("Москва — видеонаблюдение")
    draft_id = panel.editor.profile_id_edit.text()
    panel._save_profile()

    saved = repository.get(draft_id)
    assert not saved.is_builtin
    assert saved.name == "Москва — видеонаблюдение"
    assert panel.profile_list.count() == 8


def test_panel_blocks_builtin_delete_without_modal(tmp_path) -> None:
    _application = _app()
    repository = _repository(tmp_path)
    panel = TenderSearchProfilesPanel(repository)

    before = len(repository.list_profiles())
    panel._delete_selected()

    assert len(repository.list_profiles()) == before
    assert "удалить нельзя" in panel.status_label.text()


def test_panel_toggle_and_run_signal(tmp_path) -> None:
    _application = _app()
    repository = _repository(tmp_path)
    panel = TenderSearchProfilesPanel(repository)
    requested: list[str] = []
    panel.profile_run_requested.connect(requested.append)

    panel._run_selected()
    assert requested == ["all-corteris"]

    panel._toggle_selected()
    assert not repository.get("all-corteris").enabled
    requested.clear()
    panel._run_selected()
    assert requested == []
    assert "отключён" in panel.status_label.text()


def test_restore_builtins_preserves_custom_profiles(tmp_path) -> None:
    _application = _app()
    repository = _repository(tmp_path)
    repository.initialize()

    source = create_builtin_search_profiles()[0]
    custom = source.clone_as_custom(
        profile_id="custom-preserved",
        name="Сохранить меня",
    )
    repository.save(custom, replace_existing=False)
    repository.update(
        "all-corteris",
        name="Изменённое название",
    )

    panel = TenderSearchProfilesPanel(repository)
    panel._restore_builtins()

    assert repository.get("all-corteris").name == ("Все направления Кортерис")
    assert repository.get("custom-preserved").name == ("Сохранить меня")


def test_dialog_forwards_run_signal(tmp_path) -> None:
    _application = _app()
    repository = _repository(tmp_path)
    dialog = TenderSearchProfilesDialog(repository)
    requested: list[str] = []
    dialog.profile_run_requested.connect(requested.append)

    dialog.panel._run_selected()

    assert requested == ["all-corteris"]
    assert dialog.isModal()
