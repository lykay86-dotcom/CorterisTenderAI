"""Qt-free immutable contracts for deterministic tender analytics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import hashlib
import json
import re
import unicodedata


QUERY_CONTRACT_VERSION = "tender-analytics-query-v1"
SNAPSHOT_CONTRACT_VERSION = "tender-analytics-v1"
EVIDENCE_CONTRACT_VERSION = "tender-analytics-evidence-v1"

_SAFE_ID = re.compile(r"^[A-Za-z0-9._:+-]{1,256}$")
_BIDI_CONTROLS = frozenset(
    {
        "\u061c",
        "\u200e",
        "\u200f",
        "\u202a",
        "\u202b",
        "\u202c",
        "\u202d",
        "\u202e",
        "\u2066",
        "\u2067",
        "\u2068",
        "\u2069",
    }
)


class AnalyticsGrain(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class AnalyticsState(StrEnum):
    LOADING = "loading"
    READY = "ready"
    EMPTY = "empty"
    PARTIAL = "partial"
    STALE = "stale"
    CONFLICTED = "conflicted"
    ERROR = "error"
    TOO_LARGE = "too_large"


class AnalyticsEvidenceQuality(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    STALE = "stale"
    CONFLICTED = "conflicted"
    UNKNOWN = "unknown"


def _aware(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


def _safe_id(value: str, field_name: str, *, allow_empty: bool = False) -> str:
    normalized = value.strip().casefold()
    if allow_empty and not normalized:
        return ""
    if not _SAFE_ID.fullmatch(normalized):
        raise ValueError(f"{field_name} is not a safe bounded identifier")
    return normalized


def _normalized_ids(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise TypeError(f"{field_name} must be a tuple")
    return tuple(sorted({_safe_id(value, field_name) for value in values}))


def _safe_text(value: str, field_name: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError(f"{field_name} must be bounded text")
    if any(unicodedata.category(char) == "Cc" or char in _BIDI_CONTROLS for char in value):
        raise ValueError(f"{field_name} contains forbidden control text")
    return value


@dataclass(frozen=True, slots=True)
class AnalyticsInterval:
    start_inclusive: datetime
    end_exclusive: datetime
    timezone_name: str

    def __post_init__(self) -> None:
        _aware(self.start_inclusive, "start_inclusive")
        _aware(self.end_exclusive, "end_exclusive")
        if self.start_inclusive >= self.end_exclusive:
            raise ValueError("start_inclusive must be earlier than end_exclusive")
        if not self.timezone_name.strip() or len(self.timezone_name) > 64:
            raise ValueError("timezone_name must be a bounded explicit timezone")
        _safe_text(self.timezone_name, "timezone_name", maximum=64)
        from app.tenders.analytics.time_contract import resolve_timezone

        resolve_timezone(self.timezone_name)


@dataclass(frozen=True, slots=True)
class TenderAnalyticsQuery:
    interval: AnalyticsInterval
    grain: AnalyticsGrain
    source_ids: tuple[str, ...] = ()
    statuses: tuple[str, ...] = ()
    laws: tuple[str, ...] = ()
    include_archived: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.interval, AnalyticsInterval):
            raise TypeError("interval must be AnalyticsInterval")
        if not isinstance(self.grain, AnalyticsGrain):
            raise TypeError("grain must be AnalyticsGrain")
        if not isinstance(self.include_archived, bool):
            raise TypeError("include_archived must be bool")
        object.__setattr__(self, "source_ids", _normalized_ids(self.source_ids, "source_id"))
        object.__setattr__(self, "statuses", _normalized_ids(self.statuses, "status"))
        object.__setattr__(self, "laws", _normalized_ids(self.laws, "law"))
        allowed_statuses = {
            "published",
            "accepting_applications",
            "applications_closed",
            "review",
            "completed",
            "cancelled",
            "unknown",
        }
        if not set(self.statuses) <= allowed_statuses:
            raise ValueError("statuses contains an unsupported status")

    @property
    def projection(self) -> dict[str, object]:
        from app.tenders.analytics.time_contract import resolve_timezone

        zone = resolve_timezone(self.interval.timezone_name)
        return {
            "contract_version": QUERY_CONTRACT_VERSION,
            "interval_start": self.interval.start_inclusive.astimezone(zone).isoformat(
                timespec="seconds"
            ),
            "interval_end": self.interval.end_exclusive.astimezone(zone).isoformat(
                timespec="seconds"
            ),
            "timezone_name": self.interval.timezone_name,
            "grain": self.grain.value,
            "source_ids": self.source_ids,
            "statuses": self.statuses,
            "laws": self.laws,
            "include_archived": self.include_archived,
        }

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps(
            self.projection,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class AnalyticsTimeBucket:
    bucket_key: str
    start_inclusive: datetime
    end_exclusive: datetime

    def __post_init__(self) -> None:
        _safe_id(self.bucket_key, "bucket_key")
        _aware(self.start_inclusive, "bucket start")
        _aware(self.end_exclusive, "bucket end")
        if self.start_inclusive >= self.end_exclusive:
            raise ValueError("bucket start must be earlier than bucket end")


@dataclass(frozen=True, slots=True)
class AnalyticsMetricDefinition:
    metric_id: str
    version: str
    order: int
    title: str
    unit: str

    def __post_init__(self) -> None:
        _safe_id(self.metric_id, "metric_id")
        _safe_id(self.version, "metric version")
        _safe_text(self.title, "metric title", maximum=160)
        _safe_id(self.unit, "unit")
        if self.order < 0:
            raise ValueError("metric order must be non-negative")


@dataclass(frozen=True, slots=True)
class AnalyticsTenderFact:
    registry_key: str
    source_id: str
    external_id: str
    status: str
    first_seen_at: str
    last_seen_at: str = ""
    published_at: str = ""
    application_deadline: str = ""
    deadline_source_timezone: str = ""
    law: str = ""
    archived: bool = False

    def __post_init__(self) -> None:
        if not self.registry_key.strip() or len(self.registry_key) > 256:
            raise ValueError("registry_key must be bounded and non-empty")
        _safe_text(self.registry_key, "registry_key")
        object.__setattr__(
            self,
            "source_id",
            _safe_id(self.source_id or "unknown", "source_id"),
        )
        if not self.external_id.strip() or len(self.external_id) > 256:
            raise ValueError("external_id must be bounded and non-empty")
        _safe_text(self.external_id, "external_id")


@dataclass(frozen=True, slots=True)
class AnalyticsSourceObservation:
    registry_key: str
    source_id: str
    external_id: str
    first_seen_at: str

    def __post_init__(self) -> None:
        _safe_text(self.registry_key, "registry_key")
        object.__setattr__(self, "source_id", _safe_id(self.source_id, "source_id"))
        _safe_text(self.external_id, "external_id")


@dataclass(frozen=True, slots=True)
class AnalyticsProviderOutcome:
    source_id: str
    run_id: str
    outcome: str
    observed_at: datetime | None
    item_count: int | None
    reason_code: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", _safe_id(self.source_id, "source_id"))
        _safe_id(self.run_id, "run_id")
        _safe_id(self.outcome, "outcome")
        if self.observed_at is not None:
            _aware(self.observed_at, "observed_at")
        if self.item_count is not None and self.item_count < 0:
            raise ValueError("item_count must be non-negative or None")
        if self.reason_code:
            _safe_id(self.reason_code, "reason_code")


@dataclass(frozen=True, slots=True)
class AnalyticsConflict:
    registry_key: str
    field_name: str
    unresolved: bool = True

    def __post_init__(self) -> None:
        _safe_text(self.registry_key, "registry_key")
        object.__setattr__(self, "field_name", _safe_id(self.field_name, "field_name"))


@dataclass(frozen=True, slots=True)
class AnalyticsSourceCoverage:
    source_id: str
    requested: bool
    enabled: bool
    outcome: str
    observed_at: datetime | None
    freshness: str
    item_count: int | None
    reason_code: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", _safe_id(self.source_id, "source_id"))
        _safe_id(self.outcome, "outcome")
        _safe_id(self.freshness, "freshness")
        if self.observed_at is not None:
            _aware(self.observed_at, "coverage observed_at")
        if self.item_count is not None and self.item_count < 0:
            raise ValueError("coverage item_count must be non-negative or None")
        if self.reason_code:
            _safe_id(self.reason_code, "reason_code")


@dataclass(frozen=True, slots=True)
class AnalyticsEvidence:
    quality: AnalyticsEvidenceQuality
    source_ids: tuple[str, ...] = ()
    run_ids: tuple[str, ...] = ()
    contributor_count: int = 0
    missing_count: int = 0
    excluded_count: int = 0
    unknown_time_count: int = 0
    conflict_count: int = 0
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_ids", _normalized_ids(self.source_ids, "source_id"))
        object.__setattr__(self, "run_ids", _normalized_ids(self.run_ids, "run_id"))
        object.__setattr__(
            self,
            "reason_codes",
            _normalized_ids(self.reason_codes, "reason_code"),
        )
        counts = (
            self.contributor_count,
            self.missing_count,
            self.excluded_count,
            self.unknown_time_count,
            self.conflict_count,
        )
        if any(item < 0 for item in counts):
            raise ValueError("evidence counts must be non-negative")


@dataclass(frozen=True, slots=True)
class TenderAnalyticsPoint:
    point_id: str
    bucket_key: str
    bucket_label: str
    value: int
    contributor_ids: tuple[str, ...]
    evidence: AnalyticsEvidence
    bucket_start: datetime | None = None
    bucket_end: datetime | None = None

    def __post_init__(self) -> None:
        _safe_id(self.point_id, "point_id")
        _safe_id(self.bucket_key, "bucket_key")
        _safe_text(self.bucket_label, "bucket_label")
        if self.value < 0:
            raise ValueError("point value must be non-negative")
        if self.contributor_ids != tuple(sorted(set(self.contributor_ids))):
            raise ValueError("contributor_ids must be unique and sorted")


@dataclass(frozen=True, slots=True)
class TenderAnalyticsMetric:
    metric_id: str
    version: str
    title: str
    unit: str
    state: AnalyticsState
    points: tuple[TenderAnalyticsPoint, ...]
    evidence: AnalyticsEvidence

    def __post_init__(self) -> None:
        _safe_id(self.metric_id, "metric_id")
        _safe_id(self.version, "metric version")
        _safe_text(self.title, "metric title", maximum=160)
        _safe_id(self.unit, "unit")
        if not isinstance(self.state, AnalyticsState):
            raise TypeError("metric state must be AnalyticsState")


@dataclass(frozen=True, slots=True)
class TenderAnalyticsSnapshot:
    query: TenderAnalyticsQuery
    generation: int
    as_of: datetime
    state: AnalyticsState
    coverage: tuple[AnalyticsSourceCoverage, ...]
    metrics: tuple[TenderAnalyticsMetric, ...]
    fingerprint: str
    reason_codes: tuple[str, ...] = ()
    contract_version: str = SNAPSHOT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _aware(self.as_of, "as_of")
        if self.generation < 0:
            raise ValueError("generation must be non-negative")
        if not re.fullmatch(r"[0-9a-f]{64}", self.fingerprint):
            raise ValueError("fingerprint must be a SHA-256 hex digest")


@dataclass(frozen=True, slots=True)
class TenderAnalyticsSelection:
    metric_id: str
    point_id: str
    snapshot_fingerprint: str
    contributor_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _safe_id(self.metric_id, "metric_id")
        _safe_id(self.point_id, "point_id")
        if not re.fullmatch(r"[0-9a-f]{64}", self.snapshot_fingerprint):
            raise ValueError("selection fingerprint must be SHA-256")
        if self.contributor_ids != tuple(sorted(set(self.contributor_ids))):
            raise ValueError("selection contributors must be unique and sorted")


__all__ = [
    "EVIDENCE_CONTRACT_VERSION",
    "QUERY_CONTRACT_VERSION",
    "SNAPSHOT_CONTRACT_VERSION",
    "AnalyticsConflict",
    "AnalyticsEvidence",
    "AnalyticsEvidenceQuality",
    "AnalyticsGrain",
    "AnalyticsInterval",
    "AnalyticsMetricDefinition",
    "AnalyticsProviderOutcome",
    "AnalyticsSourceCoverage",
    "AnalyticsSourceObservation",
    "AnalyticsState",
    "AnalyticsTenderFact",
    "AnalyticsTimeBucket",
    "TenderAnalyticsMetric",
    "TenderAnalyticsPoint",
    "TenderAnalyticsQuery",
    "TenderAnalyticsSelection",
    "TenderAnalyticsSnapshot",
]
