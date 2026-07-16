"""RM-130 schema-v2 and typed saved-profile loading contract."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import json

import pytest

from app.tenders.search_profile_repository import (
    SearchProfileCatalogLoadStatus,
    TenderSearchProfileRepository,
)
from app.tenders.search_profiles import (
    SearchProfileRuntimeQueryPolicy,
    TenderSearchProfile,
    create_builtin_search_profiles,
)


def _profile(profile_id: str = "custom-schema", **changes: object) -> TenderSearchProfile:
    values: dict[str, object] = {
        "id": profile_id,
        "name": "Пользовательский профиль",
        "keywords": ("СКУД",),
        "min_price": Decimal("0.1000000000000000001"),
        "max_price": Decimal("9007199254740993.01"),
        "price_currency": "RUB",
        "created_at": "2026-07-16T15:00:00+00:00",
        "updated_at": "2026-07-16T16:00:00+00:00",
    }
    values.update(changes)
    return TenderSearchProfile(**values)


def _write(path, *, version: int, profiles: list[dict[str, object]]) -> bytes:
    payload = {
        "schema_version": version,
        "updated_at": "2026-07-16T18:00:00+00:00",
        "profiles": profiles,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path.read_bytes()


def test_missing_load_is_typed_and_does_not_write(tmp_path) -> None:
    path = tmp_path / "search_profiles.json"
    repository = TenderSearchProfileRepository(path)

    result = repository.load_result()

    assert result.status is SearchProfileCatalogLoadStatus.MISSING
    assert result.source_schema_version is None
    assert len(result.profiles) == 7
    assert not path.exists()


def test_valid_v1_migrates_only_in_memory_with_explicit_warnings(tmp_path) -> None:
    path = tmp_path / "search_profiles.json"
    legacy = _profile().to_dict()
    legacy.pop("runtime_query_policy")
    legacy.pop("price_currency")
    legacy["min_price"] = 0.1
    legacy["max_price"] = 5000000
    legacy["created_at"] = "2026-07-16T15:00:00"
    before = _write(path, version=1, profiles=[legacy])

    result = TenderSearchProfileRepository(path).load_result()

    assert result.status is SearchProfileCatalogLoadStatus.MIGRATED_V1
    assert result.source_schema_version == 1
    assert path.read_bytes() == before
    custom = next(item for item in result.profiles if item.id == "custom-schema")
    assert custom.runtime_query_policy is (
        SearchProfileRuntimeQueryPolicy.REPLACE_KEYWORDS_IF_PRESENT
    )
    assert custom.min_price == Decimal("0.1")
    assert custom.max_price == Decimal("5000000")
    assert custom.price_currency == "RUB"
    assert custom.created_at == ""
    assert any("numeric" in warning.casefold() for warning in result.warnings)
    assert any("timezone" in warning.casefold() for warning in result.warnings)


def test_v1_preserves_custom_and_modified_disabled_builtin_without_writing(tmp_path) -> None:
    path = tmp_path / "search_profiles.json"
    builtin = create_builtin_search_profiles()[0].to_dict()
    builtin.pop("runtime_query_policy")
    builtin.update({"name": "Edited v1 builtin", "enabled": False, "is_builtin": False})
    custom = _profile().to_dict()
    custom.pop("runtime_query_policy")
    before = _write(path, version=1, profiles=[custom, builtin])

    result = TenderSearchProfileRepository(path).load_result()
    by_id = {profile.id: profile for profile in result.profiles}

    assert result.status is SearchProfileCatalogLoadStatus.MIGRATED_V1
    assert by_id["all-corteris"].name == "Edited v1 builtin"
    assert not by_id["all-corteris"].enabled
    assert by_id["all-corteris"].is_builtin
    assert by_id["custom-schema"].min_price == Decimal("0.1000000000000000001")
    assert tuple(profile.id for profile in result.profiles[:7]) == tuple(
        profile.id for profile in create_builtin_search_profiles()
    )
    assert result.profiles[-1].id == "custom-schema"
    assert path.read_bytes() == before


def test_current_v2_round_trip_uses_strings_policy_and_aware_utc(tmp_path) -> None:
    path = tmp_path / "search_profiles.json"
    repository = TenderSearchProfileRepository(path)
    repository.initialize()
    saved = repository.save(_profile(), replace_existing=False)

    result = repository.load_result()
    payload = json.loads(path.read_text(encoding="utf-8"))
    stored = next(item for item in payload["profiles"] if item["id"] == "custom-schema")

    assert result.status is SearchProfileCatalogLoadStatus.CURRENT
    assert result.source_schema_version == 2
    assert payload["schema_version"] == 2
    assert stored["min_price"] == "0.1000000000000000001"
    assert stored["max_price"] == "9007199254740993.01"
    assert stored["runtime_query_policy"] == "replace_keywords_if_present"
    assert datetime.fromisoformat(payload["updated_at"]).tzinfo is not None
    assert next(item for item in result.profiles if item.id == "custom-schema") == saved


@pytest.mark.parametrize(
    "mutate",
    (
        lambda item: item.__setitem__("min_price", 0.1),
        lambda item: item.__setitem__("min_price", "NaN"),
        lambda item: item.__setitem__("min_price", "Infinity"),
        lambda item: item.__setitem__("min_price", "-0.01"),
        lambda item: item.__setitem__("runtime_query_policy", "unknown"),
        lambda item: item.__setitem__("created_at", "2026-07-16T15:00:00"),
        lambda item: item.__setitem__("page_size", 0),
        lambda item: item.__setitem__("minimum_score", 101),
        lambda item: item.__setitem__("lookback_days", -1),
    ),
)
def test_invalid_known_v2_field_fails_closed_without_rewrite(tmp_path, mutate) -> None:
    path = tmp_path / "search_profiles.json"
    item = _profile().to_dict()
    mutate(item)
    before = _write(path, version=2, profiles=[item])

    result = TenderSearchProfileRepository(path).load_result()

    assert result.status is SearchProfileCatalogLoadStatus.CORRUPT
    assert result.profiles == ()
    assert result.quarantine_path is not None
    assert result.quarantine_path.read_bytes() == before
    assert path.read_bytes() == before


def test_future_schema_is_typed_and_byte_preserved(tmp_path) -> None:
    path = tmp_path / "search_profiles.json"
    before = _write(path, version=99, profiles=[_profile().to_dict()])

    result = TenderSearchProfileRepository(path).load_result()

    assert result.status is SearchProfileCatalogLoadStatus.UNSUPPORTED_FUTURE
    assert result.source_schema_version == 99
    assert result.profiles == ()
    assert result.quarantine_path is None
    assert path.read_bytes() == before


def test_duplicate_casefold_identity_corrupts_whole_catalog(tmp_path) -> None:
    path = tmp_path / "search_profiles.json"
    first = _profile("custom-dupe").to_dict()
    second = _profile("custom-other").to_dict()
    second["id"] = "CUSTOM-DUPE"
    before = _write(path, version=2, profiles=[first, second])

    result = TenderSearchProfileRepository(path).load_result()

    assert result.status is SearchProfileCatalogLoadStatus.CORRUPT
    assert result.profiles == ()
    assert path.read_bytes() == before
