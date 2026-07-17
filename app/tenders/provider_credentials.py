"""Safe application commands for canonical tender-provider credentials.

This module owns no persistence. Values cross it only on an explicit save command;
stored values remain behind :mod:`app.security.secrets` and runtime adapters.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
import os
from threading import RLock
from typing import Protocol

from app.security.secrets import (
    SecretErrorCategory,
    SecretOperationError,
    delete_secret as delete_keyring_secret,
    has_secret as has_keyring_secret,
    save_secret as save_keyring_secret,
)
from app.tenders.collector.provider_definitions import canonical_provider_id
from app.tenders.providers.commercial_catalog import (
    default_commercial_provider_definitions,
)
from app.tenders.providers.mos_supplier_config import MOS_SUPPLIER_KEYRING_SECRET


class CredentialState(StrEnum):
    NOT_CONFIGURED = "not_configured"
    CONFIGURED = "configured"
    ENVIRONMENT_OVERRIDE = "environment_override"
    BACKEND_UNAVAILABLE = "backend_unavailable"
    INVALID_REQUEST = "invalid_request"


class CredentialCommandStatus(StrEnum):
    SAVED = "saved"
    REPLACED = "replaced"
    DELETED = "deleted"
    ALREADY_MISSING = "already_missing"
    REPLACEMENT_REQUIRED = "replacement_required"
    ENVIRONMENT_OVERRIDE = "environment_override"
    BACKEND_UNAVAILABLE = "backend_unavailable"
    ACCESS_DENIED = "access_denied"
    INVALID_INPUT = "invalid_input"
    OPERATION_FAILED = "operation_failed"


class CredentialErrorCategory(StrEnum):
    NONE = "none"
    BACKEND_UNAVAILABLE = "backend_unavailable"
    ACCESS_DENIED = "access_denied"
    INVALID_INPUT = "invalid_input"
    NOT_CONFIGURED = "not_configured"
    OPERATION_FAILED = "operation_failed"


@dataclass(frozen=True, slots=True)
class CredentialDescriptor:
    provider_id: str
    secret_name: str
    keyring_name: str
    environment_variable: str

    def __post_init__(self) -> None:
        values = (
            self.provider_id,
            self.secret_name,
            self.keyring_name,
            self.environment_variable,
        )
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ValueError("credential descriptor values must not be empty")
        object.__setattr__(self, "provider_id", self.provider_id.strip().casefold())
        object.__setattr__(self, "secret_name", self.secret_name.strip().casefold())
        object.__setattr__(self, "keyring_name", self.keyring_name.strip())
        object.__setattr__(
            self,
            "environment_variable",
            self.environment_variable.strip(),
        )


@dataclass(frozen=True, slots=True)
class CredentialStateResult:
    provider_id: str
    secret_name: str
    state: CredentialState
    message: str
    observed_at: str
    protected_store_configured: bool = False
    environment_override: bool = False


@dataclass(frozen=True, slots=True)
class CredentialCommandResult:
    provider_id: str
    secret_name: str
    status: CredentialCommandStatus
    state: CredentialState
    error_category: CredentialErrorCategory
    message: str
    observed_at: str


class CredentialBackend(Protocol):
    def has(self, name: str) -> bool: ...

    def save(self, name: str, value: str) -> None: ...

    def delete(self, name: str) -> None: ...


class KeyringCredentialBackend:
    """Thin application adapter over the existing protected-store owner."""

    def has(self, name: str) -> bool:
        return has_keyring_secret(name)

    def save(self, name: str, value: str) -> None:
        save_keyring_secret(name, value)

    def delete(self, name: str) -> None:
        delete_keyring_secret(name)


def provider_credential_descriptors() -> tuple[CredentialDescriptor, ...]:
    """Build the allowlist from existing provider definitions and account names."""

    descriptors = [
        CredentialDescriptor(
            "mos_supplier",
            "api_key",
            MOS_SUPPLIER_KEYRING_SECRET,
            "CORTERIS_MOS_API_KEY",
        )
    ]
    descriptors.extend(
        CredentialDescriptor(
            definition.provider_id,
            "api_key",
            definition.keyring_secret_name,
            definition.api_key_environment_variable,
        )
        for definition in default_commercial_provider_definitions()
    )
    _validate_descriptors(descriptors)
    return tuple(descriptors)


class ProviderCredentialService:
    """Save, inspect and delete provider credentials without value readback."""

    MAX_SECRET_LENGTH = 8192

    def __init__(
        self,
        backend: CredentialBackend | None = None,
        *,
        environment: Mapping[str, str] | None = None,
        descriptors: Sequence[CredentialDescriptor] | None = None,
    ) -> None:
        self._backend = backend or KeyringCredentialBackend()
        self._environment = environment if environment is not None else os.environ
        selected = tuple(descriptors or provider_credential_descriptors())
        _validate_descriptors(selected)
        self._descriptors = {(item.provider_id, item.secret_name): item for item in selected}
        self._lock = RLock()

    def has_secret(
        self,
        provider_id: str,
        secret_name: str,
    ) -> CredentialStateResult:
        descriptor = self._resolve(provider_id, secret_name)
        if descriptor is None:
            return _invalid_state()
        if self._environment_override(descriptor):
            return _state_result(
                descriptor,
                CredentialState.ENVIRONMENT_OVERRIDE,
                "Credential задан runtime environment override.",
                environment_override=True,
            )
        try:
            configured = self._backend.has(descriptor.keyring_name)
        except Exception as exc:
            category = _error_category(exc)
            return _state_result(
                descriptor,
                CredentialState.BACKEND_UNAVAILABLE,
                _safe_error_message(category),
            )
        return _state_result(
            descriptor,
            CredentialState.CONFIGURED if configured else CredentialState.NOT_CONFIGURED,
            "Credential настроен." if configured else "Credential не настроен.",
            protected_store_configured=configured,
        )

    def save_secret(
        self,
        provider_id: str,
        secret_name: str,
        value: str,
        *,
        replace: bool = False,
    ) -> CredentialCommandResult:
        descriptor = self._resolve(provider_id, secret_name)
        if descriptor is None or not _valid_secret_value(value, self.MAX_SECRET_LENGTH):
            return _invalid_command()
        if self._environment_override(descriptor):
            return _command_result(
                descriptor,
                CredentialCommandStatus.ENVIRONMENT_OVERRIDE,
                CredentialState.ENVIRONMENT_OVERRIDE,
                CredentialErrorCategory.NONE,
                "Runtime environment override активен; protected store не изменён.",
            )
        with self._lock:
            try:
                configured = self._backend.has(descriptor.keyring_name)
                if configured and not replace:
                    return _command_result(
                        descriptor,
                        CredentialCommandStatus.REPLACEMENT_REQUIRED,
                        CredentialState.CONFIGURED,
                        CredentialErrorCategory.NONE,
                        "Для замены требуется явное подтверждение.",
                    )
                self._backend.save(descriptor.keyring_name, value)
            except Exception as exc:
                return _backend_failure(descriptor, exc)
        return _command_result(
            descriptor,
            (CredentialCommandStatus.REPLACED if configured else CredentialCommandStatus.SAVED),
            CredentialState.CONFIGURED,
            CredentialErrorCategory.NONE,
            "Credential заменён." if configured else "Credential сохранён.",
        )

    def delete_secret(
        self,
        provider_id: str,
        secret_name: str,
    ) -> CredentialCommandResult:
        descriptor = self._resolve(provider_id, secret_name)
        if descriptor is None:
            return _invalid_command()
        environment_override = self._environment_override(descriptor)
        with self._lock:
            configured: bool | None = None
            if not environment_override:
                try:
                    configured = self._backend.has(descriptor.keyring_name)
                except Exception:
                    # A delete attempt can still succeed and can return a more
                    # precise bounded error than the presence probe.
                    configured = None
                if configured is False:
                    return _command_result(
                        descriptor,
                        CredentialCommandStatus.ALREADY_MISSING,
                        CredentialState.NOT_CONFIGURED,
                        CredentialErrorCategory.NOT_CONFIGURED,
                        "Credential уже отсутствует.",
                    )
            try:
                self._backend.delete(descriptor.keyring_name)
            except Exception as exc:
                return _backend_failure(descriptor, exc)
        return _command_result(
            descriptor,
            CredentialCommandStatus.DELETED,
            (
                CredentialState.ENVIRONMENT_OVERRIDE
                if environment_override
                else CredentialState.NOT_CONFIGURED
            ),
            CredentialErrorCategory.NONE,
            (
                "Protected-store credential удалён; environment override остаётся активным."
                if environment_override
                else "Credential удалён."
            ),
        )

    def _resolve(
        self,
        provider_id: str,
        secret_name: str,
    ) -> CredentialDescriptor | None:
        try:
            canonical = canonical_provider_id(provider_id)
        except (KeyError, TypeError, ValueError):
            return None
        normalized_name = str(secret_name).strip().casefold()
        return self._descriptors.get((canonical, normalized_name))

    def _environment_override(self, descriptor: CredentialDescriptor) -> bool:
        value = self._environment.get(descriptor.environment_variable)
        return _valid_secret_value(value, self.MAX_SECRET_LENGTH)


def _validate_descriptors(descriptors: Sequence[CredentialDescriptor]) -> None:
    identities = [(item.provider_id, item.secret_name) for item in descriptors]
    keyring_names = [item.keyring_name.casefold() for item in descriptors]
    environment_names = [item.environment_variable.casefold() for item in descriptors]
    if len(identities) != len(set(identities)):
        raise ValueError("credential descriptor identities must be unique")
    if len(keyring_names) != len(set(keyring_names)):
        raise ValueError("credential keyring names must be unique")
    if len(environment_names) != len(set(environment_names)):
        raise ValueError("credential environment names must be unique")


def _valid_secret_value(value: object, maximum: int) -> bool:
    if not isinstance(value, str) or not value or not value.strip() or len(value) > maximum:
        return False
    return not any(ord(character) < 32 or ord(character) == 127 for character in value)


def _invalid_state() -> CredentialStateResult:
    return CredentialStateResult(
        provider_id="unknown",
        secret_name="unknown",
        state=CredentialState.INVALID_REQUEST,
        message="Credential request отклонён безопасной валидацией.",
        observed_at=_utc_now(),
    )


def _invalid_command() -> CredentialCommandResult:
    return CredentialCommandResult(
        provider_id="unknown",
        secret_name="unknown",
        status=CredentialCommandStatus.INVALID_INPUT,
        state=CredentialState.INVALID_REQUEST,
        error_category=CredentialErrorCategory.INVALID_INPUT,
        message="Credential request отклонён безопасной валидацией.",
        observed_at=_utc_now(),
    )


def _state_result(
    descriptor: CredentialDescriptor,
    state: CredentialState,
    message: str,
    *,
    protected_store_configured: bool = False,
    environment_override: bool = False,
) -> CredentialStateResult:
    return CredentialStateResult(
        provider_id=descriptor.provider_id,
        secret_name=descriptor.secret_name,
        state=state,
        message=message,
        observed_at=_utc_now(),
        protected_store_configured=protected_store_configured,
        environment_override=environment_override,
    )


def _command_result(
    descriptor: CredentialDescriptor,
    status: CredentialCommandStatus,
    state: CredentialState,
    error_category: CredentialErrorCategory,
    message: str,
) -> CredentialCommandResult:
    return CredentialCommandResult(
        provider_id=descriptor.provider_id,
        secret_name=descriptor.secret_name,
        status=status,
        state=state,
        error_category=error_category,
        message=message,
        observed_at=_utc_now(),
    )


def _backend_failure(
    descriptor: CredentialDescriptor,
    exc: Exception,
) -> CredentialCommandResult:
    category = _error_category(exc)
    status = {
        CredentialErrorCategory.BACKEND_UNAVAILABLE: (CredentialCommandStatus.BACKEND_UNAVAILABLE),
        CredentialErrorCategory.ACCESS_DENIED: CredentialCommandStatus.ACCESS_DENIED,
    }.get(category, CredentialCommandStatus.OPERATION_FAILED)
    return _command_result(
        descriptor,
        status,
        CredentialState.BACKEND_UNAVAILABLE,
        category,
        _safe_error_message(category),
    )


def _error_category(exc: Exception) -> CredentialErrorCategory:
    if isinstance(exc, SecretOperationError):
        return {
            SecretErrorCategory.BACKEND_UNAVAILABLE: (CredentialErrorCategory.BACKEND_UNAVAILABLE),
            SecretErrorCategory.ACCESS_DENIED: CredentialErrorCategory.ACCESS_DENIED,
            SecretErrorCategory.OPERATION_FAILED: CredentialErrorCategory.OPERATION_FAILED,
        }[exc.category]
    if isinstance(exc, PermissionError):
        return CredentialErrorCategory.ACCESS_DENIED
    return CredentialErrorCategory.OPERATION_FAILED


def _safe_error_message(category: CredentialErrorCategory) -> str:
    return {
        CredentialErrorCategory.BACKEND_UNAVAILABLE: ("Защищённое хранилище временно недоступно."),
        CredentialErrorCategory.ACCESS_DENIED: ("Доступ к защищённому хранилищу запрещён."),
        CredentialErrorCategory.INVALID_INPUT: (
            "Credential request отклонён безопасной валидацией."
        ),
        CredentialErrorCategory.NOT_CONFIGURED: "Credential не настроен.",
        CredentialErrorCategory.OPERATION_FAILED: (
            "Операция с защищённым хранилищем не выполнена."
        ),
        CredentialErrorCategory.NONE: "",
    }[category]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


__all__ = [
    "CredentialBackend",
    "CredentialCommandResult",
    "CredentialCommandStatus",
    "CredentialDescriptor",
    "CredentialErrorCategory",
    "CredentialState",
    "CredentialStateResult",
    "KeyringCredentialBackend",
    "ProviderCredentialService",
    "provider_credential_descriptors",
]
