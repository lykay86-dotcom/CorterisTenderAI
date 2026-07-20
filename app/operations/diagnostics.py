"""Bounded safe diagnostic correlation without artifact ownership."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import hashlib
import json
from uuid import uuid4

from app.operations.contracts import (
    DiagnosticCorrelationId,
    OperationEpisodeId,
    OperationKind,
    OperationReasonCode,
)


class DiagnosticOwnerKind(StrEnum):
    TRANSIENT = "transient"
    CRASH_REPORT = "crash_report"
    SUPPORT_BUNDLE = "support_bundle"
    WORKFLOW_HEALTH = "workflow_health"
    COLLECTOR_RUN = "collector_run"
    ANALYSIS = "analysis"


@dataclass(frozen=True, slots=True)
class DiagnosticRecord:
    correlation_id: DiagnosticCorrelationId
    episode_id: OperationEpisodeId
    kind: OperationKind
    reason: OperationReasonCode
    occurred_at: datetime
    application_version: str
    safe_context: tuple[tuple[str, str], ...]
    owner_kind: DiagnosticOwnerKind
    evidence_reference: str
    parent_correlation_id: DiagnosticCorrelationId | None
    contract_version: int = 1

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("diagnostic time must be timezone-aware")
        if self.contract_version != 1:
            raise ValueError("unsupported diagnostic contract version")
        if len(self.application_version) > 64 or len(self.evidence_reference) > 128:
            raise ValueError("diagnostic fields must be bounded")
        if len(self.safe_context) > 16:
            raise ValueError("safe diagnostic context must be bounded")
        for key, value in self.safe_context:
            if not key or len(key) > 64 or len(value) > 256:
                raise ValueError("invalid safe diagnostic context")

    def fingerprint(self) -> str:
        payload = {
            "correlation_id": self.correlation_id.value,
            "episode_id": self.episode_id.value,
            "kind": self.kind.value,
            "reason": self.reason.value,
            "occurred_at": self.occurred_at.isoformat(),
            "application_version": self.application_version,
            "safe_context": self.safe_context,
            "owner_kind": self.owner_kind.value,
            "evidence_reference": self.evidence_reference,
            "parent": self.parent_correlation_id.value if self.parent_correlation_id else None,
            "contract_version": self.contract_version,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class DiagnosticConflictError(ValueError):
    """Raised when one correlation ID is reused for different safe evidence."""


class DiagnosticRegistry:
    def __init__(
        self,
        *,
        max_records: int = 256,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        if max_records < 1:
            raise ValueError("max_records must be positive")
        self.max_records = int(max_records)
        self._id_factory = id_factory or (lambda: f"diagnostic-{uuid4().hex}")
        self._records: OrderedDict[DiagnosticCorrelationId, DiagnosticRecord] = OrderedDict()

    def new_id(self) -> DiagnosticCorrelationId:
        return DiagnosticCorrelationId(self._id_factory())

    def register(self, record: DiagnosticRecord) -> DiagnosticRecord:
        existing = self._records.get(record.correlation_id)
        if existing is not None:
            if existing.fingerprint() != record.fingerprint():
                raise DiagnosticConflictError("conflicting diagnostic correlation reuse")
            return existing
        self._records[record.correlation_id] = record
        while len(self._records) > self.max_records:
            self._records.popitem(last=False)
        return record

    def get(self, identifier: DiagnosticCorrelationId) -> DiagnosticRecord | None:
        return self._records.get(identifier)

    def discard(self, identifier: DiagnosticCorrelationId) -> bool:
        return self._records.pop(identifier, None) is not None

    def __len__(self) -> int:
        return len(self._records)


__all__ = [
    "DiagnosticConflictError",
    "DiagnosticOwnerKind",
    "DiagnosticRecord",
    "DiagnosticRegistry",
]
