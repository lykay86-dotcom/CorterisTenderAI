"""Tests for atomic search-profile persistence."""

from __future__ import annotations

import json

import pytest

from app.tenders.corteris_filter import TenderDirection
from app.tenders.search_profile_repository import (
    BuiltinSearchProfileError,
    SearchProfileCatalogLoadStatus,
    SearchProfileNotFoundError,
    TenderSearchProfileRepository,
)
from app.tenders.search_profiles import TenderSearchProfile


def custom_profile(
    profile_id: str = "custom-skud",
) -> TenderSearchProfile:
    return TenderSearchProfile(
        id=profile_id,
        name="Мой СКУД",
        keywords=("СКУД", "турникет"),
        directions=(TenderDirection.SKUD,),
        regions=("Москва",),
        provider_ids=("eis",),
    )


def test_repository_initializes_builtin_catalog(tmp_path) -> None:
    path = tmp_path / "search_profiles.json"
    repository = TenderSearchProfileRepository(path)

    profiles = repository.initialize()

    assert path.is_file()
    assert len(profiles) == 7
    assert profiles[0].id == "all-corteris"

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    assert len(payload["profiles"]) == 7


def test_repository_custom_profile_crud(tmp_path) -> None:
    repository = TenderSearchProfileRepository(tmp_path / "search_profiles.json")
    repository.initialize()

    saved = repository.save(custom_profile())
    assert saved.created_at
    assert repository.get("custom-skud").name == "Мой СКУД"

    updated = repository.update(
        "custom-skud",
        name="СКУД Москва",
        minimum_score=45,
    )
    assert updated.name == "СКУД Москва"
    assert updated.minimum_score == 45
    assert updated.created_at == saved.created_at

    removed = repository.delete("custom-skud")
    assert removed.id == "custom-skud"
    with pytest.raises(SearchProfileNotFoundError):
        repository.get("custom-skud")


def test_builtin_profile_cannot_be_deleted(tmp_path) -> None:
    repository = TenderSearchProfileRepository(tmp_path / "search_profiles.json")
    repository.initialize()

    with pytest.raises(BuiltinSearchProfileError):
        repository.delete("video-surveillance")


def test_disabled_profiles_can_be_hidden(tmp_path) -> None:
    repository = TenderSearchProfileRepository(tmp_path / "search_profiles.json")
    repository.initialize()
    repository.set_enabled("ops", False)

    visible = repository.list_profiles(include_disabled=False)

    assert "ops" not in {profile.id for profile in visible}
    assert not repository.get("ops").enabled


def test_corrupt_catalog_is_quarantined_without_rewriting_original(
    tmp_path,
) -> None:
    path = tmp_path / "search_profiles.json"
    original = b"{not-json"
    path.write_bytes(original)
    repository = TenderSearchProfileRepository(path)

    profiles = repository.initialize()
    result = repository.load_result()

    assert profiles == ()
    assert result.status is SearchProfileCatalogLoadStatus.CORRUPT
    assert path.read_bytes() == original
    assert list(tmp_path.glob("search_profiles.corrupt-*.json"))


def test_restore_builtins_keeps_custom_profiles(tmp_path) -> None:
    repository = TenderSearchProfileRepository(tmp_path / "search_profiles.json")
    repository.initialize()
    repository.update(
        "video-surveillance",
        name="Изменённое название",
    )
    repository.save(custom_profile())

    restored = repository.restore_builtin_profiles()

    by_id = {profile.id: profile for profile in restored}
    assert by_id["video-surveillance"].name == ("Видеонаблюдение")
    assert by_id["custom-skud"].name == "Мой СКУД"
