"""Immutable, Qt-free operation feedback contracts."""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
import hashlib
import json
import math
import re
import unicodedata
from typing import Any, ClassVar, Mapping


_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_PHASE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
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


def _validate_token(value: str, *, label: str) -> None:
    if not isinstance(value, str) or not _TOKEN.fullmatch(value):
        raise ValueError(f"{label} must be a bounded opaque token")


def _require_aware(value: datetime, *, label: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class OperationEpisodeId:
    value: str

    def __post_init__(self) -> None:
        _validate_token(self.value, label="episode id")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class DiagnosticCorrelationId:
    value: str

    def __post_init__(self) -> None:
        _validate_token(self.value, label="diagnostic correlation id")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class SafeText:
    """Bounded markup-free text created from an allowlisted source."""

    value: str
    MAX_LENGTH: ClassVar[int] = 512

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise TypeError("safe text must be a string")
        if not self.value or len(self.value) > self.MAX_LENGTH:
            raise ValueError("safe text must be non-empty and bounded")
        if "<" in self.value or ">" in self.value:
            raise ValueError("safe text must not contain markup delimiters")
        if any(
            character in _BIDI_CONTROLS
            or (unicodedata.category(character).startswith("C") and character not in "\n\t")
            for character in self.value
        ):
            raise ValueError("safe text must not contain control or bidi characters")

    def __str__(self) -> str:
        return self.value


class OperationKind(StrEnum):
    TENDER_SEARCH = "tender_search"
    DASHBOARD_REFRESH = "dashboard_refresh"
    SYSTEM_HEALTH = "system_health"
    WORKFLOW_RECOVERY = "workflow_recovery"
    SUPPORT_BUNDLE = "support_bundle"
    DOCUMENT_ANALYSIS = "document_analysis"
    PROVIDER_CHECK = "provider_check"
    NOTIFICATION = "notification"
    GENERIC = "generic"


class OperationState(StrEnum):
    IDLE = "idle"
    QUEUED = "queued"
    RUNNING = "running"
    PARTIAL = "partial"
    CANCELLING = "cancelling"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    CLOSED = "closed"

    @property
    def result_terminal(self) -> bool:
        return self in {
            OperationState.PARTIAL,
            OperationState.SUCCEEDED,
            OperationState.FAILED,
            OperationState.TIMED_OUT,
            OperationState.CANCELLED,
        }

    @property
    def terminal(self) -> bool:
        return self.result_terminal or self is OperationState.CLOSED


class OperationReasonCode(StrEnum):
    OFFLINE = "offline"
    TIMEOUT = "timeout"
    CANCELLED_BY_USER = "cancelled_by_user"
    SOURCE_UNAVAILABLE = "source_unavailable"
    AUTH_REQUIRED = "auth_required"
    PERMISSION_DENIED = "permission_denied"
    VALIDATION_FAILED = "validation_failed"
    CONFLICT = "conflict"
    STALE_TARGET = "stale_target"
    UNSUPPORTED_SCHEMA = "unsupported_schema"
    DATA_DAMAGED = "data_damaged"
    STORAGE_UNAVAILABLE = "storage_unavailable"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    INTERNAL_ERROR = "internal_error"


class FeedbackSeverity(StrEnum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class ProgressMode(StrEnum):
    NONE = "none"
    INDETERMINATE = "indeterminate"
    BOUNDED = "bounded"


class TransitionDisposition(StrEnum):
    ACCEPTED = "accepted"
    IGNORED_DUPLICATE = "ignored_duplicate"
    IGNORED_STALE = "ignored_stale"
    REJECTED_CONFLICT = "rejected_conflict"
    REJECTED_TRANSITION = "rejected_transition"
    REJECTED_TERMINAL = "rejected_terminal"
    REJECTED_INVALID = "rejected_invalid"


@dataclass(frozen=True, slots=True)
class OperationSubject:
    namespace: str
    value: str
    label: SafeText | None = None

    def __post_init__(self) -> None:
        _validate_token(self.namespace, label="subject namespace")
        _validate_token(self.value, label="subject value")


@dataclass(frozen=True, slots=True)
class OperationProgress:
    mode: ProgressMode
    current: int = 0
    total: int = 0
    percent: Decimal | None = None
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    phase: str = ""

    def __post_init__(self) -> None:
        values = (self.current, self.total, self.completed, self.failed, self.skipped)
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in values
        ):
            raise ValueError("progress counters must be non-negative integers")
        if self.phase and not _PHASE.fullmatch(self.phase):
            raise ValueError("progress phase must be a closed token")
        if self.mode is ProgressMode.NONE:
            if any(values) or self.percent is not None or self.phase:
                raise ValueError("none progress cannot carry counters")
            return
        if self.mode is ProgressMode.INDETERMINATE:
            if self.total or self.percent is not None:
                raise ValueError("indeterminate progress cannot carry a total or percent")
            return
        if self.total == 0 and self.current != 0:
            raise ValueError("zero-total progress must remain at zero")
        if self.current > self.total:
            raise ValueError("progress current cannot exceed total")
        if self.completed + self.failed + self.skipped > self.current:
            raise ValueError("unit counts cannot exceed current progress")
        if self.percent is None:
            raise ValueError("bounded progress requires percent")
        try:
            numeric = float(self.percent)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("progress percent must be finite") from exc
        if not math.isfinite(numeric) or not Decimal("0") <= self.percent <= Decimal("100"):
            raise ValueError("progress percent must be within 0..100")

    @classmethod
    def none(cls) -> OperationProgress:
        return cls(mode=ProgressMode.NONE)

    @classmethod
    def indeterminate(cls, *, phase: str = "") -> OperationProgress:
        return cls(mode=ProgressMode.INDETERMINATE, phase=phase)

    @classmethod
    def bounded(
        cls,
        *,
        current: int,
        total: int,
        completed: int = 0,
        failed: int = 0,
        skipped: int = 0,
        phase: str = "",
    ) -> OperationProgress:
        if not isinstance(current, int) or not isinstance(total, int):
            raise ValueError("bounded progress requires integer counters")
        if total < 0 or current < 0 or current > total or (total == 0 and current != 0):
            raise ValueError("invalid bounded progress counters")
        try:
            percent = (
                Decimal("0.00")
                if total == 0
                else (Decimal(current) * Decimal(100) / Decimal(total)).quantize(Decimal("0.01"))
            )
        except (InvalidOperation, ZeroDivisionError) as exc:
            raise ValueError("invalid bounded progress percent") from exc
        return cls(
            mode=ProgressMode.BOUNDED,
            current=current,
            total=total,
            percent=percent,
            completed=completed,
            failed=failed,
            skipped=skipped,
            phase=phase,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "current": self.current,
            "total": self.total,
            "percent": str(self.percent) if self.percent is not None else None,
            "completed": self.completed,
            "failed": self.failed,
            "skipped": self.skipped,
            "phase": self.phase,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> OperationProgress:
        percent = payload.get("percent")
        return cls(
            mode=ProgressMode(str(payload["mode"])),
            current=int(payload.get("current", 0)),
            total=int(payload.get("total", 0)),
            percent=Decimal(str(percent)) if percent is not None else None,
            completed=int(payload.get("completed", 0)),
            failed=int(payload.get("failed", 0)),
            skipped=int(payload.get("skipped", 0)),
            phase=str(payload.get("phase", "")),
        )


@dataclass(frozen=True, slots=True)
class OperationCapabilities:
    can_cancel: bool = False
    can_retry: bool = False
    can_close: bool = False
    can_open_result: bool = False
    can_open_diagnostics: bool = False
    cancel_requires_confirmation: bool = False
    disabled_reasons: tuple[tuple[str, SafeText], ...] = ()

    def __post_init__(self) -> None:
        for name, reason in self.disabled_reasons:
            _validate_token(name, label="disabled capability")
            if not isinstance(reason, SafeText):
                raise TypeError("disabled reason must be SafeText")

    def to_dict(self) -> dict[str, Any]:
        return {
            "can_cancel": self.can_cancel,
            "can_retry": self.can_retry,
            "can_close": self.can_close,
            "can_open_result": self.can_open_result,
            "can_open_diagnostics": self.can_open_diagnostics,
            "cancel_requires_confirmation": self.cancel_requires_confirmation,
            "disabled_reasons": [[name, reason.value] for name, reason in self.disabled_reasons],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> OperationCapabilities:
        return cls(
            can_cancel=bool(payload.get("can_cancel", False)),
            can_retry=bool(payload.get("can_retry", False)),
            can_close=bool(payload.get("can_close", False)),
            can_open_result=bool(payload.get("can_open_result", False)),
            can_open_diagnostics=bool(payload.get("can_open_diagnostics", False)),
            cancel_requires_confirmation=bool(payload.get("cancel_requires_confirmation", False)),
            disabled_reasons=tuple(
                (str(name), SafeText(str(reason)))
                for name, reason in payload.get("disabled_reasons", ())
            ),
        )


@dataclass(frozen=True, slots=True)
class OperationEvent:
    state: OperationState
    generation: int
    revision: int
    occurred_at: datetime
    finished_at: datetime | None = None
    progress: OperationProgress | None = None
    reason: OperationReasonCode | None = None
    summary: SafeText | None = None
    diagnostic_id: DiagnosticCorrelationId | None = None
    capabilities: OperationCapabilities | None = None

    def __post_init__(self) -> None:
        if self.generation < 1 or self.revision < 1:
            raise ValueError("event generation and revision must be positive")
        _require_aware(self.occurred_at, label="event time")
        if self.finished_at is not None:
            _require_aware(self.finished_at, label="event finish time")


@dataclass(frozen=True, slots=True)
class OperationEpisode:
    CONTRACT_VERSION: ClassVar[int] = 1

    episode_id: OperationEpisodeId
    kind: OperationKind
    subject: OperationSubject
    state: OperationState
    attempt: int
    generation: int
    revision: int
    progress: OperationProgress
    started_at: datetime
    updated_at: datetime
    finished_at: datetime | None
    reason: OperationReasonCode | None
    summary: SafeText | None
    diagnostic_id: DiagnosticCorrelationId | None
    capabilities: OperationCapabilities
    parent_episode_id: OperationEpisodeId | None

    def __post_init__(self) -> None:
        if self.attempt < 1 or self.generation < 1 or self.revision < 1:
            raise ValueError("attempt, generation and revision must be positive")
        _require_aware(self.started_at, label="started_at")
        _require_aware(self.updated_at, label="updated_at")
        if self.updated_at < self.started_at:
            raise ValueError("updated_at cannot precede started_at")
        if self.state.terminal:
            if self.finished_at is None:
                raise ValueError("terminal episode requires finished_at")
            _require_aware(self.finished_at, label="finished_at")
            if self.finished_at < self.started_at:
                raise ValueError("finished_at cannot precede started_at")
        elif self.finished_at is not None:
            raise ValueError("active episode cannot have finished_at")

    def to_dict(self, *, native: bool = False) -> dict[str, Any]:
        if native:
            return {field.name: getattr(self, field.name) for field in fields(self)}
        return {
            "contract_version": self.CONTRACT_VERSION,
            "episode_id": self.episode_id.value,
            "kind": self.kind.value,
            "subject": {
                "namespace": self.subject.namespace,
                "value": self.subject.value,
                "label": self.subject.label.value if self.subject.label is not None else None,
            },
            "state": self.state.value,
            "attempt": self.attempt,
            "generation": self.generation,
            "revision": self.revision,
            "progress": self.progress.to_dict(),
            "started_at": self.started_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "reason": self.reason.value if self.reason is not None else None,
            "summary": self.summary.value if self.summary is not None else None,
            "diagnostic_id": self.diagnostic_id.value if self.diagnostic_id is not None else None,
            "capabilities": self.capabilities.to_dict(),
            "parent_episode_id": (
                self.parent_episode_id.value if self.parent_episode_id is not None else None
            ),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> OperationEpisode:
        if int(payload.get("contract_version", 0)) != cls.CONTRACT_VERSION:
            raise ValueError("unsupported operation episode contract version")
        subject_payload = payload["subject"]
        if not isinstance(subject_payload, Mapping):
            raise ValueError("invalid operation subject")
        label = subject_payload.get("label")
        reason = payload.get("reason")
        summary = payload.get("summary")
        diagnostic_id = payload.get("diagnostic_id")
        parent_id = payload.get("parent_episode_id")
        finished_at = payload.get("finished_at")
        return cls(
            episode_id=OperationEpisodeId(str(payload["episode_id"])),
            kind=OperationKind(str(payload["kind"])),
            subject=OperationSubject(
                namespace=str(subject_payload["namespace"]),
                value=str(subject_payload["value"]),
                label=SafeText(str(label)) if label is not None else None,
            ),
            state=OperationState(str(payload["state"])),
            attempt=int(payload["attempt"]),
            generation=int(payload["generation"]),
            revision=int(payload["revision"]),
            progress=OperationProgress.from_dict(payload["progress"]),
            started_at=datetime.fromisoformat(str(payload["started_at"])),
            updated_at=datetime.fromisoformat(str(payload["updated_at"])),
            finished_at=datetime.fromisoformat(str(finished_at)) if finished_at else None,
            reason=OperationReasonCode(str(reason)) if reason is not None else None,
            summary=SafeText(str(summary)) if summary is not None else None,
            diagnostic_id=(
                DiagnosticCorrelationId(str(diagnostic_id)) if diagnostic_id is not None else None
            ),
            capabilities=OperationCapabilities.from_dict(payload["capabilities"]),
            parent_episode_id=(
                OperationEpisodeId(str(parent_id)) if parent_id is not None else None
            ),
        )

    def semantic_fingerprint(self) -> str:
        payload = self.to_dict()
        for key in ("episode_id", "started_at", "updated_at", "finished_at"):
            payload.pop(key, None)
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "DiagnosticCorrelationId",
    "FeedbackSeverity",
    "OperationCapabilities",
    "OperationEpisode",
    "OperationEpisodeId",
    "OperationEvent",
    "OperationKind",
    "OperationProgress",
    "OperationReasonCode",
    "OperationState",
    "OperationSubject",
    "ProgressMode",
    "SafeText",
    "TransitionDisposition",
]
