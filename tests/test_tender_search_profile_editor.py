"""Tests for the reusable tender search profile editor."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from app.tenders.corteris_filter import TenderDirection
from app.tenders.search_profiles import (
    create_builtin_search_profiles,
)
from app.ui.tender_search_profile_editor import (
    TenderSearchProfileEditor,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_editor_round_trips_profile_fields() -> None:
    _application = _app()
    profile = create_builtin_search_profiles()[1]
    editor = TenderSearchProfileEditor()
    editor.load_profile(profile)

    built = editor.build_profile()

    assert built == profile
    assert not editor.profile_id_edit.isEnabled()
    assert TenderDirection.VIDEO_SURVEILLANCE in built.directions


def test_editor_parses_regions_prices_and_extra_laws() -> None:
    _application = _app()
    profile = create_builtin_search_profiles()[0]
    editor = TenderSearchProfileEditor()
    editor.load_profile(profile)

    editor.regions_edit.setPlainText("Москва\nМосковская область, Москва")
    editor.min_price_spin.setValue(150_000)
    editor.max_price_spin.setValue(5_000_000)
    editor.additional_laws_edit.setText("615-ПП, 223-ФЗ")
    editor.provider_ids_edit.setText("eis, rts_tender, eis")

    built = editor.build_profile()

    assert built.regions == (
        "Москва",
        "Московская область",
    )
    assert built.min_price == 150_000
    assert built.max_price == 5_000_000
    assert built.laws == ("44-ФЗ", "223-ФЗ", "615-ПП")
    assert built.provider_ids == ("eis", "rts_tender")


def test_editor_rejects_profile_without_keywords_or_directions() -> None:
    _application = _app()
    profile = create_builtin_search_profiles()[0]
    editor = TenderSearchProfileEditor()
    editor.load_profile(profile)

    editor.keywords_edit.clear()
    for checkbox in editor.direction_checkboxes.values():
        checkbox.setChecked(False)

    with pytest.raises(ValueError):
        editor.build_profile()


def test_new_profile_id_can_be_edited() -> None:
    _application = _app()
    source = create_builtin_search_profiles()[0]
    custom = source.clone_as_custom(
        profile_id="custom-test",
        name="Пользовательский",
    )

    editor = TenderSearchProfileEditor()
    editor.load_profile(custom, allow_id_edit=True)

    assert editor.profile_id_edit.isEnabled()
    editor.profile_id_edit.setText("custom-renamed")
    assert editor.build_profile().id == "custom-renamed"
