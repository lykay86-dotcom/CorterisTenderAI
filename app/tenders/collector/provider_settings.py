"""Canonical persistent non-secret settings for Tender Collector sources."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import StrEnum
import json
import os
from pathlib import Path
from threading import RLock
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from app.tenders.collector.provider_definitions import (
    canonical_provider_definitions,
    canonical_provider_id,
    provider_aliases,
)
from app.tenders.collector.manual_provider_registration import (
    ManualProviderConflictError,
    ManualProviderErrorCategory,
    ManualProviderExecutionError,
    ManualProviderLifecycle,
    ManualProviderRegistration,
    manual_display_name_key,
    validate_manual_registration_uniqueness,
)
from app.tenders.provider_base import ProviderDescriptor


class ProviderSettingsLoadStatus(StrEnum):
    MISSING = "missing"
    CURRENT = "current"
    MIGRATED_V2 = "migrated_v2"
    MIGRATED_SPLIT_V1 = "migrated_split_v1"
    CORRUPT = "corrupt"
    UNSUPPORTED_FUTURE = "unsupported_future"


class ProviderSettingOrigin(StrEnum):
    DEFAULT = "default"
    PERSISTED = "persisted"
    LEGACY_MIGRATED = "legacy_migrated"
    ENVIRONMENT = "environment"


class ProviderSettingsMutationError(RuntimeError):
    """Raised when unsafe persisted state blocks a settings mutation."""


@dataclass(frozen=True, slots=True)
class ProviderConfiguration:
    """Persistable commercial configuration that contains no credentials."""

    access_confirmed: bool = False
    api_base_url: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.access_confirmed, bool):
            raise TypeError("access_confirmed must be a boolean")
        object.__setattr__(self, "api_base_url", _normalize_api_base_url(self.api_base_url))


@dataclass(frozen=True, slots=True)
class ProviderEnablement:
    """A single user-controlled provider switch."""

    provider_id: str
    enabled: bool

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id must not be empty")


@dataclass(frozen=True, slots=True)
class ProviderSettingsRecord:
    provider_id: str
    enabled: bool | None = None
    configuration: ProviderConfiguration = field(default_factory=ProviderConfiguration)
    enabled_origin: ProviderSettingOrigin = ProviderSettingOrigin.PERSISTED
    configuration_origin: ProviderSettingOrigin = ProviderSettingOrigin.PERSISTED
    configuration_editable: bool = True

    def __post_init__(self) -> None:
        normalized = self.provider_id.strip().casefold()
        if not normalized:
            raise ValueError("provider_id must not be empty")
        if self.enabled is not None and not isinstance(self.enabled, bool):
            raise TypeError("enabled must be a boolean or None")
        object.__setattr__(self, "provider_id", normalized)


@dataclass(frozen=True, slots=True)
class ProviderSettingsLoadResult:
    records: tuple[ProviderSettingsRecord, ...]
    status: ProviderSettingsLoadStatus
    source_schema_version: int | None
    warnings: tuple[str, ...] = ()
    manual_registrations: tuple[ManualProviderRegistration, ...] = ()

    def get(self, provider_id: str) -> ProviderSettingsRecord:
        normalized = _canonical_or_normalized(provider_id)
        for record in self.records:
            if record.provider_id == normalized:
                return record
        raise KeyError(provider_id)


@dataclass(frozen=True, slots=True)
class ProviderSettingsSnapshot:
    providers: tuple[ProviderSettingsRecord, ...]
    status: ProviderSettingsLoadStatus
    warnings: tuple[str, ...] = ()
    manual_registrations: tuple[ManualProviderRegistration, ...] = ()

    def get(self, provider_id: str) -> ProviderSettingsRecord:
        normalized = str(provider_id).strip().casefold()
        try:
            canonical = canonical_provider_id(normalized)
        except KeyError:
            if normalized not in {item.provider_id for item in self.manual_registrations}:
                raise
            canonical = normalized
        for provider in self.providers:
            if provider.provider_id == canonical:
                return provider
        raise KeyError(provider_id)

    def get_manual(self, provider_id: str) -> ManualProviderRegistration:
        normalized = str(provider_id).strip().casefold()
        for registration in self.manual_registrations:
            if registration.provider_id == normalized:
                return registration
        raise KeyError(provider_id)

    @property
    def enabled_provider_ids(self) -> tuple[str, ...]:
        if self.status in {
            ProviderSettingsLoadStatus.CORRUPT,
            ProviderSettingsLoadStatus.UNSUPPORTED_FUTURE,
        }:
            return ()
        return tuple(item.provider_id for item in self.providers if item.enabled)

    def resolve_provider_ids(self, provider_ids: object) -> tuple[str, ...]:
        if not isinstance(provider_ids, (list, tuple, set, frozenset)):
            raise TypeError("provider_ids must be an iterable selection")
        manual_ids = {item.provider_id for item in self.manual_registrations}
        resolved: list[str] = []
        seen: set[str] = set()
        for value in provider_ids:
            normalized = str(value).strip().casefold()
            try:
                canonical = canonical_provider_id(normalized)
            except KeyError:
                if normalized not in manual_ids:
                    raise KeyError(value) from None
                canonical = normalized
            if canonical not in seen:
                seen.add(canonical)
                resolved.append(canonical)
        return tuple(resolved)

    def assert_runnable_provider_ids(self, provider_ids: object) -> tuple[str, ...]:
        resolved = self.resolve_provider_ids(provider_ids)
        manual_ids = {item.provider_id for item in self.manual_registrations}
        if any(provider_id in manual_ids for provider_id in resolved):
            raise ManualProviderExecutionError()
        return resolved

    def public_payload(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "providers": [
                {
                    "provider_id": item.provider_id,
                    "enabled": item.enabled,
                    "enabled_origin": item.enabled_origin.value,
                    "access_confirmed": item.configuration.access_confirmed,
                    "api_base_url": item.configuration.api_base_url,
                    "configuration_origin": item.configuration_origin.value,
                    "configuration_editable": item.configuration_editable,
                }
                for item in self.providers
            ],
            "manual_registrations": [
                {
                    "provider_id": item.provider_id,
                    "lifecycle_state": item.lifecycle_state.value,
                    "enabled": False,
                    "registration_only": True,
                }
                for item in self.manual_registrations
            ],
            "warnings": list(self.warnings),
        }


def create_provider_settings_snapshot(
    repository: "ProviderEnablementRepository",
    *,
    environment: Mapping[str, str] | None = None,
) -> ProviderSettingsSnapshot:
    """Resolve one immutable non-secret settings snapshot without network I/O."""

    from app.tenders.providers.commercial_catalog import (
        default_commercial_provider_definitions,
    )

    loaded = repository.load_result()
    persisted = {record.provider_id: record for record in loaded.records}
    commercial = {
        item.provider_id.casefold(): item for item in default_commercial_provider_definitions()
    }
    values = environment if environment is not None else os.environ
    warnings = list(loaded.warnings)
    resolved: list[ProviderSettingsRecord] = []
    for descriptor in canonical_provider_definitions():
        provider_id = descriptor.id.casefold()
        stored = persisted.get(provider_id)
        enabled = (
            stored.enabled
            if stored is not None and stored.enabled is not None
            else descriptor.enabled_by_default
        )
        enabled_origin = (
            stored.enabled_origin
            if stored is not None and stored.enabled is not None
            else ProviderSettingOrigin.DEFAULT
        )
        configuration = stored.configuration if stored is not None else ProviderConfiguration()
        configuration_origin = (
            stored.configuration_origin
            if stored is not None and stored.configuration != ProviderConfiguration()
            else ProviderSettingOrigin.DEFAULT
        )
        configuration_editable = True

        definition = commercial.get(provider_id)
        if definition is not None:
            environment_enabled = _optional_environment_bool(
                values,
                definition.enabled_environment_variable,
            )
            if environment_enabled is not None:
                enabled = environment_enabled
                enabled_origin = ProviderSettingOrigin.ENVIRONMENT

            environment_access = _optional_environment_bool(
                values,
                definition.access_confirmed_environment_variable,
            )
            endpoint_key = definition.api_base_url_environment_variable
            endpoint_is_overridden = endpoint_key in values
            if environment_access is not None or endpoint_is_overridden:
                access_confirmed = (
                    environment_access
                    if environment_access is not None
                    else configuration.access_confirmed
                )
                endpoint = (
                    str(values.get(endpoint_key, ""))
                    if endpoint_is_overridden
                    else configuration.api_base_url
                )
                try:
                    configuration = ProviderConfiguration(
                        access_confirmed=access_confirmed,
                        api_base_url=endpoint,
                    )
                except (TypeError, ValueError):
                    configuration = ProviderConfiguration(
                        access_confirmed=access_confirmed,
                    )
                    warnings.append(
                        f"Environment endpoint for {provider_id} is invalid and was ignored."
                    )
                configuration_origin = ProviderSettingOrigin.ENVIRONMENT
                configuration_editable = False

        if loaded.status in {
            ProviderSettingsLoadStatus.CORRUPT,
            ProviderSettingsLoadStatus.UNSUPPORTED_FUTURE,
        }:
            enabled = False
            configuration_editable = False

        resolved.append(
            ProviderSettingsRecord(
                provider_id=provider_id,
                enabled=bool(enabled),
                configuration=configuration,
                enabled_origin=enabled_origin,
                configuration_origin=configuration_origin,
                configuration_editable=configuration_editable,
            )
        )
    for registration in loaded.manual_registrations:
        resolved.append(
            ProviderSettingsRecord(
                provider_id=registration.provider_id,
                enabled=False,
                configuration=ProviderConfiguration(),
                enabled_origin=ProviderSettingOrigin.PERSISTED,
                configuration_origin=ProviderSettingOrigin.PERSISTED,
                configuration_editable=False,
            )
        )
    return ProviderSettingsSnapshot(
        providers=tuple(resolved),
        status=loaded.status,
        warnings=tuple(warnings),
        manual_registrations=loaded.manual_registrations,
    )


class ProviderEnablementRepository:
    """Own schema-v3 source settings and read v1/v2 state compatibly."""

    SCHEMA_VERSION = 3

    def __init__(
        self,
        path: str | Path,
        *,
        legacy_settings_path: str | Path | None = None,
    ) -> None:
        self.path = Path(path).expanduser()
        self.legacy_settings_path = (
            Path(legacy_settings_path).expanduser()
            if legacy_settings_path is not None
            else self.path.with_name("commercial_provider_settings.json")
        )
        self._lock = RLock()

    def load_result(self) -> ProviderSettingsLoadResult:
        with self._lock:
            return self._load_result_unlocked()

    def load(self) -> dict[str, bool]:
        result = self.load_result()
        return {
            record.provider_id: record.enabled
            for record in result.records
            if record.enabled is not None
        }

    def save(self, values: Mapping[str, bool]) -> None:
        normalized: dict[str, bool] = {}
        for provider_id, enabled in values.items():
            if not isinstance(enabled, bool):
                raise TypeError("provider enablement must be boolean")
            normalized[_canonical_or_normalized(str(provider_id))] = enabled

        def mutation(
            records: dict[str, ProviderSettingsRecord],
            _registrations: dict[str, ManualProviderRegistration],
        ) -> None:
            configurations = {
                provider_id: record.configuration for provider_id, record in records.items()
            }
            records.clear()
            for provider_id, enabled in normalized.items():
                records[provider_id] = ProviderSettingsRecord(
                    provider_id=provider_id,
                    enabled=enabled,
                    configuration=configurations.get(provider_id, ProviderConfiguration()),
                )

        self._mutate(mutation)

    def set_enabled(self, provider_id: str, enabled: bool) -> ProviderEnablement:
        normalized = _canonical_or_normalized(provider_id)
        if not isinstance(enabled, bool):
            raise TypeError("enabled must be a boolean")

        def mutation(
            records: dict[str, ProviderSettingsRecord],
            _registrations: dict[str, ManualProviderRegistration],
        ) -> None:
            previous = records.get(normalized, ProviderSettingsRecord(normalized))
            records[normalized] = replace(
                previous,
                enabled=enabled,
                enabled_origin=ProviderSettingOrigin.PERSISTED,
            )

        self._mutate(mutation)
        return ProviderEnablement(normalized, enabled)

    def set_configuration(
        self,
        provider_id: str,
        configuration: ProviderConfiguration,
    ) -> ProviderSettingsRecord:
        normalized = canonical_provider_id(provider_id)
        if not isinstance(configuration, ProviderConfiguration):
            raise TypeError("configuration must be ProviderConfiguration")

        def mutation(
            records: dict[str, ProviderSettingsRecord],
            _registrations: dict[str, ManualProviderRegistration],
        ) -> None:
            previous = records.get(normalized, ProviderSettingsRecord(normalized))
            records[normalized] = replace(
                previous,
                configuration=configuration,
                configuration_origin=ProviderSettingOrigin.PERSISTED,
            )

        self._mutate(mutation)
        return self.load_result().get(normalized)

    def register_manual_provider(
        self,
        registration: ManualProviderRegistration,
    ) -> ManualProviderRegistration:
        if not isinstance(registration, ManualProviderRegistration):
            raise TypeError("registration must be ManualProviderRegistration")

        def mutation(
            records: dict[str, ProviderSettingsRecord],
            registrations: dict[str, ManualProviderRegistration],
        ) -> None:
            if registration.provider_id in registrations or registration.provider_id in records:
                raise ManualProviderConflictError(ManualProviderErrorCategory.IDENTITY_COLLISION)
            candidate = tuple(registrations.values()) + (registration,)
            validate_manual_registration_uniqueness(candidate)
            _validate_manual_against_builtin_catalog(candidate)
            registrations[registration.provider_id] = registration

        self._mutate(mutation)
        return registration

    def update_manual_provider(
        self,
        registration: ManualProviderRegistration,
    ) -> ManualProviderRegistration:
        if not isinstance(registration, ManualProviderRegistration):
            raise TypeError("registration must be ManualProviderRegistration")

        def mutation(
            _records: dict[str, ProviderSettingsRecord],
            registrations: dict[str, ManualProviderRegistration],
        ) -> None:
            if registration.provider_id not in registrations:
                raise KeyError(registration.provider_id)
            candidate = tuple(
                registration if item.provider_id == registration.provider_id else item
                for item in registrations.values()
            )
            validate_manual_registration_uniqueness(candidate)
            _validate_manual_against_builtin_catalog(candidate)
            registrations[registration.provider_id] = registration

        self._mutate(mutation)
        return registration

    def is_enabled(self, descriptor: ProviderDescriptor) -> bool:
        result = self.load_result()
        if descriptor.id.strip().casefold() in {
            item.provider_id for item in result.manual_registrations
        }:
            return False
        values = {
            record.provider_id: record.enabled
            for record in result.records
            if record.enabled is not None
        }
        return values.get(descriptor.id.strip().casefold(), descriptor.enabled_by_default)

    def _load_result_unlocked(self) -> ProviderSettingsLoadResult:
        if not self.path.is_file():
            return self._load_without_canonical()
        try:
            payload = _read_json_object(self.path)
            version = _schema_version(payload)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            return ProviderSettingsLoadResult(
                records=(),
                status=ProviderSettingsLoadStatus.CORRUPT,
                source_schema_version=None,
                warnings=(f"Canonical provider settings are corrupt: {type(exc).__name__}",),
            )
        if version > self.SCHEMA_VERSION:
            return ProviderSettingsLoadResult(
                records=(),
                status=ProviderSettingsLoadStatus.UNSUPPORTED_FUTURE,
                source_schema_version=version,
            )
        if version == self.SCHEMA_VERSION:
            try:
                records, registrations = _decode_current(payload)
            except (ValueError, TypeError) as exc:
                return ProviderSettingsLoadResult(
                    records=(),
                    status=ProviderSettingsLoadStatus.CORRUPT,
                    source_schema_version=version,
                    warnings=(f"Canonical provider settings are corrupt: {type(exc).__name__}",),
                )
            return ProviderSettingsLoadResult(
                records=records,
                status=ProviderSettingsLoadStatus.CURRENT,
                source_schema_version=version,
                manual_registrations=registrations,
            )
        if version == 2:
            try:
                records = _decode_v2(payload)
            except (ValueError, TypeError) as exc:
                return ProviderSettingsLoadResult(
                    records=(),
                    status=ProviderSettingsLoadStatus.CORRUPT,
                    source_schema_version=version,
                    warnings=(f"Canonical provider settings are corrupt: {type(exc).__name__}",),
                )
            return ProviderSettingsLoadResult(
                records=records,
                status=ProviderSettingsLoadStatus.MIGRATED_V2,
                source_schema_version=version,
            )
        if version != 1:
            return ProviderSettingsLoadResult(
                records=(),
                status=ProviderSettingsLoadStatus.CORRUPT,
                source_schema_version=version,
                warnings=("Unsupported historical provider settings schema.",),
            )
        return self._migrate_split_v1(payload)

    def _load_without_canonical(self) -> ProviderSettingsLoadResult:
        if not self.legacy_settings_path.is_file():
            return ProviderSettingsLoadResult(
                records=(),
                status=ProviderSettingsLoadStatus.MISSING,
                source_schema_version=None,
            )
        return self._migrate_split_v1(None)

    def _migrate_split_v1(
        self,
        general_payload: Mapping[str, object] | None,
    ) -> ProviderSettingsLoadResult:
        warnings: list[str] = []
        try:
            enabled = (
                _decode_v1_general(general_payload, warnings) if general_payload is not None else {}
            )
            legacy_enabled, configurations = self._read_legacy_v1(warnings)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            return ProviderSettingsLoadResult(
                records=(),
                status=ProviderSettingsLoadStatus.CORRUPT,
                source_schema_version=1,
                warnings=(f"Split provider settings are corrupt: {type(exc).__name__}",),
            )
        for provider_id, value in legacy_enabled.items():
            if provider_id in enabled and enabled[provider_id] != value:
                warnings.append(
                    f"General enablement for {provider_id} overrides legacy commercial value."
                )
            enabled.setdefault(provider_id, value)
        ids = set(enabled) | set(configurations)
        records = tuple(
            ProviderSettingsRecord(
                provider_id=provider_id,
                enabled=enabled.get(provider_id),
                configuration=configurations.get(provider_id, ProviderConfiguration()),
                enabled_origin=ProviderSettingOrigin.LEGACY_MIGRATED,
                configuration_origin=ProviderSettingOrigin.LEGACY_MIGRATED,
            )
            for provider_id in sorted(ids)
        )
        return ProviderSettingsLoadResult(
            records=records,
            status=ProviderSettingsLoadStatus.MIGRATED_SPLIT_V1,
            source_schema_version=1,
            warnings=tuple(warnings),
        )

    def _read_legacy_v1(
        self,
        warnings: list[str],
    ) -> tuple[dict[str, bool], dict[str, ProviderConfiguration]]:
        if not self.legacy_settings_path.is_file():
            return {}, {}
        payload = _read_json_object(self.legacy_settings_path)
        if _schema_version(payload) != 1:
            raise ValueError("legacy commercial settings schema must be v1")
        raw_providers = payload.get("providers")
        if not isinstance(raw_providers, dict):
            raise TypeError("legacy commercial providers must be an object")
        enabled: dict[str, bool] = {}
        configurations: dict[str, ProviderConfiguration] = {}
        for raw_id, raw_value in _canonical_items(raw_providers, warnings):
            if not isinstance(raw_value, dict):
                raise TypeError("legacy commercial provider settings must be objects")
            raw_enabled = raw_value.get("enabled", False)
            raw_access = raw_value.get("access_confirmed", False)
            raw_url = raw_value.get("api_base_url", "")
            if not isinstance(raw_enabled, bool) or not isinstance(raw_access, bool):
                raise TypeError("legacy commercial booleans must be boolean")
            if not isinstance(raw_url, str):
                raise TypeError("legacy commercial endpoint must be a string")
            enabled[raw_id] = raw_enabled
            configurations[raw_id] = ProviderConfiguration(
                access_confirmed=raw_access,
                api_base_url=raw_url,
            )
        return enabled, configurations

    def _mutate(self, callback) -> None:
        with self._lock:
            result = self._load_result_unlocked()
            if result.status in {
                ProviderSettingsLoadStatus.CORRUPT,
                ProviderSettingsLoadStatus.UNSUPPORTED_FUTURE,
            }:
                raise ProviderSettingsMutationError(
                    f"Provider settings mutation blocked: {result.status.value}"
                )
            records = {record.provider_id: record for record in result.records}
            registrations = {
                registration.provider_id: registration
                for registration in result.manual_registrations
            }
            callback(records, registrations)
            if result.status is ProviderSettingsLoadStatus.MIGRATED_SPLIT_V1:
                self._backup_v1_sources()
            elif result.status is ProviderSettingsLoadStatus.MIGRATED_V2:
                self._backup_previous_source(2)
            self._write_current(records.values(), registrations.values())

    def _backup_v1_sources(self) -> None:
        existing = (self.path, self.legacy_settings_path)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        for source in existing:
            if not source.is_file():
                continue
            previous = tuple(source.parent.glob(f"{source.name}.v1-*.bak"))
            if previous:
                continue
            backup = source.with_name(f"{source.name}.v1-{timestamp}.bak")
            with backup.open("xb") as handle:
                handle.write(source.read_bytes())

    def _backup_previous_source(self, version: int) -> None:
        if not self.path.is_file():
            return
        previous = tuple(self.path.parent.glob(f"{self.path.name}.v{version}-*.bak"))
        if previous:
            return
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = self.path.with_name(f"{self.path.name}.v{version}-{timestamp}.bak")
        with backup.open("xb") as handle:
            handle.write(self.path.read_bytes())

    def _write_current(self, records: Any, registrations: Any = ()) -> None:
        ordered = tuple(sorted(records, key=lambda item: item.provider_id))
        ordered_registrations = tuple(sorted(registrations, key=lambda item: item.provider_id))
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "providers": {
                record.provider_id: record.enabled
                for record in ordered
                if record.enabled is not None
            },
            "configuration": {
                record.provider_id: {
                    "access_confirmed": record.configuration.access_confirmed,
                    "api_base_url": record.configuration.api_base_url,
                }
                for record in ordered
                if record.configuration != ProviderConfiguration()
            },
            "manual_registrations": {
                registration.provider_id: registration.persisted_payload()
                for registration in ordered_registrations
            },
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)


def _read_json_object(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("provider settings payload must be an object")
    return payload


def _schema_version(payload: Mapping[str, object]) -> int:
    value = payload.get("schema_version")
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("schema_version must be an integer")
    return value


def _decode_current(
    payload: Mapping[str, object],
) -> tuple[tuple[ProviderSettingsRecord, ...], tuple[ManualProviderRegistration, ...]]:
    records = _decode_provider_records(payload)
    raw_registrations = payload.get("manual_registrations", {})
    if not isinstance(raw_registrations, dict):
        raise TypeError("manual_registrations must be an object")
    registrations: list[ManualProviderRegistration] = []
    seen_ids: set[str] = set()
    for raw_id, raw_value in sorted(
        raw_registrations.items(), key=lambda item: str(item[0]).casefold()
    ):
        provider_id = str(raw_id)
        if provider_id in seen_ids:
            raise ValueError("manual provider ids must be unique")
        seen_ids.add(provider_id)
        if not isinstance(raw_value, dict):
            raise TypeError("manual registration must be an object")
        unknown = set(raw_value) - {
            "display_name",
            "homepage_url",
            "endpoint_url",
            "lifecycle_state",
            "created_at",
            "updated_at",
        }
        if unknown:
            raise ValueError("manual registration has unsupported fields")
        display_name = raw_value.get("display_name")
        homepage_url = raw_value.get("homepage_url")
        endpoint_url = raw_value.get("endpoint_url", "")
        lifecycle = raw_value.get("lifecycle_state")
        created_at = raw_value.get("created_at")
        updated_at = raw_value.get("updated_at")
        if not all(
            isinstance(value, str)
            for value in (
                display_name,
                homepage_url,
                endpoint_url,
                lifecycle,
                created_at,
                updated_at,
            )
        ):
            raise TypeError("manual registration fields must be strings")
        registrations.append(
            ManualProviderRegistration(
                provider_id=provider_id,
                display_name=display_name,
                homepage_url=homepage_url,
                endpoint_url=endpoint_url,
                lifecycle_state=ManualProviderLifecycle(lifecycle),
                created_at=_parse_aware_datetime(created_at),
                updated_at=_parse_aware_datetime(updated_at),
            )
        )
    result = tuple(registrations)
    validate_manual_registration_uniqueness(result)
    _validate_manual_against_builtin_catalog(result)
    return records, result


def _decode_v2(payload: Mapping[str, object]) -> tuple[ProviderSettingsRecord, ...]:
    return _decode_provider_records(payload)


def _decode_provider_records(payload: Mapping[str, object]) -> tuple[ProviderSettingsRecord, ...]:
    raw_updated_at = payload.get("updated_at")
    if not isinstance(raw_updated_at, str) or not raw_updated_at.strip():
        raise TypeError("updated_at must be an aware timestamp")
    try:
        updated_at = datetime.fromisoformat(raw_updated_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("updated_at must be ISO 8601") from exc
    if updated_at.utcoffset() is None:
        raise ValueError("updated_at must be timezone-aware")
    raw_enabled = payload.get("providers")
    raw_configuration = payload.get("configuration", {})
    if not isinstance(raw_enabled, dict) or not isinstance(raw_configuration, dict):
        raise TypeError("providers and configuration must be objects")
    warnings: list[str] = []
    enabled: dict[str, bool] = {}
    for provider_id, value in _canonical_items(raw_enabled, warnings):
        if not isinstance(value, bool):
            raise TypeError("provider enablement must be boolean")
        enabled[provider_id] = value
    configurations: dict[str, ProviderConfiguration] = {}
    for provider_id, value in _canonical_items(raw_configuration, warnings):
        if not isinstance(value, dict):
            raise TypeError("provider configuration must be an object")
        unknown = set(value) - {"access_confirmed", "api_base_url"}
        if unknown:
            raise ValueError("provider configuration has unsupported fields")
        access_confirmed = value.get("access_confirmed", False)
        api_base_url = value.get("api_base_url", "")
        if not isinstance(access_confirmed, bool) or not isinstance(api_base_url, str):
            raise TypeError("provider configuration field has invalid type")
        configurations[provider_id] = ProviderConfiguration(
            access_confirmed=access_confirmed,
            api_base_url=api_base_url,
        )
    ids = set(enabled) | set(configurations)
    return tuple(
        ProviderSettingsRecord(
            provider_id=provider_id,
            enabled=enabled.get(provider_id),
            configuration=configurations.get(provider_id, ProviderConfiguration()),
        )
        for provider_id in sorted(ids)
    )


def _parse_aware_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("manual registration timestamp must be ISO 8601") from None
    if parsed.utcoffset() is None:
        raise ValueError("manual registration timestamp must be timezone-aware")
    return parsed


def _validate_manual_against_builtin_catalog(
    registrations: tuple[ManualProviderRegistration, ...],
) -> None:
    definitions = canonical_provider_definitions()
    builtin_ids = {item.id.casefold() for item in definitions}
    aliases = set(provider_aliases())
    builtin_name_keys = {manual_display_name_key(item.display_name) for item in definitions}
    for registration in registrations:
        if registration.provider_id in builtin_ids or registration.provider_id in aliases:
            raise ManualProviderConflictError(ManualProviderErrorCategory.IDENTITY_COLLISION)
        if registration.display_name_key in builtin_name_keys:
            raise ManualProviderConflictError(ManualProviderErrorCategory.DUPLICATE_NAME)


def _decode_v1_general(
    payload: Mapping[str, object],
    warnings: list[str],
) -> dict[str, bool]:
    if _schema_version(payload) != 1:
        raise ValueError("general provider settings schema must be v1")
    raw_providers = payload.get("providers")
    if not isinstance(raw_providers, dict):
        raise TypeError("general providers must be an object")
    result: dict[str, bool] = {}
    for provider_id, enabled in _canonical_items(raw_providers, warnings):
        if not isinstance(enabled, bool):
            raise TypeError("general provider enablement must be boolean")
        result[provider_id] = enabled
    return result


def _canonical_items(
    values: Mapping[object, object],
    warnings: list[str],
):
    aliases = provider_aliases()
    ordered = sorted(
        values.items(),
        key=lambda item: (
            str(item[0]).strip().casefold() in aliases,
            str(item[0]).strip().casefold(),
        ),
    )
    seen: set[str] = set()
    for raw_id, value in ordered:
        normalized = str(raw_id).strip().casefold()
        if not normalized:
            raise ValueError("provider id must not be empty")
        canonical = _canonical_or_normalized(normalized)
        if normalized in aliases:
            warnings.append(f"Provider alias {normalized} resolved to {canonical}.")
        if canonical in seen:
            warnings.append(f"Duplicate provider setting for {canonical} ignored.")
            continue
        seen.add(canonical)
        yield canonical, value


def _canonical_or_normalized(provider_id: str) -> str:
    normalized = str(provider_id).strip().casefold()
    if not normalized:
        raise ValueError("provider_id must not be empty")
    try:
        return canonical_provider_id(normalized)
    except KeyError:
        return normalized


def _normalize_api_base_url(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("api_base_url must be a string")
    raw = value.strip()
    if not raw:
        return ""
    try:
        parsed = urlsplit(raw)
        port = f":{parsed.port}" if parsed.port else ""
    except ValueError as exc:
        raise ValueError("api_base_url must be a valid HTTP(S) endpoint") from exc
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("api_base_url must be a valid HTTP(S) endpoint")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("api_base_url must be a safe HTTP(S) endpoint")
    hostname = parsed.hostname.casefold()
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme.casefold(), hostname + port, path, "", ""))


def _optional_environment_bool(
    environment: Mapping[str, str],
    key: str,
) -> bool | None:
    if key not in environment:
        return None
    normalized = str(environment.get(key, "")).strip().casefold()
    if normalized in {"1", "true", "yes", "on", "да"}:
        return True
    if normalized in {"0", "false", "no", "off", "нет", ""}:
        return False
    return None


__all__ = [
    "ProviderConfiguration",
    "ProviderEnablement",
    "ProviderEnablementRepository",
    "ProviderSettingOrigin",
    "ProviderSettingsLoadResult",
    "ProviderSettingsLoadStatus",
    "ProviderSettingsMutationError",
    "ProviderSettingsRecord",
    "ProviderSettingsSnapshot",
    "create_provider_settings_snapshot",
]
