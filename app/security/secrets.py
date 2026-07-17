from __future__ import annotations

from enum import StrEnum

import keyring

SERVICE = "CorterisTenderAI"


class SecretErrorCategory(StrEnum):
    """Bounded public categories for protected-store failures."""

    BACKEND_UNAVAILABLE = "backend_unavailable"
    ACCESS_DENIED = "access_denied"
    OPERATION_FAILED = "operation_failed"


class SecretOperationError(RuntimeError):
    """Sanitized keyring failure that never includes backend diagnostic text."""

    def __init__(self, category: SecretErrorCategory) -> None:
        self.category = category
        super().__init__(_safe_error_message(category))


def save_secret(name: str, value: str) -> None:
    try:
        keyring.set_password(SERVICE, name, value)
    except Exception as exc:
        _raise_sanitized(exc)


def load_secret(name: str) -> str | None:
    """Load a value for an explicit runtime adapter, never for UI display."""

    try:
        return keyring.get_password(SERVICE, name)
    except Exception as exc:
        _raise_sanitized(exc)


def has_secret(name: str) -> bool:
    """Return presence metadata without exposing the stored value to callers."""

    try:
        return keyring.get_password(SERVICE, name) is not None
    except Exception as exc:
        _raise_sanitized(exc)


def delete_secret(name: str) -> None:
    try:
        keyring.delete_password(SERVICE, name)
    except keyring.errors.PasswordDeleteError:
        pass
    except Exception as exc:
        _raise_sanitized(exc)


def _raise_sanitized(exc: Exception) -> None:
    if isinstance(exc, PermissionError):
        category = SecretErrorCategory.ACCESS_DENIED
    elif isinstance(exc, (keyring.errors.NoKeyringError, keyring.errors.InitError)):
        category = SecretErrorCategory.BACKEND_UNAVAILABLE
    else:
        category = SecretErrorCategory.OPERATION_FAILED
    raise SecretOperationError(category) from None


def _safe_error_message(category: SecretErrorCategory) -> str:
    return {
        SecretErrorCategory.BACKEND_UNAVAILABLE: ("Защищённое хранилище временно недоступно."),
        SecretErrorCategory.ACCESS_DENIED: "Доступ к защищённому хранилищу запрещён.",
        SecretErrorCategory.OPERATION_FAILED: ("Операция с защищённым хранилищем не выполнена."),
    }[category]


__all__ = [
    "SERVICE",
    "SecretErrorCategory",
    "SecretOperationError",
    "delete_secret",
    "has_secret",
    "load_secret",
    "save_secret",
]
