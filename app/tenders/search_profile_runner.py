"""Run saved tender-search profiles through the Corteris pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from threading import RLock

from app.tenders.tender_registry import (
    TenderRegistryRepository,
    TenderRegistrySaveSummary,
)

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
        tender_registry: TenderRegistryRepository | None = None,
        *,
        persistence_required: bool = False,
    ) -> None:
        self.repository = repository
        self.search_service = search_service
        self.tender_registry = tender_registry
        self.persistence_required = bool(persistence_required)
        self._persistence_lock = RLock()
        self._last_save_summaries: dict[str, TenderRegistrySaveSummary] = {}
        self._last_persistence_errors: dict[str, str] = {}

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
            raise ValueError(f"Search profile is disabled: {profile.id}")

        result = self.search_service.search(
            profile.to_search_query(
                today=today,
                page=page,
            ),
            filter_options=profile.to_filter_options(),
            provider_ids=(profile.provider_ids if profile.provider_ids else None),
            include_disabled=(profile.include_disabled_providers),
            parallel=parallel,
        )

        run = TenderSearchProfileRun(
            profile=profile,
            result=result,
            executed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        self._persist_run(run)
        return run

    def last_save_summary(
        self,
        profile_id: str,
    ) -> TenderRegistrySaveSummary | None:
        normalized = profile_id.strip().casefold()
        with self._persistence_lock:
            return self._last_save_summaries.get(normalized)

    def last_persistence_error(self, profile_id: str) -> str:
        normalized = profile_id.strip().casefold()
        with self._persistence_lock:
            return self._last_persistence_errors.get(normalized, "")

    def _persist_run(self, run: TenderSearchProfileRun) -> None:
        if self.tender_registry is None:
            return

        profile_id = run.profile.id.strip().casefold()
        try:
            summary = self.tender_registry.record_profile_run(run)
        except Exception as exc:
            with self._persistence_lock:
                self._last_save_summaries.pop(profile_id, None)
                self._last_persistence_errors[profile_id] = f"{type(exc).__name__}: {exc}"
            if self.persistence_required:
                raise
            return

        with self._persistence_lock:
            self._last_save_summaries[profile_id] = summary
            self._last_persistence_errors.pop(profile_id, None)


__all__ = [
    "TenderSearchProfileRun",
    "TenderSearchProfileRunner",
]
