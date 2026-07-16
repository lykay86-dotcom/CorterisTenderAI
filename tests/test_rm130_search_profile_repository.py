"""RM-130 non-destructive repository migration and built-in protection."""

from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path

import pytest

from app.tenders.search_profile_repository import (
    BuiltinSearchProfileError,
    SearchProfileCatalogLoadStatus,
    SearchProfileCatalogMutationError,
    TenderSearchProfileRepository,
)
from app.tenders.search_profiles import TenderSearchProfile, create_builtin_search_profiles


def _profile(profile_id: str = "custom-a", **changes: object) -> TenderSearchProfile:
    values: dict[str, object] = {
        "id": profile_id,
        "name": "Custom A",
        "keywords": ("СКУД",),
        "min_price": Decimal("100.00"),
        "created_at": "2026-07-16T15:00:00+00:00",
        "updated_at": "2026-07-16T16:00:00+00:00",
    }
    values.update(changes)
    return TenderSearchProfile(**values)


def _write(path: Path, *, version: int, profiles: list[dict[str, object]]) -> bytes:
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


def test_first_v1_mutation_creates_exact_backup_and_current_v2(tmp_path) -> None:
    path = tmp_path / "search_profiles.json"
    legacy = _profile().to_dict()
    legacy.pop("runtime_query_policy")
    original = _write(path, version=1, profiles=[legacy])
    repository = TenderSearchProfileRepository(path)

    updated = repository.update("custom-a", name="Updated")

    backups = list(tmp_path.glob("search_profiles.v1-backup-*.json"))
    assert updated.name == "Updated"
    assert len(backups) == 1
    assert backups[0].read_bytes() == original
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 2
    assert repository.load_result().status is SearchProfileCatalogLoadStatus.CURRENT


def test_corrupt_catalog_is_copied_to_quarantine_without_target_rewrite(tmp_path) -> None:
    path = tmp_path / "search_profiles.json"
    original = b"{not-json"
    path.write_bytes(original)
    repository = TenderSearchProfileRepository(path)

    result = repository.load_result()

    assert result.status is SearchProfileCatalogLoadStatus.CORRUPT
    assert result.quarantine_path is not None
    assert result.quarantine_path.read_bytes() == original
    assert path.read_bytes() == original
    with pytest.raises(SearchProfileCatalogMutationError):
        repository.save(_profile())


@pytest.mark.parametrize("version", (3, 99))
def test_future_catalog_blocks_every_mutation_and_preserves_bytes(tmp_path, version) -> None:
    path = tmp_path / "search_profiles.json"
    before = _write(path, version=version, profiles=[_profile().to_dict()])
    repository = TenderSearchProfileRepository(path)

    operations = (
        lambda: repository.save(_profile("custom-b")),
        lambda: repository.update("custom-a", name="Changed"),
        lambda: repository.delete("custom-a"),
        lambda: repository.set_enabled("custom-a", False),
        repository.restore_builtin_profiles,
    )
    for operation in operations:
        with pytest.raises(SearchProfileCatalogMutationError):
            operation()
        assert path.read_bytes() == before


def test_builtin_identity_comes_from_canonical_id_not_json_flag(tmp_path) -> None:
    path = tmp_path / "search_profiles.json"
    canonical = create_builtin_search_profiles()[0].to_dict()
    canonical.update({"name": "Edited builtin", "enabled": False, "is_builtin": False})
    forged = _profile("custom-forged").to_dict()
    forged["is_builtin"] = True
    _write(path, version=2, profiles=[canonical, forged])
    repository = TenderSearchProfileRepository(path)

    result = repository.load_result()
    by_id = {profile.id: profile for profile in result.profiles}

    assert by_id["all-corteris"].is_builtin
    assert by_id["all-corteris"].name == "Edited builtin"
    assert not by_id["all-corteris"].enabled
    assert not by_id["custom-forged"].is_builtin
    assert repository.delete("custom-forged").id == "custom-forged"
    with pytest.raises(BuiltinSearchProfileError):
        repository.delete("all-corteris")


def test_atomic_replace_failure_preserves_original_and_cleans_temp(tmp_path, monkeypatch) -> None:
    path = tmp_path / "search_profiles.json"
    repository = TenderSearchProfileRepository(path)
    repository.initialize()
    original = path.read_bytes()
    real_replace = Path.replace

    def fail_target_replace(source: Path, target: Path) -> Path:
        if source.name.endswith(".tmp") and target == path:
            raise OSError("simulated replace failure")
        return real_replace(source, target)

    monkeypatch.setattr(Path, "replace", fail_target_replace)

    with pytest.raises(SearchProfileCatalogMutationError):
        repository.save(_profile(), replace_existing=False)

    assert path.read_bytes() == original
    assert not path.with_suffix(path.suffix + ".tmp").exists()


def test_restore_resets_only_builtins_and_preserves_custom_exact(tmp_path) -> None:
    path = tmp_path / "search_profiles.json"
    repository = TenderSearchProfileRepository(path)
    repository.initialize()
    saved = repository.save(_profile(), replace_existing=False)
    repository.update("all-corteris", name="Changed")

    restored = repository.restore_builtin_profiles()
    by_id = {profile.id: profile for profile in restored}

    assert by_id["all-corteris"].name == "Все направления Кортерис"
    assert by_id["custom-a"].to_dict() == saved.to_dict()
