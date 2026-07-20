"""Allowlist-first safe feedback projection."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
import re
import unicodedata
from uuid import uuid4

from app.core.version import APP_VERSION
from app.operations.contracts import (
    DiagnosticCorrelationId,
    FeedbackSeverity,
    OperationEpisodeId,
    OperationKind,
    OperationReasonCode,
    SafeText,
)
from app.operations.diagnostics import (
    DiagnosticOwnerKind,
    DiagnosticRecord,
    DiagnosticRegistry,
)


_BIDI = re.compile("[\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]")
_MARKUP = re.compile(r"[<>]")
_WHITESPACE = re.compile(r"\s+")


def sanitize_safe_text(value: object, *, max_length: int = 512) -> SafeText:
    if max_length < 1 or max_length > SafeText.MAX_LENGTH:
        raise ValueError("safe text bound is outside the contract")
    normalized = unicodedata.normalize("NFKC", str(value))
    normalized = _BIDI.sub("", normalized)
    normalized = "".join(
        " " if unicodedata.category(character).startswith("C") else character
        for character in normalized
    )
    normalized = _MARKUP.sub("", normalized)
    normalized = _WHITESPACE.sub(" ", normalized).strip()
    if not normalized:
        normalized = "РќРµС‚ Р±РµР·РѕРїР°СЃРЅРѕРіРѕ РѕРїРёСЃР°РЅРёСЏ."
    return SafeText(normalized[:max_length].rstrip())


@dataclass(frozen=True, slots=True)
class FeedbackAction:
    action_id: str
    label: SafeText
    accessible_label: SafeText


@dataclass(frozen=True, slots=True)
class SafeFeedback:
    feedback_id: str
    episode_id: OperationEpisodeId
    kind: OperationKind
    severity: FeedbackSeverity
    title: SafeText
    summary: SafeText
    reason: OperationReasonCode
    actions: tuple[FeedbackAction, ...]
    diagnostic_id: DiagnosticCorrelationId | None
    occurred_at: datetime
    accessible_text: SafeText

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("feedback time must be timezone-aware")
        if not self.feedback_id or len(self.feedback_id) > 128:
            raise ValueError("feedback id must be bounded")

    def to_plain_text(self) -> str:
        rendered = f"{self.title.value}. {self.summary.value}"
        if self.diagnostic_id is not None:
            rendered += f" РљРѕРґ РґРёР°РіРЅРѕСЃС‚РёРєРё: {self.diagnostic_id.value}."
        return rendered

    def to_notification_payload(self) -> dict[str, object]:
        return {
            "feedback_id": self.feedback_id,
            "episode_id": self.episode_id.value,
            "severity": self.severity.value,
            "title": self.title.value,
            "summary": self.summary.value,
            "reason": self.reason.value,
            "diagnostic_id": self.diagnostic_id.value if self.diagnostic_id else None,
            "accessible_text": self.accessible_text.value,
            "actions": [action.action_id for action in self.actions],
        }

    def to_export_dict(self) -> dict[str, object]:
        return {
            **self.to_notification_payload(),
            "kind": self.kind.value,
            "occurred_at": self.occurred_at.isoformat(),
        }


_PRESENTATION: Mapping[
    OperationReasonCode,
    tuple[FeedbackSeverity, str, str],
] = {
    OperationReasonCode.OFFLINE: (
        FeedbackSeverity.WARNING,
        "РќРµС‚ СЃРµС‚РµРІРѕРіРѕ СЃРѕРµРґРёРЅРµРЅРёСЏ",
        "РџСЂРѕРІРµСЂСЊС‚Рµ РїРѕРґРєР»СЋС‡РµРЅРёРµ Рё РїРѕРІС‚РѕСЂРёС‚Рµ РѕРїРµСЂР°С†РёСЋ.",
    ),
    OperationReasonCode.TIMEOUT: (
        FeedbackSeverity.WARNING,
        "РСЃС‚РµРєР»Рѕ РІСЂРµРјСЏ РѕР¶РёРґР°РЅРёСЏ",
        "РћРїРµСЂР°С†РёСЏ РЅРµ РїРѕРґС‚РІРµСЂРґРёР»Р° Р·Р°РІРµСЂС€РµРЅРёРµ. РџРѕРІС‚РѕСЂРёС‚Рµ РїРѕР·Р¶Рµ.",
    ),
    OperationReasonCode.CANCELLED_BY_USER: (
        FeedbackSeverity.INFO,
        "РћРїРµСЂР°С†РёСЏ РѕСЃС‚Р°РЅРѕРІР»РµРЅР°",
        "РћСЃС‚Р°РЅРѕРІРєР° РїРѕРґС‚РІРµСЂР¶РґРµРЅР° РІР»Р°РґРµР»СЊС†РµРј РѕРїРµСЂР°С†РёРё.",
    ),
    OperationReasonCode.SOURCE_UNAVAILABLE: (
        FeedbackSeverity.WARNING,
        "РСЃС‚РѕС‡РЅРёРє РЅРµРґРѕСЃС‚СѓРїРµРЅ",
        "РџСЂРѕРІРµСЂСЊС‚Рµ СЃРѕСЃС‚РѕСЏРЅРёРµ РёСЃС‚РѕС‡РЅРёРєР° Рё РїРѕРІС‚РѕСЂРёС‚Рµ РѕРїРµСЂР°С†РёСЋ.",
    ),
    OperationReasonCode.AUTH_REQUIRED: (
        FeedbackSeverity.WARNING,
        "РўСЂРµР±СѓРµС‚СЃСЏ РЅР°СЃС‚СЂРѕР№РєР° РґРѕСЃС‚СѓРїР°",
        "РћС‚РєСЂРѕР№С‚Рµ РЅР°СЃС‚СЂРѕР№РєРё РїСЂРѕРІР°Р№РґРµСЂР° Рё РїРѕРІС‚РѕСЂРёС‚Рµ РѕРїРµСЂР°С†РёСЋ.",
    ),
    OperationReasonCode.PERMISSION_DENIED: (
        FeedbackSeverity.ERROR,
        "РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ РїСЂР°РІ",
        "РџСЂРѕРІРµСЂСЊС‚Рµ РґРѕСЃС‚СѓРї Рє С†РµР»РµРІРѕРјСѓ РѕР±СЉРµРєС‚Сѓ.",
    ),
    OperationReasonCode.VALIDATION_FAILED: (
        FeedbackSeverity.WARNING,
        "Р”Р°РЅРЅС‹Рµ РЅРµ РїСЂРѕС€Р»Рё РїСЂРѕРІРµСЂРєСѓ",
        "РСЃРїСЂР°РІСЊС‚Рµ РІС…РѕРґРЅС‹Рµ РґР°РЅРЅС‹Рµ Рё РїРѕРІС‚РѕСЂРёС‚Рµ РѕРїРµСЂР°С†РёСЋ.",
    ),
    OperationReasonCode.CONFLICT: (
        FeedbackSeverity.WARNING,
        "РћР±РЅР°СЂСѓР¶РµРЅ РєРѕРЅС„Р»РёРєС‚ РґР°РЅРЅС‹С…",
        "РћР±РЅРѕРІРёС‚Рµ РґР°РЅРЅС‹Рµ Рё РїРѕРІС‚РѕСЂРёС‚Рµ РґРµР№СЃС‚РІРёРµ.",
    ),
    OperationReasonCode.STALE_TARGET: (
        FeedbackSeverity.WARNING,
        "Р¦РµР»РµРІРѕР№ РѕР±СЉРµРєС‚ РёР·РјРµРЅРёР»СЃСЏ",
        "РћР±РЅРѕРІРёС‚Рµ СЃРїРёСЃРѕРє Рё РІС‹Р±РµСЂРёС‚Рµ РѕР±СЉРµРєС‚ РїРѕРІС‚РѕСЂРЅРѕ.",
    ),
    OperationReasonCode.UNSUPPORTED_SCHEMA: (
        FeedbackSeverity.ERROR,
        "Р¤РѕСЂРјР°С‚ РґР°РЅРЅС‹С… РЅРµ РїРѕРґРґРµСЂР¶РёРІР°РµС‚СЃСЏ",
        "Р§С‚РµРЅРёРµ РѕСЃС‚Р°РЅРѕРІР»РµРЅРѕ Р±РµР· РёР·РјРµРЅРµРЅРёСЏ РґР°РЅРЅС‹С….",
    ),
    OperationReasonCode.DATA_DAMAGED: (
        FeedbackSeverity.ERROR,
        "Р”Р°РЅРЅС‹Рµ РїРѕРІСЂРµР¶РґРµРЅС‹",
        "РћС‚РєСЂРѕР№С‚Рµ С†РµРЅС‚СЂ РІРѕСЃСЃС‚Р°РЅРѕРІР»РµРЅРёСЏ РёР»Рё РґРёР°РіРЅРѕСЃС‚РёРєСѓ.",
    ),
    OperationReasonCode.STORAGE_UNAVAILABLE: (
        FeedbackSeverity.ERROR,
        "РҐСЂР°РЅРёР»РёС‰Рµ РЅРµРґРѕСЃС‚СѓРїРЅРѕ",
        "РџСЂРѕРІРµСЂСЊС‚Рµ РґРѕСЃС‚СѓРї Рє Р»РѕРєР°Р»СЊРЅРѕРјСѓ С…СЂР°РЅРёР»РёС‰Сѓ.",
    ),
    OperationReasonCode.DEPENDENCY_UNAVAILABLE: (
        FeedbackSeverity.ERROR,
        "РљРѕРјРїРѕРЅРµРЅС‚ РЅРµРґРѕСЃС‚СѓРїРµРЅ",
        "РџРµСЂРµР·Р°РїСѓСЃС‚РёС‚Рµ РїСЂРёР»РѕР¶РµРЅРёРµ Рё РїРѕРІС‚РѕСЂРёС‚Рµ РѕРїРµСЂР°С†РёСЋ.",
    ),
    OperationReasonCode.INTERNAL_ERROR: (
        FeedbackSeverity.ERROR,
        "РћРїРµСЂР°С†РёСЏ РЅРµ Р·Р°РІРµСЂС€РµРЅР°",
        "РўРµС…РЅРёС‡РµСЃРєРёРµ РґРµС‚Р°Р»Рё Р±РµР·РѕРїР°СЃРЅРѕ СЃРєСЂС‹С‚С‹. РћС‚РєСЂРѕР№С‚Рµ РґРёР°РіРЅРѕСЃС‚РёРєСѓ.",
    ),
}


class SafeFeedbackProjector:
    def __init__(
        self,
        *,
        registry: DiagnosticRegistry | None = None,
        feedback_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.registry = registry if registry is not None else DiagnosticRegistry()
        self._feedback_id_factory = feedback_id_factory or (lambda: f"feedback-{uuid4().hex}")

    def project_exception(
        self,
        error: BaseException,
        *,
        episode_id: OperationEpisodeId,
        kind: OperationKind,
        occurred_at: datetime,
    ) -> SafeFeedback:
        del error
        return self.project_reason(
            OperationReasonCode.INTERNAL_ERROR,
            episode_id=episode_id,
            kind=kind,
            occurred_at=occurred_at,
            register_diagnostic=True,
        )

    def project_reason(
        self,
        reason: OperationReasonCode,
        *,
        episode_id: OperationEpisodeId,
        kind: OperationKind,
        occurred_at: datetime,
        unsafe_detail: object | None = None,
        register_diagnostic: bool | None = None,
    ) -> SafeFeedback:
        del unsafe_detail
        severity, title_value, summary_value = _PRESENTATION[reason]
        should_register = (
            severity is FeedbackSeverity.ERROR
            if register_diagnostic is None
            else register_diagnostic
        )
        diagnostic_id = self.registry.new_id() if should_register else None
        if diagnostic_id is not None:
            self.registry.register(
                DiagnosticRecord(
                    correlation_id=diagnostic_id,
                    episode_id=episode_id,
                    kind=kind,
                    reason=reason,
                    occurred_at=occurred_at,
                    application_version=APP_VERSION,
                    safe_context=(("operation_kind", kind.value),),
                    owner_kind=DiagnosticOwnerKind.TRANSIENT,
                    evidence_reference="session-safe-record",
                    parent_correlation_id=None,
                )
            )
        title = SafeText(title_value)
        summary = SafeText(summary_value)
        accessible_value = f"{title.value}. {summary.value}"
        if diagnostic_id is not None:
            accessible_value += f" РљРѕРґ РґРёР°РіРЅРѕСЃС‚РёРєРё: {diagnostic_id.value}."
        return SafeFeedback(
            feedback_id=self._feedback_id_factory(),
            episode_id=episode_id,
            kind=kind,
            severity=severity,
            title=title,
            summary=summary,
            reason=reason,
            actions=(),
            diagnostic_id=diagnostic_id,
            occurred_at=occurred_at,
            accessible_text=SafeText(accessible_value),
        )


__all__ = [
    "FeedbackAction",
    "SafeFeedback",
    "SafeFeedbackProjector",
    "sanitize_safe_text",
]
