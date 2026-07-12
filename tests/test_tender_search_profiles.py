"""Tests for saved tender-search profiles and built-in presets."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.tenders.corteris_filter import TenderDirection
from app.tenders.search_profiles import (
    TenderSearchProfile,
    create_builtin_search_profiles,
)


def test_builtin_profiles_cover_all_corteris_directions() -> None:
    profiles = create_builtin_search_profiles(
        now=datetime(
            2026, 7, 13, 8, 0, tzinfo=timezone.utc
        )
    )

    assert [profile.id for profile in profiles] == [
        "all-corteris",
        "video-surveillance",
        "ops",
        "skud",
        "barriers-anpr",
        "maintenance",
        "integrated-security",
    ]
    assert all(profile.is_builtin for profile in profiles)

    covered = {
        direction
        for profile in profiles
        for direction in profile.directions
    }
    assert {
        TenderDirection.VIDEO_SURVEILLANCE,
        TenderDirection.OPS,
        TenderDirection.SKUD,
        TenderDirection.BARRIERS,
        TenderDirection.ANPR,
        TenderDirection.MAINTENANCE,
        TenderDirection.INTEGRATED_SECURITY,
    }.issubset(covered)


def test_profile_builds_search_query_and_filter_options() -> None:
    profile = TenderSearchProfile(
        id="moscow-video",
        name="Москва — видео",
        keywords=("видеонаблюдение",),
        excluded_keywords=("веб-камера",),
        directions=(TenderDirection.VIDEO_SURVEILLANCE,),
        regions=("Москва",),
        laws=("44-ФЗ",),
        min_price=100_000,
        max_price=5_000_000,
        minimum_score=40,
        lookback_days=14,
        page_size=100,
        provider_ids=("eis",),
    )

    query = profile.to_search_query(
        today=date(2026, 7, 13),
        page=2,
    )
    options = profile.to_filter_options()

    assert query.date_from == date(2026, 6, 29)
    assert query.date_to == date(2026, 7, 13)
    assert query.page == 2
    assert query.page_size == 100
    assert query.excluded_keywords == ("веб-камера",)
    assert options.minimum_score == 40
    assert options.required_directions == (
        TenderDirection.VIDEO_SURVEILLANCE,
    )
    assert options.regions == ("Москва",)


def test_profile_json_round_trip_preserves_directions() -> None:
    source = create_builtin_search_profiles()[4]

    restored = TenderSearchProfile.from_dict(
        source.to_dict()
    )

    assert restored == source
    assert restored.directions == (
        TenderDirection.BARRIERS,
        TenderDirection.ANPR,
    )


def test_profile_prices_round_trip_as_exact_json_strings() -> None:
    profile = TenderSearchProfile(
        id="exact-money",
        name="Точные суммы",
        keywords=("СКУД",),
        min_price=0.1,
        max_price="9007199254740993.01",
    )

    payload = profile.to_dict()
    restored = TenderSearchProfile.from_dict(payload)
    legacy = TenderSearchProfile.from_dict(
        {
            **payload,
            "min_price": 1000,
            "max_price": 5000000.5,
        }
    )

    assert payload["min_price"] == "0.1"
    assert payload["max_price"] == "9007199254740993.01"
    assert restored.min_price == Decimal("0.1")
    assert restored.max_price == Decimal("9007199254740993.01")
    assert legacy.min_price == Decimal("1000")
    assert legacy.max_price == Decimal("5000000.5")


def test_clone_as_custom_changes_identity_and_timestamps() -> None:
    builtin = create_builtin_search_profiles()[1]
    moment = datetime(
        2026, 7, 13, 9, 30, tzinfo=timezone.utc
    )

    clone = builtin.clone_as_custom(
        profile_id="video-moscow",
        name="Видео — Москва",
        now=moment,
    )

    assert clone.id == "video-moscow"
    assert clone.name == "Видео — Москва"
    assert not clone.is_builtin
    assert clone.created_at == "2026-07-13T09:30:00+00:00"
    assert clone.updated_at == clone.created_at
    assert clone.keywords == builtin.keywords


def test_profile_rejects_invalid_ranges_and_identity() -> None:
    with pytest.raises(ValueError):
        TenderSearchProfile(
            id="Bad Id",
            name="Bad",
            keywords=("СКУД",),
        )

    with pytest.raises(ValueError):
        TenderSearchProfile(
            id="bad-price",
            name="Bad price",
            keywords=("СКУД",),
            min_price=1000,
            max_price=100,
        )
