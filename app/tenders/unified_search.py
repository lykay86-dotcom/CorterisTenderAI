"""Pure request boundary for the RM-128 unified tender search."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum

from app.tenders.collector.provider_control import ProviderDisplayState
from app.tenders.provider_base import TenderSearchQuery
from app.tenders.search_profiles import (
    SearchProfileRuntimeQueryPolicy,
    TenderSearchProfile,
)


class UnifiedTenderSearchValidationError(ValueError):
    """Bounded validation failure safe to display in the unified-search UI."""

    def __init__(self, public_message: str) -> None:
        normalized = " ".join(str(public_message).split())
        super().__init__(normalized[:300])
        self.public_message = normalized[:300]


class SearchProfileExecutionMode(StrEnum):
    """Auditable interpretation of transient runtime query text."""

    SAVED_PROFILE = "saved_profile"
    KEYWORD_OVERRIDE = "keyword_override"


@dataclass(frozen=True, slots=True)
class UnifiedTenderSearchRequest:
    """One immutable user request before profile/provider resolution."""

    profile_id: str
    query_text: str = ""
    provider_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ResolvedUnifiedTenderSearch:
    """Validated request ready for the existing Collector session."""

    profile: TenderSearchProfile
    query: TenderSearchQuery
    provider_ids: tuple[str, ...]
    execution_mode: SearchProfileExecutionMode


def resolve_unified_tender_search(
    request: UnifiedTenderSearchRequest,
    *,
    profiles: Iterable[TenderSearchProfile],
    provider_states: Iterable[ProviderDisplayState],
    today: date | None = None,
) -> ResolvedUnifiedTenderSearch:
    """Resolve snapshots without repository, persistence, UI or network access."""

    profile_id = str(request.profile_id).strip().casefold()
    if not profile_id:
        raise UnifiedTenderSearchValidationError("Выберите сохранённый профиль поиска.")

    profile_map = {profile.id.strip().casefold(): profile for profile in profiles}
    profile = profile_map.get(profile_id)
    if profile is None:
        raise UnifiedTenderSearchValidationError("Выбранный профиль не найден.")
    if not profile.enabled:
        raise UnifiedTenderSearchValidationError("Выбранный профиль отключён.")

    normalized_provider_ids = _normalize_provider_ids(request.provider_ids)
    if not normalized_provider_ids:
        raise UnifiedTenderSearchValidationError("Выберите хотя бы один доступный источник.")

    state_map = {
        state.provider_id.strip().casefold(): state
        for state in provider_states
        if state.provider_id.strip()
    }
    for provider_id in normalized_provider_ids:
        state = state_map.get(provider_id)
        if state is None:
            raise UnifiedTenderSearchValidationError(
                f"Источник «{provider_id}» не найден или его состояние устарело."
            )
        if not state.enabled:
            raise UnifiedTenderSearchValidationError(f"Источник «{provider_id}» отключён.")

    query = profile.to_search_query(today=today)
    query_text = " ".join(str(request.query_text).split())
    if profile.runtime_query_policy is not (
        SearchProfileRuntimeQueryPolicy.REPLACE_KEYWORDS_IF_PRESENT
    ):
        raise UnifiedTenderSearchValidationError(
            "Политика текста запроса выбранного профиля не поддерживается."
        )
    execution_mode = SearchProfileExecutionMode.SAVED_PROFILE
    if query_text:
        query = replace(query, keywords=(query_text,))
        execution_mode = SearchProfileExecutionMode.KEYWORD_OVERRIDE

    return ResolvedUnifiedTenderSearch(
        profile=profile,
        query=query,
        provider_ids=normalized_provider_ids,
        execution_mode=execution_mode,
    )


def _normalize_provider_ids(provider_ids: Iterable[object]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for item in provider_ids:
        provider_id = str(item).strip().casefold()
        if not provider_id or provider_id in seen:
            continue
        seen.add(provider_id)
        normalized.append(provider_id)
    return tuple(normalized)


__all__ = [
    "ResolvedUnifiedTenderSearch",
    "SearchProfileExecutionMode",
    "UnifiedTenderSearchRequest",
    "UnifiedTenderSearchValidationError",
    "resolve_unified_tender_search",
]
