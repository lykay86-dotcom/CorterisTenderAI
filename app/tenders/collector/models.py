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


class NormalizationDiagnosticSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class NormalizationDiagnosticCode(StrEnum):
    MISSING_REQUIRED = "missing_required"
    MISSING_OPTIONAL = "missing_optional"
    INVALID_FORMAT = "invalid_format"
    OUT_OF_RANGE = "out_of_range"
    UNSUPPORTED_VALUE = "unsupported_value"
    UNMAPPED_VALUE = "unmapped_value"
    CONFLICTING_VALUES = "conflicting_values"
    LOSSY_TRANSFORM_BLOCKED = "lossy_transform_blocked"
    UNSAFE_URL_REJECTED = "unsafe_url_rejected"
    NAIVE_DATETIME_REJECTED = "naive_datetime_rejected"
    AMBIGUOUS_DATETIME_REJECTED = "ambiguous_datetime_rejected"
    INVALID_MONEY_REJECTED = "invalid_money_rejected"
    RESOURCE_LIMIT_EXCEEDED = "resource_limit_exceeded"


class NormalizationFieldOutcome(StrEnum):
    DIRECT = "direct"
    NORMALIZED = "normalized"
    MISSING = "missing"
    INVALID = "invalid"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class NormalizationDiagnostic:
    code: NormalizationDiagnosticCode
    severity: NormalizationDiagnosticSeverity
    field: str
    source_field: str
    provider_id: str
    message: str
    recoverable: bool

    def __post_init__(self) -> None:
        if not self.field.strip() or not self.provider_id.strip():
            raise ValueError("normalization diagnostic identity is required")
        if len(self.message) > 300:
            raise ValueError("normalization diagnostic message is too long")


@dataclass(frozen=True, slots=True)
class NormalizedFieldProvenance:
    field: str
    source_field: str
    provider_id: str
    transform_id: str
    outcome: NormalizationFieldOutcome
    source_record_id: str
    verified: bool = False

    def __post_init__(self) -> None:
        if not self.field.strip() or not self.provider_id.strip():
            raise ValueError("normalization provenance identity is required")
        if self.verified:
            raise ValueError("normalization provenance cannot assert verification")


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
    diagnostics: tuple[NormalizationDiagnostic, ...]
    provenance: tuple[NormalizedFieldProvenance, ...]
    contract_version: int
    semantic_fingerprint: str

    def __post_init__(self) -> None:
        if not self.canonical_key.strip():
            raise ValueError("canonical_key must not be empty")
        if not self.aliases:
            raise ValueError("NormalizedTender.aliases must not be empty")
        if not 0 <= self.completeness_score <= 100:
            raise ValueError("completeness_score must be between 0 and 100")
        if self.contract_version < 1:
            raise ValueError("normalization contract version must be positive")
        if len(self.semantic_fingerprint) != 64:
            raise ValueError("semantic fingerprint must be a SHA-256 hex digest")

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
    TIMED_OUT = "timed_out"
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
class ProviderRunOutcomeRecord:
    """Safe persisted terminal outcome used by passive source monitoring."""

    run_id: str
    provider_id: str
    status: str
    completed_at: str
    error_code: str
    error_message: str
    item_count: int
    elapsed_ms: int
    page_count: int = 0
    artifact_count: int = 0

    def __post_init__(self) -> None:
        if not self.run_id.strip() or not self.provider_id.strip():
            raise ValueError("provider run outcome identity is required")
        if (
            self.item_count < 0
            or self.elapsed_ms < 0
            or self.page_count < 0
            or self.artifact_count < 0
        ):
            raise ValueError("provider run outcome counters must be non-negative")


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
    "ProviderRunOutcomeRecord",
    "DeduplicationGroup",
    "DeduplicationMatchLevel",
    "DeduplicationResult",
    "NormalizedTender",
    "NormalizationDiagnostic",
    "NormalizationDiagnosticCode",
    "NormalizationDiagnosticSeverity",
    "NormalizationFieldOutcome",
    "NormalizedFieldProvenance",
    "TenderAliasType",
    "TenderIdentityAlias",
    "TenderObservationStatus",
]
