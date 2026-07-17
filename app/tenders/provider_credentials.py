"""Safe application commands for canonical tender-provider credentials.

This module owns no persistence. Values cross it only on an explicit save command;
stored values remain behind :mod:`app.security.secrets` and runtime adapters.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
import os
import hashlib
import json
from threading import RLock
from typing import Protocol

from app.security.secrets import (
    SecretErrorCategory,
    SecretOperationError,
    delete_secret as delete_keyring_secret,
    has_secret as has_keyring_secret,
    load_secret as load_keyring_secret,
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
    environment_variable: str | None

    def __post_init__(self) -> None:
        values = (self.provider_id, self.secret_name, self.keyring_name)
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ValueError("credential descriptor values must not be empty")
        if self.environment_variable is not None and (
            not isinstance(self.environment_variable, str) or not self.environment_variable.strip()
        ):
            raise ValueError("credential descriptor values must not be empty")
        object.__setattr__(self, "provider_id", self.provider_id.strip().casefold())
        object.__setattr__(self, "secret_name", self.secret_name.strip().casefold())
        object.__setattr__(self, "keyring_name", self.keyring_name.strip())
        if self.environment_variable is not None:
            object.__setattr__(self, "environment_variable", self.environment_variable.strip())

    @property
    def environment_name(self) -> str | None:
        return self.environment_variable

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(
            {
                "version": 1,
                "provider_id": self.provider_id,
                "secret_name": self.secret_name,
                "keyring_name": self.keyring_name,
                "environment_variable": self.environment_variable,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class RuntimeCredentialSecret:
    provider_id: str
    secret_name: str
    value: str = field(repr=False)
    descriptor_fingerprint: str


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

    def get(self, name: str) -> str | None: ...


class KeyringCredentialBackend:
    """Thin application adapter over the existing protected-store owner."""

    def has(self, name: str) -> bool:
        return has_keyring_secret(name)

    def save(self, name: str, value: str) -> None:
        save_keyring_secret(name, value)

    def delete(self, name: str) -> None:
        delete_keyring_secret(name)

    def get(self, name: str) -> str | None:
        return load_keyring_secret(name)


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


def manual_credential_descriptors(
    provider_id: str,
    secret_names: Sequence[str],
) -> tuple[CredentialDescriptor, ...]:
    normalized = _manual_provider_id(provider_id)
    result: list[CredentialDescriptor] = []
    for value in secret_names:
        secret_name = str(value).strip().casefold()
        if secret_name not in {"api_key", "username", "password"}:
            raise ValueError("manual credential kind is invalid")
        result.append(
            CredentialDescriptor(
                normalized,
                secret_name,
                f"collector.{normalized}.{secret_name}",
                None,
            )
        )
    _validate_descriptors(result)
    return tuple(result)


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

    def resolve_runtime_secret(
        self,
        provider_id: str,
        secret_name: str,
    ) -> RuntimeCredentialSecret:
        descriptor = self._resolve(provider_id, secret_name)
        if descriptor is None:
            raise ValueError("credential request is invalid")
        environment_value = (
            self._environment.get(descriptor.environment_variable)
            if descriptor.environment_variable is not None
            else None
        )
        if _valid_secret_value(environment_value, self.MAX_SECRET_LENGTH):
            value = environment_value
        else:
            getter = getattr(self._backend, "get", None)
            if getter is None:
                raise RuntimeError("credential runtime resolution is unavailable")
            value = getter(descriptor.keyring_name)
        if not _valid_secret_value(value, self.MAX_SECRET_LENGTH):
            raise RuntimeError("credential is not configured")
        assert isinstance(value, str)
        return RuntimeCredentialSecret(
            descriptor.provider_id,
            descriptor.secret_name,
            value,
            descriptor.fingerprint,
        )

    def credential_marker(
        self,
        provider_id: str,
        secret_names: Sequence[str],
    ) -> str:
        markers: list[dict[str, object]] = []
        for secret_name in secret_names:
            descriptor = self._resolve(provider_id, secret_name)
            if descriptor is None:
                raise ValueError("credential request is invalid")
            state = self.has_secret(descriptor.provider_id, descriptor.secret_name)
            markers.append(
                {
                    "descriptor": descriptor.fingerprint,
                    "state": state.state.value,
                    "protected_store": state.protected_store_configured,
                    "environment": state.environment_override,
                }
            )
        payload = json.dumps(markers, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _resolve(
        self,
        provider_id: str,
        secret_name: str,
    ) -> CredentialDescriptor | None:
        try:
            normalized_provider = str(provider_id).strip().casefold()
            canonical = (
                _manual_provider_id(normalized_provider)
                if normalized_provider.startswith("manual_")
                else canonical_provider_id(normalized_provider)
            )
        except (KeyError, TypeError, ValueError):
            return None
        normalized_name = str(secret_name).strip().casefold()
        descriptor = self._descriptors.get((canonical, normalized_name))
        if (
            descriptor is None
            and canonical.startswith("manual_")
            and normalized_name in {"api_key", "username", "password"}
        ):
            descriptor = manual_credential_descriptors(canonical, (normalized_name,))[0]
            self._descriptors[(canonical, normalized_name)] = descriptor
        return descriptor

    def _environment_override(self, descriptor: CredentialDescriptor) -> bool:
        if descriptor.environment_variable is None:
            return False
        value = self._environment.get(descriptor.environment_variable)
        return _valid_secret_value(value, self.MAX_SECRET_LENGTH)


def _validate_descriptors(descriptors: Sequence[CredentialDescriptor]) -> None:
    identities = [(item.provider_id, item.secret_name) for item in descriptors]
    keyring_names = [item.keyring_name.casefold() for item in descriptors]
    environment_names = [
        item.environment_variable.casefold()
        for item in descriptors
        if item.environment_variable is not None
    ]
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


def _manual_provider_id(value: object) -> str:
    normalized = str(value).strip().casefold()
    if (
        len(normalized) != 39
        or not normalized.startswith("manual_")
        or any(character not in "0123456789abcdef" for character in normalized[7:])
    ):
        raise ValueError("manual provider id is invalid")
    return normalized


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
    "RuntimeCredentialSecret",
    "manual_credential_descriptors",
    "provider_credential_descriptors",
]
