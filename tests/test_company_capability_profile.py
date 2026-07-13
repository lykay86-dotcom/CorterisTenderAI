"""Tests for the confirmed company capability profile."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.tenders.collector.company_capability import (
    CompanyCapabilityProfile,
    CompanyCapabilityProfileRepository,
)
from app.tenders.collector.participation_score import (
    CorterisCompanyProfile,
    CorterisParticipationRanker,
    ParticipationScoringContext,
)
from tests.collector_c3_helpers import make_tender


NOW = "2026-07-12T12:00:00+00:00"


def _profile(**changes) -> CompanyCapabilityProfile:
    values = {
        "company_name": "ООО КОРТЕРИС",
        "business_directions": ("видеонаблюдение", "СКУД"),
        "self_install_regions": ("Москва",),
        "licenses": ("МЧС",),
        "installation_crew_count": 2,
        "confirmed_experience": ("Контракт №1",),
        "max_project_amount": Decimal("30000000"),
        "working_capital": Decimal("5000000"),
        "equipment": ("IP-камера",),
        "brands": ("Trassir",),
        "suppliers": ("Поставщик 1",),
        "minimum_margin_percent": Decimal("20"),
        "confirmed_at": NOW,
        "confirmed_by": "Директор",
        "evidence_note": "Проверено по документам компании",
    }
    values.update(changes)
    return CompanyCapabilityProfile(**values)


def test_profile_normalizes_and_reports_missing_sections() -> None:
    profile = _profile(
        business_directions="СКУД; Видеонаблюдение; скуд",
        max_project_amount="30000000.00",
    )

    assert profile.business_directions == ("СКУД", "Видеонаблюдение")
    assert profile.max_project_amount == Decimal("30000000.00")
    assert profile.is_confirmed
    assert profile.is_configured
    assert "СРО" not in profile.missing_sections


def test_repository_requires_confirmation_and_round_trips_decimal(tmp_path) -> None:
    repository = CompanyCapabilityProfileRepository(tmp_path / "company_capability_profile.json")

    with pytest.raises(ValueError):
        repository.save(CompanyCapabilityProfile(company_name="ООО КОРТЕРИС"))

    repository.save(_profile())
    restored = repository.load()

    assert restored.company_name == "ООО КОРТЕРИС"
    assert restored.max_project_amount == Decimal("30000000")
    assert restored.updated_at
    assert restored.confirmed_by == "Директор"


def test_empty_production_profile_removes_assumed_capabilities() -> None:
    scoring_profile = CorterisCompanyProfile.from_capability(CompanyCapabilityProfile())
    score = CorterisParticipationRanker(scoring_profile).score(
        make_tender(),
        ParticipationScoringContext(now=datetime(2026, 7, 12, tzinfo=timezone.utc)),
    )

    assert score.total_score <= 64
    assert any(
        "Недостаточно данных о возможностях компании" in item for item in score.negative_factors
    )
    components = {item.key: item for item in score.components}
    assert "Недостаточно данных" in components["region"].explanation
    assert "Недостаточно данных" in components["price"].explanation
    assert "Недостаточно данных" in components["equipment"].explanation


def test_confirmed_profile_drives_direction_region_and_price() -> None:
    scoring_profile = CorterisCompanyProfile.from_capability(_profile())
    score = CorterisParticipationRanker(scoring_profile).score(
        make_tender(
            title="Монтаж видеонаблюдения Trassir",
            amount="1500000",
        ),
        ParticipationScoringContext(now=datetime(2026, 7, 12, tzinfo=timezone.utc)),
    )
    components = {item.key: item for item in score.components}

    assert scoring_profile.strict_capabilities
    assert components["direction"].score > 0
    assert components["region"].score == 10
    assert components["price"].score == 10
    assert "Недостаточно данных о возможностях компании" not in (score.negative_factors)
