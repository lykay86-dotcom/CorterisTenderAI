"""RM-130 saved-profile execution modes over the RM-128 pure resolver."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from app.tenders.collector.provider_control import ProviderDisplayState, ProviderUiState
from app.tenders.search_profile_repository import TenderSearchProfileRepository
from app.tenders.search_profiles import (
    SearchProfileRuntimeQueryPolicy,
    TenderSearchProfile,
)
from app.tenders.unified_search import (
    SearchProfileExecutionMode,
    UnifiedTenderSearchRequest,
    resolve_unified_tender_search,
)


def _profile() -> TenderSearchProfile:
    return TenderSearchProfile(
        id="universal-profile",
        name="Universal",
        keywords=("камеры", "монтаж"),
        excluded_keywords=("аренда",),
        regions=("Москва",),
        laws=("44-ФЗ",),
        min_price=Decimal("0.1"),
        max_price=Decimal("9007199254740993.01"),
        price_currency="RUB",
        lookback_days=15,
        page_size=75,
        provider_ids=("eis",),
    )


def _state() -> ProviderDisplayState:
    return ProviderDisplayState(
        provider_id="eis",
        display_name="ЕИС",
        enabled=True,
        ui_state=ProviderUiState.LIMITED,
        status_text="Доступен",
        connection_mode="public",
        implementation_status="implemented",
        homepage_url="https://example.invalid/",
        last_checked_at="",
        last_success_at="",
        last_error="",
        latency_ms=None,
    )


def _resolve(profile: TenderSearchProfile, query_text: str):
    return resolve_unified_tender_search(
        UnifiedTenderSearchRequest(profile.id, query_text, ("eis",)),
        profiles=(profile,),
        provider_states=(_state(),),
        today=date(2026, 7, 16),
    )


def test_blank_runtime_text_is_saved_profile_mode_with_exact_query() -> None:
    profile = _profile()

    resolved = _resolve(profile, " \t\n ")

    assert resolved.execution_mode is SearchProfileExecutionMode.SAVED_PROFILE
    assert resolved.query == profile.to_search_query(today=date(2026, 7, 16))
    assert resolved.profile is profile


def test_nonblank_runtime_text_is_keyword_override_only() -> None:
    profile = _profile()
    original = profile.to_search_query(today=date(2026, 7, 16))

    resolved = _resolve(profile, "  камеры\n тепловизионные   монтаж ")

    assert resolved.execution_mode is SearchProfileExecutionMode.KEYWORD_OVERRIDE
    assert resolved.query.keywords == ("камеры тепловизионные монтаж",)
    assert replace(resolved.query, keywords=original.keywords) == original
    assert resolved.query.min_price == Decimal("0.1")
    assert resolved.query.max_price == Decimal("9007199254740993.01")
    assert profile.keywords == ("камеры", "монтаж")


def test_profile_policy_is_typed_and_unknown_policy_fails_closed() -> None:
    assert _profile().runtime_query_policy is (
        SearchProfileRuntimeQueryPolicy.REPLACE_KEYWORDS_IF_PRESENT
    )

    with pytest.raises(ValueError, match="runtime_query_policy"):
        replace(_profile(), runtime_query_policy="unknown")


def test_runtime_text_never_mutates_repository_bytes(tmp_path) -> None:
    repository = TenderSearchProfileRepository(tmp_path / "search_profiles.json")
    repository.initialize()
    saved = repository.save(_profile(), replace_existing=False)
    before = repository.path.read_bytes()

    resolved = _resolve(repository.get(saved.id), "  только текущий запуск  ")

    assert resolved.execution_mode is SearchProfileExecutionMode.KEYWORD_OVERRIDE
    assert resolved.query.keywords == ("только текущий запуск",)
    assert repository.path.read_bytes() == before
    assert repository.get(saved.id).keywords == ("камеры", "монтаж")
