"""Run saved tender-search profiles through the Corteris pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from app.tenders.corteris_search import (
    CorterisTenderSearchResult,
    CorterisTenderSearchService,
)
from app.tenders.search_profile_repository import (
    TenderSearchProfileRepository,
)
from app.tenders.search_profiles import TenderSearchProfile


@dataclass(frozen=True, slots=True)
class TenderSearchProfileRun:
    profile: TenderSearchProfile
    result: CorterisTenderSearchResult
    executed_at: str


class TenderSearchProfileRunner:
    """Resolve a saved profile and execute its provider/filter settings."""

    def __init__(
        self,
        repository: TenderSearchProfileRepository,
        search_service: CorterisTenderSearchService,
    ) -> None:
        self.repository = repository
        self.search_service = search_service

    def run(
        self,
        profile_id: str,
        *,
        today: date | None = None,
        page: int = 1,
        parallel: bool = True,
    ) -> TenderSearchProfileRun:
        profile = self.repository.get(profile_id)
        if not profile.enabled:
            raise ValueError(
                f"Search profile is disabled: {profile.id}"
            )

        result = self.search_service.search(
            profile.to_search_query(
                today=today,
                page=page,
            ),
            filter_options=profile.to_filter_options(),
            provider_ids=(
                profile.provider_ids
                if profile.provider_ids
                else None
            ),
            include_disabled=(
                profile.include_disabled_providers
            ),
            parallel=parallel,
        )

        return TenderSearchProfileRun(
            profile=profile,
            result=result,
            executed_at=datetime.now(timezone.utc).isoformat(
                timespec="seconds"
            ),
        )


__all__ = [
    "TenderSearchProfileRun",
    "TenderSearchProfileRunner",
]
