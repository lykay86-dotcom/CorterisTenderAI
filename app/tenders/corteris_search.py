"""Search service combining provider results with Corteris filtering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.tenders.corteris_filter import (
    CorterisTenderFilter,
    CorterisTenderFilterResult,
    TenderFilterOptions,
)
from app.tenders.provider_base import TenderSearchQuery
from app.tenders.search_engine import (
    AggregatedTenderSearchResult,
    TenderSearchEngine,
)


@dataclass(frozen=True, slots=True)
class CorterisTenderSearchResult:
    provider_result: AggregatedTenderSearchResult
    filter_result: CorterisTenderFilterResult

    @property
    def tenders(self):
        return self.filter_result.tenders

    @property
    def found_count(self) -> int:
        return self.provider_result.raw_item_count

    @property
    def relevant_count(self) -> int:
        return self.filter_result.accepted_count


class CorterisTenderSearchService:
    """Run provider search, then classify, filter and rank results."""

    def __init__(
        self,
        engine: TenderSearchEngine,
        tender_filter: CorterisTenderFilter | None = None,
    ) -> None:
        self.engine = engine
        self.tender_filter = tender_filter or CorterisTenderFilter()

    def search(
        self,
        query: TenderSearchQuery,
        *,
        filter_options: TenderFilterOptions | None = None,
        provider_ids: Sequence[str] | None = None,
        include_disabled: bool = False,
        parallel: bool = True,
    ) -> CorterisTenderSearchResult:
        provider_result = self.engine.search(
            query,
            provider_ids=provider_ids,
            include_disabled=include_disabled,
            parallel=parallel,
        )
        filter_result = self.tender_filter.filter(
            provider_result.items,
            options=filter_options,
        )
        return CorterisTenderSearchResult(
            provider_result=provider_result,
            filter_result=filter_result,
        )


__all__ = [
    "CorterisTenderSearchResult",
    "CorterisTenderSearchService",
]
