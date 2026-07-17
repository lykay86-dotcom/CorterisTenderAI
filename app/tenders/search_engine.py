"""Unified tender search engine with parallel providers and deduplication."""

from __future__ import annotations

from concurrent.futures import (
    Future,
    ThreadPoolExecutor,
    wait,
)
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from time import perf_counter
from typing import TYPE_CHECKING, Iterable, Mapping, Sequence

from app.tenders.models import (
    TenderCustomer,
    TenderDocument,
    TenderMoney,
    TenderProcedureType,
    TenderStatus,
    UnifiedTender,
)

if TYPE_CHECKING:
    from app.tenders.collector.normalizer import TenderNormalizer
from app.tenders.provider_base import (
    ProviderCapabilityError,
    ProviderNotConfiguredError,
    TenderProviderError,
    TenderSearchQuery,
    TenderSearchResult,
)
from app.tenders.provider_registry import (
    RegisteredProvider,
    TenderProviderRegistry,
)


class ProviderSearchStatus(StrEnum):
    SUCCESS = "success"
    EMPTY = "empty"
    NOT_CONFIGURED = "not_configured"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class ProviderSearchOutcome:
    provider_id: str
    display_name: str
    status: ProviderSearchStatus
    elapsed_ms: int
    item_count: int = 0
    warnings: tuple[str, ...] = ()
    error_type: str = ""
    error_message: str = ""

    @property
    def successful(self) -> bool:
        return self.status in {
            ProviderSearchStatus.SUCCESS,
            ProviderSearchStatus.EMPTY,
        }


@dataclass(frozen=True, slots=True)
class AggregatedTenderSearchResult:
    items: tuple[UnifiedTender, ...]
    outcomes: tuple[ProviderSearchOutcome, ...]
    raw_item_count: int
    duplicate_count: int
    provider_count: int
    completed_provider_count: int
    started_at: str
    completed_at: str
    elapsed_ms: int

    @property
    def successful_provider_ids(self) -> tuple[str, ...]:
        return tuple(outcome.provider_id for outcome in self.outcomes if outcome.successful)

    @property
    def failed_provider_ids(self) -> tuple[str, ...]:
        return tuple(
            outcome.provider_id
            for outcome in self.outcomes
            if outcome.status
            in {
                ProviderSearchStatus.FAILED,
                ProviderSearchStatus.NOT_CONFIGURED,
                ProviderSearchStatus.TIMED_OUT,
                ProviderSearchStatus.UNSUPPORTED,
            }
        )

    @property
    def has_partial_failures(self) -> bool:
        return bool(self.failed_provider_ids)

    @property
    def is_empty(self) -> bool:
        return not self.items


@dataclass(frozen=True, slots=True)
class _ProviderExecution:
    entry: RegisteredProvider
    result: TenderSearchResult | None
    outcome: ProviderSearchOutcome


class TenderSearchEngine:
    """Search enabled providers and return deterministic merged results."""

    def __init__(
        self,
        registry: TenderProviderRegistry,
        *,
        max_workers: int = 6,
        timeout_seconds: float = 30.0,
        normalizer: TenderNormalizer | None = None,
    ) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        self.registry = registry
        self.max_workers = int(max_workers)
        self.timeout_seconds = float(timeout_seconds)
        if normalizer is None:
            from app.tenders.collector.normalizer import TenderNormalizer

            normalizer = TenderNormalizer()
        self.normalizer = normalizer

    def search(
        self,
        query: TenderSearchQuery,
        *,
        provider_ids: Sequence[str] | None = None,
        include_disabled: bool = False,
        parallel: bool = True,
    ) -> AggregatedTenderSearchResult:
        started = datetime.now()
        started_counter = perf_counter()
        entries = self._select_entries(
            provider_ids=provider_ids,
            include_disabled=include_disabled,
        )

        if parallel and entries:
            executions = self._search_parallel(entries, query)
        else:
            executions = tuple(self._execute_provider(entry, query) for entry in entries)

        raw_items: list[UnifiedTender] = []
        outcomes: list[ProviderSearchOutcome] = []
        for execution in executions:
            outcomes.append(execution.outcome)
            if execution.result is not None:
                raw_items.extend(
                    item.tender for item in self.normalizer.normalize_many(execution.result.items)
                )

        merged_items = self._deduplicate(
            raw_items,
            provider_priorities={entry.id: entry.priority for entry in entries},
        )

        completed = datetime.now()
        elapsed_ms = max(
            0,
            int((perf_counter() - started_counter) * 1000),
        )
        return AggregatedTenderSearchResult(
            items=tuple(merged_items),
            outcomes=tuple(outcomes),
            raw_item_count=len(raw_items),
            duplicate_count=len(raw_items) - len(merged_items),
            provider_count=len(entries),
            completed_provider_count=sum(
                1 for outcome in outcomes if outcome.status != ProviderSearchStatus.TIMED_OUT
            ),
            started_at=started.isoformat(timespec="seconds"),
            completed_at=completed.isoformat(timespec="seconds"),
            elapsed_ms=elapsed_ms,
        )

    def _search_parallel(
        self,
        entries: Sequence[RegisteredProvider],
        query: TenderSearchQuery,
    ) -> tuple[_ProviderExecution, ...]:
        executor = ThreadPoolExecutor(
            max_workers=min(self.max_workers, len(entries)),
            thread_name_prefix="TenderProvider",
        )
        future_map: dict[
            Future[_ProviderExecution],
            RegisteredProvider,
        ] = {
            executor.submit(
                self._execute_provider,
                entry,
                query,
            ): entry
            for entry in entries
        }

        done, pending = wait(
            future_map,
            timeout=self.timeout_seconds,
        )

        execution_by_id: dict[str, _ProviderExecution] = {}
        for future in done:
            entry = future_map[future]
            try:
                execution_by_id[entry.id] = future.result()
            except Exception as exc:
                execution_by_id[entry.id] = _ProviderExecution(
                    entry=entry,
                    result=None,
                    outcome=ProviderSearchOutcome(
                        provider_id=entry.id,
                        display_name=(entry.provider.descriptor.display_name),
                        status=ProviderSearchStatus.FAILED,
                        elapsed_ms=0,
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                    ),
                )

        for future in pending:
            entry = future_map[future]
            future.cancel()
            execution_by_id[entry.id] = _ProviderExecution(
                entry=entry,
                result=None,
                outcome=ProviderSearchOutcome(
                    provider_id=entry.id,
                    display_name=(entry.provider.descriptor.display_name),
                    status=ProviderSearchStatus.TIMED_OUT,
                    elapsed_ms=int(self.timeout_seconds * 1000),
                    error_type="TimeoutError",
                    error_message=(f"Провайдер не завершил поиск за {self.timeout_seconds:g} сек."),
                ),
            )

        executor.shutdown(wait=False, cancel_futures=True)

        return tuple(execution_by_id[entry.id] for entry in entries)

    @staticmethod
    def _execute_provider(
        entry: RegisteredProvider,
        query: TenderSearchQuery,
    ) -> _ProviderExecution:
        started = perf_counter()
        provider = entry.provider
        descriptor = provider.descriptor

        try:
            result = provider.search(query)
        except ProviderNotConfiguredError as exc:
            return _ProviderExecution(
                entry=entry,
                result=None,
                outcome=ProviderSearchOutcome(
                    provider_id=entry.id,
                    display_name=descriptor.display_name,
                    status=ProviderSearchStatus.NOT_CONFIGURED,
                    elapsed_ms=_elapsed_ms(started),
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                ),
            )
        except ProviderCapabilityError as exc:
            return _ProviderExecution(
                entry=entry,
                result=None,
                outcome=ProviderSearchOutcome(
                    provider_id=entry.id,
                    display_name=descriptor.display_name,
                    status=ProviderSearchStatus.UNSUPPORTED,
                    elapsed_ms=_elapsed_ms(started),
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                ),
            )
        except TenderProviderError as exc:
            return _ProviderExecution(
                entry=entry,
                result=None,
                outcome=ProviderSearchOutcome(
                    provider_id=entry.id,
                    display_name=descriptor.display_name,
                    status=ProviderSearchStatus.FAILED,
                    elapsed_ms=_elapsed_ms(started),
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                ),
            )
        except Exception as exc:
            return _ProviderExecution(
                entry=entry,
                result=None,
                outcome=ProviderSearchOutcome(
                    provider_id=entry.id,
                    display_name=descriptor.display_name,
                    status=ProviderSearchStatus.FAILED,
                    elapsed_ms=_elapsed_ms(started),
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                ),
            )

        status = ProviderSearchStatus.SUCCESS if result.items else ProviderSearchStatus.EMPTY
        return _ProviderExecution(
            entry=entry,
            result=result,
            outcome=ProviderSearchOutcome(
                provider_id=entry.id,
                display_name=descriptor.display_name,
                status=status,
                elapsed_ms=_elapsed_ms(started),
                item_count=len(result.items),
                warnings=result.warnings,
            ),
        )

    def _select_entries(
        self,
        *,
        provider_ids: Sequence[str] | None,
        include_disabled: bool,
    ) -> tuple[RegisteredProvider, ...]:
        registered = self.registry.list_registered()

        if provider_ids is None:
            return tuple(entry for entry in registered if include_disabled or entry.enabled)

        requested = tuple(
            dict.fromkeys(
                provider_id.strip() for provider_id in provider_ids if provider_id.strip()
            )
        )
        registered_by_id = {entry.id: entry for entry in registered}
        unknown = [provider_id for provider_id in requested if provider_id not in registered_by_id]
        if unknown:
            raise KeyError("Unknown tender providers: " + ", ".join(unknown))

        requested_set = set(requested)
        return tuple(
            entry
            for entry in registered
            if entry.id in requested_set and (include_disabled or entry.enabled)
        )

    @classmethod
    def _deduplicate(
        cls,
        items: Iterable[UnifiedTender],
        *,
        provider_priorities: Mapping[str, int],
    ) -> list[UnifiedTender]:
        merged_by_cross_key: dict[str, UnifiedTender] = {}
        order: list[str] = []

        for item in items:
            key = item.cross_source_key or item.identity_key
            if key not in merged_by_cross_key:
                merged_by_cross_key[key] = cls._with_provenance(
                    item,
                    sources=(item.source.value,),
                    identities=(item.identity_key,),
                )
                order.append(key)
                continue

            current = merged_by_cross_key[key]
            merged_by_cross_key[key] = cls._merge_tenders(
                current,
                item,
                provider_priorities=provider_priorities,
            )

        return [merged_by_cross_key[key] for key in order]

    @classmethod
    def _merge_tenders(
        cls,
        left: UnifiedTender,
        right: UnifiedTender,
        *,
        provider_priorities: Mapping[str, int],
    ) -> UnifiedTender:
        primary, secondary = cls._choose_primary(
            left,
            right,
            provider_priorities=provider_priorities,
        )

        metadata = dict(secondary.raw_metadata)
        metadata.update(primary.raw_metadata)

        sources = _ordered_unique(
            (
                *_metadata_values(
                    left.raw_metadata,
                    "aggregated_sources",
                ),
                left.source.value,
                *_metadata_values(
                    right.raw_metadata,
                    "aggregated_sources",
                ),
                right.source.value,
            )
        )
        identities = _ordered_unique(
            (
                *_metadata_values(
                    left.raw_metadata,
                    "aggregated_identities",
                ),
                left.identity_key,
                *_metadata_values(
                    right.raw_metadata,
                    "aggregated_identities",
                ),
                right.identity_key,
            )
        )
        metadata["aggregated_sources"] = sources
        metadata["aggregated_identities"] = identities
        metadata["duplicate_count"] = max(
            1,
            len(identities) - 1,
        )

        return UnifiedTender(
            source=primary.source,
            external_id=primary.external_id,
            procurement_number=primary.procurement_number,
            title=_prefer_text(primary.title, secondary.title),
            customer=cls._merge_customer(
                primary.customer,
                secondary.customer,
            ),
            source_url=primary.source_url,
            published_at=(primary.published_at or secondary.published_at),
            application_deadline=(primary.application_deadline or secondary.application_deadline),
            execution_deadline=(primary.execution_deadline or secondary.execution_deadline),
            price=cls._merge_money(
                primary.price,
                secondary.price,
            ),
            status=cls._prefer_status(
                primary.status,
                secondary.status,
            ),
            procedure_type=cls._prefer_procedure(
                primary.procedure_type,
                secondary.procedure_type,
            ),
            law=_prefer_text(primary.law, secondary.law),
            region=_prefer_text(
                primary.region,
                secondary.region,
            ),
            description=_prefer_text(
                primary.description,
                secondary.description,
            ),
            classification_codes=_ordered_unique(
                (
                    *primary.classification_codes,
                    *secondary.classification_codes,
                )
            ),
            tags=_ordered_unique((*primary.tags, *secondary.tags)),
            documents=cls._merge_documents(
                primary.documents,
                secondary.documents,
            ),
            raw_metadata=metadata,
        )

    @classmethod
    def _choose_primary(
        cls,
        left: UnifiedTender,
        right: UnifiedTender,
        *,
        provider_priorities: Mapping[str, int],
    ) -> tuple[UnifiedTender, UnifiedTender]:
        left_priority = provider_priorities.get(
            left.source.value,
            10_000,
        )
        right_priority = provider_priorities.get(
            right.source.value,
            10_000,
        )

        if left_priority != right_priority:
            return (left, right) if left_priority < right_priority else (right, left)

        left_score = cls._richness_score(left)
        right_score = cls._richness_score(right)
        return (left, right) if left_score >= right_score else (right, left)

    @staticmethod
    def _richness_score(item: UnifiedTender) -> int:
        score = 0
        score += 3 if item.price is not None else 0
        score += 2 if item.published_at is not None else 0
        score += 2 if item.application_deadline is not None else 0
        score += 2 if item.description.strip() else 0
        score += 1 if item.region.strip() else 0
        score += 1 if item.law.strip() else 0
        score += len(item.documents) * 2
        score += len(item.tags)
        score += len(item.classification_codes)
        return score

    @staticmethod
    def _merge_customer(
        primary: TenderCustomer,
        secondary: TenderCustomer,
    ) -> TenderCustomer:
        return TenderCustomer(
            name=_prefer_text(primary.name, secondary.name),
            inn=_prefer_text(primary.inn, secondary.inn),
            kpp=_prefer_text(primary.kpp, secondary.kpp),
            region=_prefer_text(
                primary.region,
                secondary.region,
            ),
            address=_prefer_text(
                primary.address,
                secondary.address,
            ),
        )

    @staticmethod
    def _merge_money(
        primary: TenderMoney | None,
        secondary: TenderMoney | None,
    ) -> TenderMoney | None:
        if primary is None:
            return secondary
        if secondary is None:
            return primary

        if primary.amount == 0 and secondary.amount > 0:
            return secondary
        return TenderMoney(
            amount=primary.amount,
            currency=(primary.currency or secondary.currency),
            includes_vat=(
                primary.includes_vat if primary.includes_vat is not None else secondary.includes_vat
            ),
        )

    @staticmethod
    def _prefer_status(
        primary: TenderStatus,
        secondary: TenderStatus,
    ) -> TenderStatus:
        if primary == TenderStatus.UNKNOWN:
            return secondary
        return primary

    @staticmethod
    def _prefer_procedure(
        primary: TenderProcedureType,
        secondary: TenderProcedureType,
    ) -> TenderProcedureType:
        if primary == TenderProcedureType.UNKNOWN:
            return secondary
        return primary

    @staticmethod
    def _merge_documents(
        primary: Sequence[TenderDocument],
        secondary: Sequence[TenderDocument],
    ) -> tuple[TenderDocument, ...]:
        result: list[TenderDocument] = []
        seen: set[str] = set()

        for document in (*primary, *secondary):
            key = (
                document.checksum_sha256.strip().casefold()
                or document.url.strip().casefold()
                or document.id.strip().casefold()
            )
            if key in seen:
                continue
            seen.add(key)
            result.append(document)
        return tuple(result)

    @staticmethod
    def _with_provenance(
        item: UnifiedTender,
        *,
        sources: tuple[str, ...],
        identities: tuple[str, ...],
    ) -> UnifiedTender:
        metadata = dict(item.raw_metadata)
        metadata["aggregated_sources"] = sources
        metadata["aggregated_identities"] = identities
        metadata["duplicate_count"] = 0
        return UnifiedTender(
            source=item.source,
            external_id=item.external_id,
            procurement_number=item.procurement_number,
            title=item.title,
            customer=item.customer,
            source_url=item.source_url,
            published_at=item.published_at,
            application_deadline=item.application_deadline,
            execution_deadline=item.execution_deadline,
            price=item.price,
            status=item.status,
            procedure_type=item.procedure_type,
            law=item.law,
            region=item.region,
            description=item.description,
            classification_codes=item.classification_codes,
            tags=item.tags,
            documents=item.documents,
            raw_metadata=metadata,
        )


def _elapsed_ms(started: float) -> int:
    return max(0, int((perf_counter() - started) * 1000))


def _prefer_text(primary: str, secondary: str) -> str:
    first = primary.strip()
    second = secondary.strip()
    if not first:
        return second
    if not second:
        return first
    return first if len(first) >= len(second) else second


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value).strip()
        if not normalized:
            continue
        identity = normalized.casefold()
        if identity in seen:
            continue
        seen.add(identity)
        result.append(normalized)
    return tuple(result)


def _metadata_values(
    metadata: Mapping[str, object],
    key: str,
) -> tuple[str, ...]:
    value = metadata.get(key, ())
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (tuple, list, set)):
        return tuple(str(item) for item in value)
    return ()


__all__ = [
    "AggregatedTenderSearchResult",
    "ProviderSearchOutcome",
    "ProviderSearchStatus",
    "TenderSearchEngine",
]
