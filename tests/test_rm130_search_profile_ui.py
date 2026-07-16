"""RM-130 exact Decimal input and typed catalog status presentation."""

from __future__ import annotations

from decimal import Decimal
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLineEdit

from app.tenders.search_profile_repository import TenderSearchProfileRepository
from app.tenders.search_profiles import TenderSearchProfile
from app.ui.tender_search_profile_editor import TenderSearchProfileEditor
from app.ui.tender_search_profiles_dialog import TenderSearchProfilesPanel


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _profile() -> TenderSearchProfile:
    return TenderSearchProfile(
        id="exact-ui",
        name="Exact UI",
        keywords=("СКУД",),
        min_price=Decimal("0.1"),
        max_price=Decimal("9007199254740993.01"),
        created_at="2026-07-16T15:00:00+00:00",
        updated_at="2026-07-16T16:00:00+00:00",
    )


def _write(path, *, version: int, profiles: list[dict[str, object]]) -> bytes:
    path.write_text(
        json.dumps(
            {
                "schema_version": version,
                "updated_at": "2026-07-16T18:00:00+00:00",
                "profiles": profiles,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path.read_bytes()


def test_editor_round_trips_exact_decimal_without_float(tmp_path) -> None:
    _application = _app()
    editor = TenderSearchProfileEditor()
    editor.load_profile(_profile())

    assert isinstance(editor.min_price_spin, QLineEdit)
    assert isinstance(editor.max_price_spin, QLineEdit)
    assert editor.min_price_spin.text() == "0.1"
    assert editor.max_price_spin.text() == "9007199254740993.01"

    built = editor.build_profile()
    repository = TenderSearchProfileRepository(tmp_path / "search_profiles.json")
    repository.initialize()
    saved = repository.save(built, replace_existing=False)
    payload = json.loads(repository.path.read_text(encoding="utf-8"))
    stored = next(item for item in payload["profiles"] if item["id"] == "exact-ui")

    assert built.min_price == Decimal("0.1")
    assert built.max_price == Decimal("9007199254740993.01")
    assert stored["min_price"] == "0.1"
    assert stored["max_price"] == "9007199254740993.01"

    reloaded = repository.get(saved.id)
    second_editor = TenderSearchProfileEditor()
    second_editor.load_profile(reloaded)
    assert second_editor.min_price_spin.text() == "0.1"
    assert second_editor.max_price_spin.text() == "9007199254740993.01"
    assert second_editor.build_profile().min_price == Decimal("0.1")
    assert second_editor.build_profile().max_price == Decimal("9007199254740993.01")


def test_migrated_v1_status_is_honest_and_editable(tmp_path) -> None:
    _application = _app()
    path = tmp_path / "search_profiles.json"
    legacy = _profile().to_dict()
    legacy.pop("runtime_query_policy")
    before = _write(path, version=1, profiles=[legacy])

    panel = TenderSearchProfilesPanel(TenderSearchProfileRepository(path))

    assert "schema v1" in panel.status_label.text()
    assert panel.save_button.isEnabled()
    assert path.read_bytes() == before


def test_future_status_blocks_mutation_and_preserves_bytes(tmp_path) -> None:
    _application = _app()
    path = tmp_path / "search_profiles.json"
    before = _write(path, version=99, profiles=[_profile().to_dict()])

    panel = TenderSearchProfilesPanel(TenderSearchProfileRepository(path))

    assert "новее" in panel.status_label.text().casefold()
    assert not panel.save_button.isEnabled()
    assert not panel.restore_button.isEnabled()
    assert not panel.run_button.isEnabled()
    assert path.read_bytes() == before


def test_corrupt_status_blocks_mutation_and_preserves_original(tmp_path) -> None:
    _application = _app()
    path = tmp_path / "search_profiles.json"
    original = b"{not-json"
    path.write_bytes(original)

    panel = TenderSearchProfilesPanel(TenderSearchProfileRepository(path))

    assert "повреж" in panel.status_label.text().casefold()
    assert not panel.save_button.isEnabled()
    assert not panel.restore_button.isEnabled()
    assert path.read_bytes() == original
