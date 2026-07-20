"""Safe notification envelopes and schema-v1 compatibility adapter."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
import hashlib
import json
import re
from typing import Any, Protocol

from app.core.version import APP_VERSION
from app.operations.contracts import (
    DiagnosticCorrelationId,
    FeedbackSeverity,
    OperationEpisodeId,
    OperationKind,
    OperationReasonCode,
    OperationState,
    OperationSubject,
    SafeText,
)
from app.operations.diagnostics import (
    DiagnosticOwnerKind,
    DiagnosticRecord,
    DiagnosticRegistry,
)
from app.operations.safe_feedback import sanitize_safe_text

_UNSAFE_LEGACY = re.compile(
    r"(?ix)(authorization\s*:|bearer\s+|api[_-]?key|token\s*=|password|"
    r"[a-z]:[\\/]|/(?:home|users?)/|https?://[^\s?#]+[?#]|<\s*/?\s*(?:script|style|img)|"
    r"onerror\s*=|[\u202a-\u202e\u2066-\u2069])"
)


class LegacyCollectorNotification(Protocol):
    @property
    def id(self) -> str: ...

    @property
    def created_at(self) -> str: ...

    @property
    def title(self) -> str: ...

    @property
    def message(self) -> str: ...

    @property
    def kind(self) -> object: ...

    @property
    def read(self) -> bool: ...

    @property
    def run_id(self) -> str: ...


class NotificationKind(StrEnum):
    SUCCESS = "success"
    INFO = "info"
    WARNING = "warning"
    FAILURE = "failure"


class NotificationDisposition(StrEnum):
    INSERTED = "inserted"
    DUPLICATE = "duplicate"
    REVISED = "revised"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class NotificationAction:
    action_id: str
    route_id: str
    subject: OperationSubject
    freshness_token: str
    label: SafeText
    accessible_label: SafeText
    confirmation_required: bool = False
    single_shot: bool = False

    def __post_init__(self) -> None:
        if not self.action_id or len(self.action_id) > 64:
            raise ValueError("notification action id must be bounded")
        if not self.route_id or len(self.route_id) > 128:
            raise ValueError("notification route id must be bounded")
        if not self.freshness_token or len(self.freshness_token) > 128:
            raise ValueError("notification freshness token must be bounded")


@dataclass(frozen=True, slots=True)
class NotificationEnvelope:
    notification_id: str
    event_id: str
    episode_id: OperationEpisodeId | None
    correlation_id: DiagnosticCorrelationId | None
    kind: NotificationKind
    severity: FeedbackSeverity
    title: SafeText
    summary: SafeText
    subject: OperationSubject | None
    actions: tuple[NotificationAction, ...]
    created_at: datetime
    revision: int
    terminal_state: OperationState | None
    read_at: datetime | None
    dismissed_at: datetime | None

    def __post_init__(self) -> None:
        if not self.notification_id or len(self.notification_id) > 128:
            raise ValueError("notification id must be bounded")
        if not self.event_id or len(self.event_id) > 128:
            raise ValueError("notification event id must be bounded")
        if self.revision < 1:
            raise ValueError("notification revision must be positive")
        for label, value in (
            ("created_at", self.created_at),
            ("read_at", self.read_at),
            ("dismissed_at", self.dismissed_at),
        ):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError(f"{label} must be timezone-aware")

    def to_dict(self, *, native: bool = False) -> dict[str, Any]:
        if native:
            return {
                "notification_id": self.notification_id,
                "event_id": self.event_id,
                "episode_id": self.episode_id,
                "correlation_id": self.correlation_id,
                "kind": self.kind,
                "severity": self.severity,
                "title": self.title,
                "summary": self.summary,
                "subject": self.subject,
                "actions": self.actions,
                "created_at": self.created_at,
                "revision": self.revision,
                "terminal_state": self.terminal_state,
                "read_at": self.read_at,
                "dismissed_at": self.dismissed_at,
            }
        return {
            "notification_id": self.notification_id,
            "event_id": self.event_id,
            "episode_id": self.episode_id.value if self.episode_id else None,
            "correlation_id": self.correlation_id.value if self.correlation_id else None,
            "kind": self.kind.value,
            "severity": self.severity.value,
            "title": self.title.value,
            "summary": self.summary.value,
            "subject": (
                {"namespace": self.subject.namespace, "value": self.subject.value}
                if self.subject
                else None
            ),
            "actions": [action.action_id for action in self.actions],
            "created_at": self.created_at.isoformat(),
            "revision": self.revision,
            "terminal_state": self.terminal_state.value if self.terminal_state else None,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "dismissed_at": self.dismissed_at.isoformat() if self.dismissed_at else None,
        }

    def fingerprint(self, *, include_revision: bool = True) -> str:
        payload = self.to_dict()
        payload.pop("read_at", None)
        payload.pop("dismissed_at", None)
        if not include_revision:
            payload.pop("revision", None)
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class NotificationLedger:
    def __init__(self, *, max_items: int = 200) -> None:
        if max_items < 1:
            raise ValueError("max_items must be positive")
        self.max_items = int(max_items)
        self._items: OrderedDict[str, NotificationEnvelope] = OrderedDict()

    def upsert(self, envelope: NotificationEnvelope) -> NotificationDisposition:
        existing = self._items.get(envelope.notification_id)
        if existing is None:
            self._items[envelope.notification_id] = envelope
            while len(self._items) > self.max_items:
                self._items.popitem(last=False)
            return NotificationDisposition.INSERTED
        if envelope.revision == existing.revision:
            return (
                NotificationDisposition.DUPLICATE
                if envelope.fingerprint() == existing.fingerprint()
                else NotificationDisposition.CONFLICT
            )
        if envelope.revision < existing.revision:
            return NotificationDisposition.CONFLICT
        revised = replace(
            envelope,
            read_at=existing.read_at,
            dismissed_at=existing.dismissed_at,
        )
        self._items[envelope.notification_id] = revised
        return NotificationDisposition.REVISED

    def get(self, notification_id: str) -> NotificationEnvelope | None:
        return self._items.get(notification_id)

    def mark_read(self, notification_id: str, *, occurred_at: datetime) -> NotificationEnvelope:
        item = self._required(notification_id)
        updated = item if item.read_at is not None else replace(item, read_at=occurred_at)
        self._items[notification_id] = updated
        return updated

    def dismiss(self, notification_id: str, *, occurred_at: datetime) -> NotificationEnvelope:
        item = self._required(notification_id)
        updated = item if item.dismissed_at is not None else replace(item, dismissed_at=occurred_at)
        self._items[notification_id] = updated
        return updated

    def active(self) -> tuple[NotificationEnvelope, ...]:
        return tuple(item for item in self._items.values() if item.dismissed_at is None)

    def _required(self, notification_id: str) -> NotificationEnvelope:
        item = self.get(notification_id)
        if item is None:
            raise KeyError(notification_id)
        return item


class UnsupportedNotificationSchema(ValueError):
    pass


class StaleNotificationAction(ValueError):
    pass


class LegacyCollectorNotificationAdapter:
    def __init__(self, *, registry: DiagnosticRegistry | None = None) -> None:
        self.registry = registry if registry is not None else DiagnosticRegistry()

    def adapt(
        self,
        notification: LegacyCollectorNotification,
        *,
        schema_version: int,
    ) -> NotificationEnvelope:
        if schema_version != 1:
            raise UnsupportedNotificationSchema("unsupported collector notification schema")
        try:
            created_at = datetime.fromisoformat(notification.created_at.replace("Z", "+00:00"))
            if created_at.tzinfo is None or created_at.utcoffset() is None:
                raise ValueError
        except ValueError as exc:
            raise UnsupportedNotificationSchema("notification time is not aware") from exc

        unsafe = bool(
            _UNSAFE_LEGACY.search(notification.title) or _UNSAFE_LEGACY.search(notification.message)
        )
        correlation_id = None
        if unsafe:
            title = SafeText("Уведомление скрыто для безопасности")
            summary = SafeText("Откройте диагностику и повторите операцию.")
            correlation_id = self.registry.new_id()
            self.registry.register(
                DiagnosticRecord(
                    correlation_id=correlation_id,
                    episode_id=OperationEpisodeId(
                        "legacy-" + hashlib.sha256(notification.id.encode()).hexdigest()[:24]
                    ),
                    kind=OperationKind.NOTIFICATION,
                    reason=OperationReasonCode.INTERNAL_ERROR,
                    occurred_at=created_at,
                    application_version=APP_VERSION,
                    safe_context=(("source", "collector_notification_v1"),),
                    owner_kind=DiagnosticOwnerKind.COLLECTOR_RUN,
                    evidence_reference="legacy-notification",
                    parent_correlation_id=None,
                )
            )
        else:
            title = sanitize_safe_text(notification.title, max_length=160)
            summary = sanitize_safe_text(notification.message, max_length=320)

        subject = None
        if notification.run_id:
            try:
                subject = OperationSubject("collector_run", notification.run_id)
            except ValueError:
                subject = None
        kind, severity, terminal = _legacy_kind(notification.kind)
        safe_identifier = (
            notification.id
            if notification.id and len(notification.id) <= 96
            else hashlib.sha256(notification.id.encode()).hexdigest()[:32]
        )
        return NotificationEnvelope(
            notification_id=f"legacy:{safe_identifier}",
            event_id=f"legacy-event:{hashlib.sha256(notification.id.encode()).hexdigest()[:32]}",
            episode_id=None,
            correlation_id=correlation_id,
            kind=kind,
            severity=severity,
            title=title,
            summary=summary,
            subject=subject,
            actions=(),
            created_at=created_at,
            revision=1,
            terminal_state=terminal,
            read_at=created_at if notification.read else None,
            dismissed_at=None,
        )


def _legacy_kind(kind: object) -> tuple[NotificationKind, FeedbackSeverity, OperationState | None]:
    value = str(getattr(kind, "value", kind))
    return {
        "success": (
            NotificationKind.SUCCESS,
            FeedbackSeverity.SUCCESS,
            OperationState.SUCCEEDED,
        ),
        "info": (
            NotificationKind.INFO,
            FeedbackSeverity.INFO,
            None,
        ),
        "warning": (
            NotificationKind.WARNING,
            FeedbackSeverity.WARNING,
            OperationState.PARTIAL,
        ),
        "error": (
            NotificationKind.FAILURE,
            FeedbackSeverity.ERROR,
            OperationState.FAILED,
        ),
    }[value]


def resolve_notification_action(
    envelope: NotificationEnvelope,
    *,
    action_id: str,
    current_subject: OperationSubject,
    current_freshness_token: str,
) -> NotificationAction:
    action = next((item for item in envelope.actions if item.action_id == action_id), None)
    if action is None:
        raise StaleNotificationAction("notification action is unavailable")
    if action.subject != current_subject or action.freshness_token != current_freshness_token:
        raise StaleNotificationAction("notification target is stale")
    return action


__all__ = [
    "LegacyCollectorNotificationAdapter",
    "NotificationAction",
    "NotificationDisposition",
    "NotificationEnvelope",
    "NotificationKind",
    "NotificationLedger",
    "StaleNotificationAction",
    "UnsupportedNotificationSchema",
    "resolve_notification_action",
]
