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
        normalized = "Нет безопасного описания."
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
            rendered += f" Код диагностики: {self.diagnostic_id.value}."
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
        "Нет сетевого соединения",
        "Проверьте подключение и повторите операцию.",
    ),
    OperationReasonCode.TIMEOUT: (
        FeedbackSeverity.WARNING,
        "Истекло время ожидания",
        "Операция не подтвердила завершение. Повторите позже.",
    ),
    OperationReasonCode.CANCELLED_BY_USER: (
        FeedbackSeverity.INFO,
        "Операция остановлена",
        "Остановка подтверждена владельцем операции.",
    ),
    OperationReasonCode.SOURCE_UNAVAILABLE: (
        FeedbackSeverity.WARNING,
        "Источник недоступен",
        "Проверьте состояние источника и повторите операцию.",
    ),
    OperationReasonCode.AUTH_REQUIRED: (
        FeedbackSeverity.WARNING,
        "Требуется настройка доступа",
        "Откройте настройки провайдера и повторите операцию.",
    ),
    OperationReasonCode.PERMISSION_DENIED: (
        FeedbackSeverity.ERROR,
        "Недостаточно прав",
        "Проверьте доступ к целевому объекту.",
    ),
    OperationReasonCode.VALIDATION_FAILED: (
        FeedbackSeverity.WARNING,
        "Данные не прошли проверку",
        "Исправьте входные данные и повторите операцию.",
    ),
    OperationReasonCode.CONFLICT: (
        FeedbackSeverity.WARNING,
        "Обнаружен конфликт данных",
        "Обновите данные и повторите действие.",
    ),
    OperationReasonCode.STALE_TARGET: (
        FeedbackSeverity.WARNING,
        "Целевой объект изменился",
        "Обновите список и выберите объект повторно.",
    ),
    OperationReasonCode.UNSUPPORTED_SCHEMA: (
        FeedbackSeverity.ERROR,
        "Формат данных не поддерживается",
        "Чтение остановлено без изменения данных.",
    ),
    OperationReasonCode.DATA_DAMAGED: (
        FeedbackSeverity.ERROR,
        "Данные повреждены",
        "Откройте центр восстановления или диагностику.",
    ),
    OperationReasonCode.STORAGE_UNAVAILABLE: (
        FeedbackSeverity.ERROR,
        "Хранилище недоступно",
        "Проверьте доступ к локальному хранилищу.",
    ),
    OperationReasonCode.DEPENDENCY_UNAVAILABLE: (
        FeedbackSeverity.ERROR,
        "Компонент недоступен",
        "Перезапустите приложение и повторите операцию.",
    ),
    OperationReasonCode.INTERNAL_ERROR: (
        FeedbackSeverity.ERROR,
        "Операция не завершена",
        "Технические детали безопасно скрыты. Откройте диагностику.",
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
            accessible_value += f" Код диагностики: {diagnostic_id.value}."
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
