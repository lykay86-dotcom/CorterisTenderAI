"""RM-128 pure unified-search request boundary."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date
from decimal import Decimal

import pytest

from app.tenders.collector.provider_control import ProviderDisplayState, ProviderUiState
from app.tenders.search_profiles import TenderSearchProfile
from app.tenders.unified_search import (
    UnifiedTenderSearchRequest,
    UnifiedTenderSearchValidationError,
    resolve_unified_tender_search,
)


def _profile(*, enabled: bool = True) -> TenderSearchProfile:
    return TenderSearchProfile(
        id="  video-profile  ",
        name="Видеонаблюдение",
        description="Камеры и монтаж",
        keywords=("камеры", "монтаж"),
        excluded_keywords=("аренда",),
        regions=("Москва",),
        laws=("44-ФЗ",),
        min_price=Decimal("100000.25"),
        max_price=Decimal("9000000.75"),
        price_currency="RUB",
        lookback_days=15,
        page_size=75,
        provider_ids=("eis", "mos_supplier"),
        enabled=enabled,
    )


def _state(provider_id: str, *, enabled: bool = True) -> ProviderDisplayState:
    return ProviderDisplayState(
        provider_id=provider_id,
        display_name=provider_id.upper(),
        enabled=enabled,
        ui_state=ProviderUiState.LIMITED if enabled else ProviderUiState.DISABLED,
        status_text="Доступен" if enabled else "Отключён",
        connection_mode="Тест",
        implementation_status="test",
        homepage_url="https://example.invalid/",
        last_checked_at="",
        last_success_at="",
        last_error="",
        latency_ms=None,
    )


def test_blank_query_preserves_profile_query_and_exact_money() -> None:
    profile = _profile()
    resolved = resolve_unified_tender_search(
        UnifiedTenderSearchRequest(
            profile_id=" VIDEO-PROFILE ",
            query_text=" \t ",
            provider_ids=(" EIS ", "mos_supplier"),
        ),
        profiles=(profile,),
        provider_states=(_state("eis"), _state("mos_supplier")),
        today=date(2026, 7, 16),
    )

    assert resolved.profile is profile
    assert resolved.query == profile.to_search_query(today=date(2026, 7, 16))
    assert resolved.query.min_price == Decimal("100000.25")
    assert resolved.query.max_price == Decimal("9000000.75")
    assert isinstance(resolved.query.min_price, Decimal)
    assert resolved.query.price_currency == "RUB"
    assert resolved.provider_ids == ("eis", "mos_supplier")


def test_nonblank_query_replaces_only_keywords_and_deduplicates_sources() -> None:
    profile = _profile()
    original = profile.to_search_query(today=date(2026, 7, 16))
    resolved = resolve_unified_tender_search(
        UnifiedTenderSearchRequest(
            profile_id=profile.id,
            query_text="  камеры\n  тепловизионные   монтаж  ",
            provider_ids=("EIS", " eis ", "MOS_SUPPLIER", "eis"),
        ),
        profiles=(profile,),
        provider_states=(_state("eis"), _state("mos_supplier")),
        today=date(2026, 7, 16),
    )

    assert resolved.query.keywords == ("камеры тепловизионные монтаж",)
    assert resolved.provider_ids == ("eis", "mos_supplier")
    assert resolved.query.excluded_keywords == original.excluded_keywords
    assert resolved.query.regions == original.regions
    assert resolved.query.laws == original.laws
    assert resolved.query.date_from == original.date_from
    assert resolved.query.date_to == original.date_to
    assert resolved.query.min_price == original.min_price
    assert resolved.query.max_price == original.max_price
    assert resolved.query.price_currency == original.price_currency
    assert resolved.query.page == original.page
    assert resolved.query.page_size == original.page_size
    assert profile.keywords == ("камеры", "монтаж")


@pytest.mark.parametrize(
    ("profiles", "states", "request", "message"),
    (
        ((), (_state("eis"),), UnifiedTenderSearchRequest("missing", "", ("eis",)), "не найден"),
        (
            (_profile(enabled=False),),
            (_state("eis"),),
            UnifiedTenderSearchRequest("video-profile", "", ("eis",)),
            "отключён",
        ),
        (
            (_profile(),),
            (_state("eis"),),
            UnifiedTenderSearchRequest("video-profile", "", ()),
            "источник",
        ),
        (
            (_profile(),),
            (_state("eis"),),
            UnifiedTenderSearchRequest("video-profile", "", ("stale",)),
            "не найден",
        ),
        (
            (_profile(),),
            (_state("eis", enabled=False),),
            UnifiedTenderSearchRequest("video-profile", "", ("eis",)),
            "отключён",
        ),
    ),
)
def test_invalid_profile_or_provider_is_rejected_without_fallback(
    profiles,
    states,
    request,
    message,
) -> None:
    with pytest.raises(UnifiedTenderSearchValidationError, match=message):
        resolve_unified_tender_search(
            request,
            profiles=profiles,
            provider_states=states,
            today=date(2026, 7, 16),
        )


def test_request_is_immutable() -> None:
    request = UnifiedTenderSearchRequest("video-profile", "камеры", ("eis",))

    with pytest.raises(FrozenInstanceError):
        request.query_text = "изменено"  # type: ignore[misc]
