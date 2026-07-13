"""Collector-specific immutable domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping

from app.tenders.models import UnifiedTender


class TenderAliasType(StrEnum):
    EIS_NUMBER = "eis_number"
    PROCUREMENT_NUMBER = "procurement_number"
    PLATFORM_NUMBER = "platform_number"
    SOURCE_EXTERNAL_ID = "source_external_id"
    COMPOSITE = "composite"
    CONTENT = "content"


@dataclass(frozen=True, slots=True)
class TenderIdentityAlias:
    key: str
    alias_type: TenderAliasType
    strength: int

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("TenderIdentityAlias.key must not be empty")
        if not 0 <= self.strength <= 100:
            raise ValueError("alias strength must be between 0 and 100")


@dataclass(frozen=True, slots=True)
class NormalizedTender:
    tender: UnifiedTender
    canonical_key: str
    aliases: tuple[TenderIdentityAlias, ...]
    normalized_title: str
    normalized_customer: str
    normalized_customer_inn: str
    normalized_procurement_number: str
    content_hash: str
    duplicate_hash: str
    completeness_score: int

    def __post_init__(self) -> None:
        if not self.canonical_key.strip():
            raise ValueError("canonical_key must not be empty")
        if not self.aliases:
            raise ValueError("NormalizedTender.aliases must not be empty")
        if not 0 <= self.completeness_score <= 100:
            raise ValueError("completeness_score must be between 0 and 100")

    @property
    def alias_keys(self) -> tuple[str, ...]:
        return tuple(alias.key for alias in self.aliases)


class DeduplicationMatchLevel(StrEnum):
    SINGLE = "single"
    EIS_NUMBER = "eis_number"
    PROCUREMENT_NUMBER = "procurement_number"
    PLATFORM_NUMBER = "platform_number"
    SOURCE_EXTERNAL_ID = "source_external_id"
    COMPOSITE = "composite"
    CONTENT = "content"


@dataclass(frozen=True, slots=True)
class DeduplicationGroup:
    canonical_key: str
    item: NormalizedTender
    source_items: tuple[NormalizedTender, ...]
    match_levels: tuple[DeduplicationMatchLevel, ...] = ()

    @property
    def duplicate_count(self) -> int:
        return max(0, len(self.source_items) - 1)


@dataclass(frozen=True, slots=True)
class DeduplicationResult:
    items: tuple[NormalizedTender, ...]
    groups: tuple[DeduplicationGroup, ...]
    raw_count: int

    @property
    def merged_count(self) -> int:
        return len(self.items)

    @property
    def duplicate_count(self) -> int:
        return max(0, self.raw_count - self.merged_count)


class TenderObservationStatus(StrEnum):
    NEW = "new"
    UNCHANGED = "unchanged"
    CHANGED = "changed"


class CollectionRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class CollectionPersistenceSummary:
    run_id: str
    new_count: int
    unchanged_count: int
    changed_count: int
    merged_count: int
    duplicate_count: int
    change_count: int
    version_count: int
    alias_conflict_count: int = 0
    ranked_count: int = 0
    recommended_count: int = 0
    manual_review_count: int = 0
    possible_count: int = 0
    not_recommended_count: int = 0
    verification_run_id: str = ""
    verified_field_count: int = 0
    conflict_count: int = 0
    unresolved_conflict_count: int = 0
    verification_incomplete_count: int = 0
    stale_count: int = 0
    due_soon_count: int = 0
    expired_count: int = 0
    reverification_due_count: int = 0

    @property
    def observed_count(self) -> int:
        return self.new_count + self.unchanged_count + self.changed_count


@dataclass(frozen=True, slots=True)
class CollectionRunRecord:
    run_id: str
    status: CollectionRunStatus
    started_at: str
    completed_at: str
    query_json: str
    requested_provider_ids: tuple[str, ...]
    raw_count: int
    merged_count: int
    duplicate_count: int
    new_count: int
    unchanged_count: int
    changed_count: int
    provider_count: int
    successful_provider_count: int
    failed_provider_count: int
    elapsed_ms: int
    error_type: str = ""
    error_message: str = ""


@dataclass(frozen=True, slots=True)
class CollectorSourceReference:
    registry_key: str
    source: str
    external_id: str
    source_url: str
    first_seen_at: str
    last_seen_at: str
    content_hash: str
    active: bool


@dataclass(frozen=True, slots=True)
class CollectorRunResult:
    run_id: str
    status: CollectionRunStatus
    batch_result: object
    deduplication: DeduplicationResult
    persistence: CollectionPersistenceSummary
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)


__all__ = [
    "CollectionPersistenceSummary",
    "CollectionRunRecord",
    "CollectionRunStatus",
    "CollectorRunResult",
    "CollectorSourceReference",
    "DeduplicationGroup",
    "DeduplicationMatchLevel",
    "DeduplicationResult",
    "NormalizedTender",
    "TenderAliasType",
    "TenderIdentityAlias",
    "TenderObservationStatus",
]
