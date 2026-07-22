"""Typed, safe public failures for Collector search execution."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum

from app.tenders.collector.async_http import (
    AsyncHttpError,
    AsyncHttpResponseTooLargeError,
    AsyncHttpStatusError,
    AsyncHttpTransportError,
)
from app.tenders.collector.cancellation import CollectorCancelledError
from app.tenders.collector.async_provider import ProviderPageContractError
from app.tenders.provider_base import ProviderCapabilityError, ProviderNotConfiguredError


class SearchErrorCategory(StrEnum):
    NONE = "none"
    CONFIGURATION = "configuration"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    NETWORK = "network"
    REMOTE_SERVICE = "remote_service"
    CANCELLED = "cancelled"
    PROTOCOL = "protocol"
    INTERNAL = "internal"


SAFE_SEARCH_ERROR_MESSAGES = {
    "search_cancelled": "Операция поиска отменена.",
    "provider_not_configured": "Источник не настроен.",
    "provider_search_unsupported": "Источник не поддерживает поиск.",
    "provider_timeout": "Источник не завершил поиск за отведённое время.",
    "remote_response_too_large": "Ответ источника превышает допустимый размер.",
    "provider_authentication_failed": "Источник отклонил данные аутентификации.",
    "provider_access_forbidden": "Источник запретил доступ к операции.",
    "provider_rate_limited": "Источник временно ограничил частоту запросов.",
    "provider_service_unavailable": "Сервис источника временно недоступен.",
    "provider_http_error": "Источник вернул неподдерживаемый ответ.",
    "provider_network_error": "Не удалось безопасно получить ответ источника.",
    "provider_remote_error": "Источник завершил операцию с ошибкой.",
    "provider_internal_error": "Источник завершил поиск с безопасно скрытой ошибкой.",
    "provider_circuit_open": "Источник временно отключён после повторных ошибок.",
    "provider_cursor_cycle": "Источник вернул повторяющийся курсор страницы.",
    "provider_page_budget_exceeded": "Источник превысил допустимый объём страниц.",
    "provider_page_contract_error": "Источник нарушил контракт страницы.",
    "collector_internal_error": "Сбор завершился с безопасно скрытой ошибкой.",
}

_SENSITIVE_PUBLIC_MARKERS = (
    "authorization",
    "api_key",
    "apikey",
    "bearer ",
    "cookie",
    "password",
    "secret",
    "token",
    "://",
)
_SAFE_PROVIDER_WARNING = "Предупреждение источника безопасно скрыто."


@dataclass(frozen=True, slots=True)
class SearchFailure:
    category: SearchErrorCategory
    code: str
    message: str
    attempts: int = 1
    retryable: bool = False
    http_status: int | None = None
    occurred_at: str = field(default_factory=lambda: _utc_now())

    def __post_init__(self) -> None:
        if self.category is SearchErrorCategory.NONE:
            raise ValueError("SearchFailure category must describe a failure")
        if not self.code.strip() or not self.message.strip():
            raise ValueError("SearchFailure code and message are required")
        if self.attempts < 1:
            raise ValueError("SearchFailure attempts must be positive")
        if self.http_status is not None and not 100 <= self.http_status <= 599:
            raise ValueError("SearchFailure HTTP status is invalid")
        if len(self.code) > 120 or len(self.message) > 300:
            raise ValueError("SearchFailure public fields exceed their bounds")
        try:
            occurred = datetime.fromisoformat(self.occurred_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("SearchFailure timestamp is invalid") from exc
        if occurred.tzinfo is None or occurred.utcoffset() is None:
            raise ValueError("SearchFailure timestamp must be timezone-aware")


def classify_search_error(error: BaseException) -> SearchFailure:
    """Convert an exception to a stable public value without using its text."""

    if isinstance(error, (CollectorCancelledError, asyncio.CancelledError)):
        return SearchFailure(
            SearchErrorCategory.CANCELLED,
            "search_cancelled",
            "Операция поиска отменена.",
        )
    if isinstance(error, ProviderNotConfiguredError):
        return SearchFailure(
            SearchErrorCategory.CONFIGURATION,
            "provider_not_configured",
            "Источник не настроен.",
        )
    if isinstance(error, ProviderCapabilityError):
        return SearchFailure(
            SearchErrorCategory.PROTOCOL,
            "provider_search_unsupported",
            "Источник не поддерживает поиск.",
        )
    if isinstance(error, ProviderPageContractError):
        return SearchFailure(
            SearchErrorCategory.PROTOCOL,
            error.code,
            SAFE_SEARCH_ERROR_MESSAGES.get(
                error.code,
                SAFE_SEARCH_ERROR_MESSAGES["provider_page_contract_error"],
            ),
        )
    if isinstance(error, (TimeoutError, asyncio.TimeoutError)):
        return SearchFailure(
            SearchErrorCategory.TIMEOUT,
            "provider_timeout",
            "Источник не завершил поиск за отведённое время.",
            retryable=True,
        )
    if isinstance(error, AsyncHttpResponseTooLargeError):
        return _http_failure(
            error,
            SearchErrorCategory.PROTOCOL,
            "remote_response_too_large",
            "Ответ источника превышает допустимый размер.",
        )
    if isinstance(error, AsyncHttpStatusError):
        status = error.status_code
        if status == 401:
            values = (
                SearchErrorCategory.AUTHENTICATION,
                "provider_authentication_failed",
                "Источник отклонил данные аутентификации.",
            )
        elif status == 403:
            values = (
                SearchErrorCategory.AUTHORIZATION,
                "provider_access_forbidden",
                "Источник запретил доступ к операции.",
            )
        elif status == 429:
            values = (
                SearchErrorCategory.RATE_LIMIT,
                "provider_rate_limited",
                "Источник временно ограничил частоту запросов.",
            )
        elif status is not None and status >= 500:
            values = (
                SearchErrorCategory.REMOTE_SERVICE,
                "provider_service_unavailable",
                "Сервис источника временно недоступен.",
            )
        else:
            values = (
                SearchErrorCategory.PROTOCOL,
                "provider_http_error",
                "Источник вернул неподдерживаемый ответ.",
            )
        return _http_failure(error, *values)
    if isinstance(error, AsyncHttpTransportError):
        return _http_failure(
            error,
            SearchErrorCategory.NETWORK,
            "provider_network_error",
            "Не удалось безопасно получить ответ источника.",
        )
    if isinstance(error, AsyncHttpError):
        return _http_failure(
            error,
            SearchErrorCategory.REMOTE_SERVICE,
            "provider_remote_error",
            "Источник завершил операцию с ошибкой.",
        )
    return SearchFailure(
        SearchErrorCategory.INTERNAL,
        "provider_internal_error",
        "Источник завершил поиск с безопасно скрытой ошибкой.",
    )


def _http_failure(
    error: AsyncHttpError,
    category: SearchErrorCategory,
    code: str,
    message: str,
) -> SearchFailure:
    return SearchFailure(
        category=category,
        code=code,
        message=message,
        attempts=max(1, int(error.attempts)),
        retryable=bool(error.transient),
        http_status=error.status_code,
    )


def safe_search_error_fields(
    code: str,
    *,
    default_code: str = "provider_internal_error",
) -> tuple[str, str]:
    """Return only an allowlisted code and its fixed public message."""

    normalized = code.strip().casefold()
    if normalized not in SAFE_SEARCH_ERROR_MESSAGES:
        normalized = default_code
    return normalized, SAFE_SEARCH_ERROR_MESSAGES[normalized]


def safe_provider_display_name(value: str, *, provider_id: str = "") -> str:
    """Bound a provider label and discard values that resemble secret metadata."""

    normalized = " ".join(str(value).split())
    if (
        not normalized
        or len(normalized) > 200
        or any(marker in normalized.casefold() for marker in _SENSITIVE_PUBLIC_MARKERS)
    ):
        fallback = " ".join(str(provider_id).split())
        if (
            not fallback
            or len(fallback) > 120
            or any(marker in fallback.casefold() for marker in _SENSITIVE_PUBLIC_MARKERS)
        ):
            return "Источник"
        return fallback.upper()
    return normalized


def safe_provider_warnings(values: tuple[str, ...]) -> tuple[str, ...]:
    """Keep bounded provider warnings while replacing secret-shaped metadata."""

    result: list[str] = []
    for value in values[:20]:
        normalized = " ".join(str(value).split())
        if not normalized:
            continue
        if len(normalized) > 300 or any(
            marker in normalized.casefold() for marker in _SENSITIVE_PUBLIC_MARKERS
        ):
            normalized = _SAFE_PROVIDER_WARNING
        result.append(normalized)
    return tuple(result)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


__all__ = [
    "SAFE_SEARCH_ERROR_MESSAGES",
    "SearchErrorCategory",
    "SearchFailure",
    "classify_search_error",
    "safe_provider_display_name",
    "safe_provider_warnings",
    "safe_search_error_fields",
]
