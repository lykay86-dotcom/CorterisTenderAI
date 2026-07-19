"""Immutable, Qt-free RM-149 tender detail contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final


DETAIL_CONTRACT_VERSION: Final = "tender-detail-v1"
CARD_CONTRACT_VERSION: Final = "tender-card-v1"
PRIMARY_ACTION_POLICY_VERSION: Final = "tender-primary-action-v1"

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


def _bounded_text(value: str, field_name: str, *, limit: int = 4096) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be text")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    if len(normalized) > limit:
        raise ValueError(f"{field_name} is too long")
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        raise ValueError(f"{field_name} contains control characters")
    if any(character in _BIDI_CONTROLS for character in normalized):
        raise ValueError(f"{field_name} contains bidi controls")
    return normalized


def _aware(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


class TenderIdentityKind(StrEnum):
    REGISTRY = "registry"
    LEGACY_ORM = "legacy_orm"


class TenderDetailState(StrEnum):
    LOADING = "loading"
    READY = "ready"
    EMPTY = "empty"
    PARTIAL = "partial"
    STALE = "stale"
    CONFLICTED = "conflicted"
    NOT_FOUND = "not_found"
    ERROR = "error"
    CLOSED = "closed"


class TenderValueState(StrEnum):
    AVAILABLE = "available"
    MISSING = "missing"
    INVALID = "invalid"
    CONFLICTED = "conflicted"
    UNSUPPORTED = "unsupported"
    STALE = "stale"
    NOT_LOADED = "not_loaded"


class TenderSeverity(StrEnum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    CRITICAL = "critical"


class TenderActionState(StrEnum):
    AVAILABLE = "available"
    DISABLED = "disabled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CONTEXT_REQUIRED = "context_required"
    STALE = "stale"
    CONFLICTED = "conflicted"
    UNSUPPORTED = "unsupported"


class TenderActionRole(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"


@dataclass(frozen=True, slots=True)
class TenderIdentity:
    kind: TenderIdentityKind
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, TenderIdentityKind):
            raise TypeError("kind must be TenderIdentityKind")
        object.__setattr__(self, "value", _bounded_text(self.value, "identity", limit=256))

    @property
    def public_id(self) -> str:
        return f"{self.kind.value}:{self.value}"


@dataclass(frozen=True, slots=True)
class TenderFact:
    stable_id: str
    label: str
    value: str
    accessible_value: str
    state: TenderValueState = TenderValueState.AVAILABLE
    source_timestamp: str = ""


@dataclass(frozen=True, slots=True)
class TenderStatusItem:
    stable_id: str
    label: str
    value: str
    severity: TenderSeverity
    explanation: str
    source_timestamp: str = ""


@dataclass(frozen=True, slots=True)
class TenderCriticalWarning:
    stable_id: str
    title: str
    detail: str
    severity: TenderSeverity = TenderSeverity.CRITICAL
    blocking: bool = True


@dataclass(frozen=True, slots=True)
class TenderDecisionSummary:
    recommendation: str
    recommendation_text: str
    score: int | None
    confidence: float | None
    summary: str
    decision_id: str
    decided_at: str
    policy_version: str
    evidence: tuple[str, ...]
    missing: tuple[str, ...]
    actions: tuple[str, ...]
    input_fingerprint: str


@dataclass(frozen=True, slots=True)
class TenderActionSpec:
    action_id: str
    label: str
    state: TenderActionState
    reason: str
    identity: TenderIdentity
    required_capability: str
    role: TenderActionRole
    destructive: bool
    snapshot_fingerprint: str
    source_revision: str
    focus_return_token: str
    accessible_description: str


@dataclass(frozen=True, slots=True)
class TenderHistoryItem:
    stable_id: str
    occurred_at: str
    title: str
    detail: str
    accepted: bool


@dataclass(frozen=True, slots=True)
class TenderActionValidation:
    allowed: bool
    reason_code: str
    state: TenderDetailState


@dataclass(frozen=True, slots=True)
class TenderDetailSnapshot:
    identity: TenderIdentity
    generated_at: datetime
    source_revision: str
    state: TenderDetailState
    title: str
    source: str
    source_url: str
    facts: tuple[TenderFact, ...]
    statuses: tuple[TenderStatusItem, ...]
    critical_warnings: tuple[TenderCriticalWarning, ...]
    decision: TenderDecisionSummary | None
    actions: tuple[TenderActionSpec, ...]
    history: tuple[TenderHistoryItem, ...]
    fingerprint: str
    accessible_summary: str
    reason_code: str = ""
    missing_sections: tuple[str, ...] = ()
    contract_version: str = DETAIL_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _aware(self.generated_at, "generated_at")
        if self.contract_version != DETAIL_CONTRACT_VERSION:
            raise ValueError("unsupported tender detail contract")
        if sum(action.role is TenderActionRole.PRIMARY for action in self.actions) != 1:
            raise ValueError("a tender detail snapshot must have exactly one primary action")

    @property
    def primary_action(self) -> TenderActionSpec:
        return next(action for action in self.actions if action.role is TenderActionRole.PRIMARY)

    def fact(self, stable_id: str) -> TenderFact:
        return next(item for item in self.facts if item.stable_id == stable_id)

    def status(self, stable_id: str) -> TenderStatusItem:
        return next(item for item in self.statuses if item.stable_id == stable_id)


@dataclass(frozen=True, slots=True)
class TenderCardProjection:
    identity: TenderIdentity
    title: str
    source: str
    lifecycle: str
    deadline: str
    price: str
    price_accessible: str
    verification: str
    freshness: str
    conflicts: str
    decision: str
    critical_warning: str
    primary_action: TenderActionSpec
    snapshot_fingerprint: str
    accessible_summary: str
    contract_version: str = CARD_CONTRACT_VERSION


__all__ = [
    "CARD_CONTRACT_VERSION",
    "DETAIL_CONTRACT_VERSION",
    "PRIMARY_ACTION_POLICY_VERSION",
    "TenderActionRole",
    "TenderActionSpec",
    "TenderActionState",
    "TenderActionValidation",
    "TenderCardProjection",
    "TenderCriticalWarning",
    "TenderDecisionSummary",
    "TenderDetailSnapshot",
    "TenderDetailState",
    "TenderFact",
    "TenderHistoryItem",
    "TenderIdentity",
    "TenderIdentityKind",
    "TenderSeverity",
    "TenderStatusItem",
    "TenderValueState",
]
