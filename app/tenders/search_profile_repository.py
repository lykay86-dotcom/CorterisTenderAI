"""Atomic versioned JSON repository for saved tender-search profiles."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum
import json
from pathlib import Path
from threading import RLock
from typing import Any

from app.tenders.search_profiles import (
    SearchProfileRuntimeQueryPolicy,
    TenderSearchProfile,
    create_builtin_search_profiles,
)


class SearchProfileNotFoundError(KeyError):
    """Raised when a saved search profile does not exist."""


class BuiltinSearchProfileError(ValueError):
    """Raised when a protected built-in profile is deleted or replaced."""


class SearchProfileCatalogMutationError(ValueError):
    """Bounded failure raised when catalog mutation cannot be completed safely."""

    def __init__(self, public_message: str) -> None:
        normalized = " ".join(str(public_message).split())[:300]
        super().__init__(normalized)
        self.public_message = normalized


class SearchProfileCatalogLoadStatus(StrEnum):
    MISSING = "missing"
    CURRENT = "current"
    MIGRATED_V1 = "migrated_v1"
    CORRUPT = "corrupt"
    UNSUPPORTED_FUTURE = "unsupported_future"


@dataclass(frozen=True, slots=True)
class SearchProfileCatalogLoadResult:
    profiles: tuple[TenderSearchProfile, ...]
    status: SearchProfileCatalogLoadStatus
    source_schema_version: int | None
    warnings: tuple[str, ...] = ()
    quarantine_path: Path | None = None


_PROFILE_FIELDS = frozenset(
    {
        "id",
        "name",
        "description",
        "keywords",
        "excluded_keywords",
        "directions",
        "require_all_directions",
        "regions",
        "laws",
        "min_price",
        "max_price",
        "price_currency",
        "minimum_score",
        "only_open",
        "lookback_days",
        "page_size",
        "provider_ids",
        "include_disabled_providers",
        "enabled",
        "is_builtin",
        "created_at",
        "updated_at",
        "runtime_query_policy",
    }
)
_V2_REQUIRED_PROFILE_FIELDS = _PROFILE_FIELDS
_ARRAY_FIELDS = frozenset(
    {
        "keywords",
        "excluded_keywords",
        "directions",
        "regions",
        "laws",
        "provider_ids",
    }
)
_BOOLEAN_FIELDS = frozenset(
    {
        "require_all_directions",
        "only_open",
        "include_disabled_providers",
        "enabled",
        "is_builtin",
    }
)
_INTEGER_FIELDS = frozenset({"minimum_score", "page_size"})
_STRING_FIELDS = frozenset(
    {
        "id",
        "name",
        "description",
        "price_currency",
        "created_at",
        "updated_at",
        "runtime_query_policy",
    }
)


class TenderSearchProfileRepository:
    """Persist built-in and user-created profiles in one versioned catalog."""

    SCHEMA_VERSION = 2

    def __init__(
        self,
        path: str | Path,
        *,
        builtins: Iterable[TenderSearchProfile] | None = None,
    ) -> None:
        self.path = Path(path).expanduser()
        self._lock = RLock()
        self._builtins = tuple(
            builtins if builtins is not None else create_builtin_search_profiles()
        )
        self._validate_builtin_catalog()
        self._builtin_ids = frozenset(profile.id for profile in self._builtins)

    def load_result(self) -> SearchProfileCatalogLoadResult:
        """Read one snapshot without rewriting valid v1/current/future bytes."""

        with self._lock:
            result, _source = self._read_snapshot_unlocked(quarantine_corrupt=True)
            return result

    def initialize(self) -> tuple[TenderSearchProfile, ...]:
        """Create a current catalog only when the file is genuinely missing."""

        with self._lock:
            result, source = self._read_snapshot_unlocked(quarantine_corrupt=True)
            if result.status is SearchProfileCatalogLoadStatus.MISSING:
                self._write_unlocked(result.profiles)
            del source
            return result.profiles

    def list_profiles(
        self,
        *,
        include_disabled: bool = True,
    ) -> tuple[TenderSearchProfile, ...]:
        result = self.load_result()
        if include_disabled:
            return result.profiles
        return tuple(profile for profile in result.profiles if profile.enabled)

    def get(self, profile_id: str) -> TenderSearchProfile:
        normalized = profile_id.strip().casefold()
        for profile in self.list_profiles():
            if profile.id == normalized:
                return profile
        raise SearchProfileNotFoundError(normalized)

    def save(
        self,
        profile: TenderSearchProfile,
        *,
        replace_existing: bool = True,
    ) -> TenderSearchProfile:
        if not isinstance(profile, TenderSearchProfile):
            raise TypeError("profile must be a TenderSearchProfile")
        with self._lock:
            result, source = self._mutable_snapshot_unlocked()
            profiles = list(result.profiles)
            index = next(
                (position for position, item in enumerate(profiles) if item.id == profile.id),
                None,
            )

            if profile.id in self._builtin_ids and not profile.is_builtin:
                raise BuiltinSearchProfileError(
                    "A custom profile cannot replace a built-in profile"
                )
            profile = replace(
                profile,
                is_builtin=profile.id in self._builtin_ids,
            )
            if index is not None and not replace_existing:
                raise ValueError(f"Search profile already exists: {profile.id}")

            timestamp = _now_iso()
            if index is None:
                saved = replace(
                    profile,
                    created_at=profile.created_at or timestamp,
                    updated_at=timestamp,
                )
                profiles.append(saved)
            else:
                current = profiles[index]
                if current.id in self._builtin_ids and profile.id not in self._builtin_ids:
                    raise BuiltinSearchProfileError(
                        "A built-in profile cannot be replaced with a custom profile"
                    )
                saved = replace(
                    profile,
                    created_at=current.created_at or profile.created_at or timestamp,
                    updated_at=timestamp,
                    is_builtin=current.id in self._builtin_ids,
                )
                profiles[index] = saved

            self._commit_unlocked(self._sort_profiles(profiles), result, source)
            return saved

    def update(self, profile_id: str, **changes: Any) -> TenderSearchProfile:
        forbidden = {"id", "is_builtin", "created_at", "updated_at"}
        invalid = forbidden.intersection(changes)
        if invalid:
            raise ValueError(
                "Protected profile fields cannot be updated: " + ", ".join(sorted(invalid))
            )
        with self._lock:
            result, source = self._mutable_snapshot_unlocked()
            normalized = profile_id.strip().casefold()
            profiles = list(result.profiles)
            index = next(
                (position for position, item in enumerate(profiles) if item.id == normalized),
                None,
            )
            if index is None:
                raise SearchProfileNotFoundError(normalized)
            current = profiles[index]
            updated = replace(current, **changes, updated_at=_now_iso())
            profiles[index] = updated
            self._commit_unlocked(self._sort_profiles(profiles), result, source)
            return updated

    def set_enabled(self, profile_id: str, enabled: bool) -> TenderSearchProfile:
        return self.update(profile_id, enabled=bool(enabled))

    def delete(self, profile_id: str) -> TenderSearchProfile:
        normalized = profile_id.strip().casefold()
        with self._lock:
            result, source = self._mutable_snapshot_unlocked()
            profiles = list(result.profiles)
            for index, profile in enumerate(profiles):
                if profile.id != normalized:
                    continue
                if profile.id in self._builtin_ids:
                    raise BuiltinSearchProfileError("Built-in search profiles cannot be deleted")
                removed = profiles.pop(index)
                self._commit_unlocked(self._sort_profiles(profiles), result, source)
                return removed
        raise SearchProfileNotFoundError(normalized)

    def restore_builtin_profiles(self) -> tuple[TenderSearchProfile, ...]:
        with self._lock:
            result, source = self._mutable_snapshot_unlocked()
            custom = [profile for profile in result.profiles if profile.id not in self._builtin_ids]
            restored = self._sort_profiles([*self._builtins, *custom])
            self._commit_unlocked(restored, result, source)
            return tuple(restored)

    def _mutable_snapshot_unlocked(
        self,
    ) -> tuple[SearchProfileCatalogLoadResult, bytes | None]:
        result, source = self._read_snapshot_unlocked(quarantine_corrupt=True)
        if result.status in {
            SearchProfileCatalogLoadStatus.CORRUPT,
            SearchProfileCatalogLoadStatus.UNSUPPORTED_FUTURE,
        }:
            raise SearchProfileCatalogMutationError(
                "Каталог профилей повреждён или создан более новой версией. "
                "Восстановите поддерживаемый файл перед изменением."
            )
        return result, source

    def _read_snapshot_unlocked(
        self,
        *,
        quarantine_corrupt: bool,
    ) -> tuple[SearchProfileCatalogLoadResult, bytes | None]:
        if not self.path.is_file():
            return (
                SearchProfileCatalogLoadResult(
                    profiles=self._sort_tuple(self._builtins),
                    status=SearchProfileCatalogLoadStatus.MISSING,
                    source_schema_version=None,
                ),
                None,
            )

        source_schema_version: int | None = None
        source: bytes | None = None
        try:
            source = self.path.read_bytes()
            payload = json.loads(source.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("catalog must be an object")
            raw_version = payload.get("schema_version")
            if isinstance(raw_version, bool) or not isinstance(raw_version, int):
                raise ValueError("schema_version must be an integer")
            source_schema_version = raw_version
            if raw_version > self.SCHEMA_VERSION:
                return (
                    SearchProfileCatalogLoadResult(
                        profiles=(),
                        status=SearchProfileCatalogLoadStatus.UNSUPPORTED_FUTURE,
                        source_schema_version=raw_version,
                        warnings=("Версия каталога новее поддерживаемой.",),
                    ),
                    source,
                )
            if raw_version not in {1, self.SCHEMA_VERSION}:
                raise ValueError("unsupported schema version")
            warnings: list[str] = []
            profiles = self._decode_profiles_unlocked(
                payload,
                schema_version=raw_version,
                warnings=warnings,
            )
            status = (
                SearchProfileCatalogLoadStatus.MIGRATED_V1
                if raw_version == 1
                else SearchProfileCatalogLoadStatus.CURRENT
            )
            return (
                SearchProfileCatalogLoadResult(
                    profiles=tuple(profiles),
                    status=status,
                    source_schema_version=raw_version,
                    warnings=tuple(warnings),
                ),
                source,
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            quarantine_path = None
            if quarantine_corrupt and source is not None:
                quarantine_path = self._quarantine_copy_unlocked(source)
            return (
                SearchProfileCatalogLoadResult(
                    profiles=(),
                    status=SearchProfileCatalogLoadStatus.CORRUPT,
                    source_schema_version=source_schema_version,
                    warnings=("Каталог профилей повреждён или содержит неверные данные.",),
                    quarantine_path=quarantine_path,
                ),
                source,
            )

    def _decode_profiles_unlocked(
        self,
        payload: Mapping[str, object],
        *,
        schema_version: int,
        warnings: list[str],
    ) -> list[TenderSearchProfile]:
        if schema_version == self.SCHEMA_VERSION:
            _aware_timestamp(
                payload.get("updated_at"),
                field_name="catalog.updated_at",
            )
        else:
            _legacy_timestamp(
                payload.get("updated_at", ""),
                field_name="catalog.updated_at",
                warnings=warnings,
            )
        raw_profiles = payload.get("profiles")
        if not isinstance(raw_profiles, list):
            raise ValueError("profiles must be an array")

        decoded: list[TenderSearchProfile] = []
        seen: set[str] = set()
        for raw_profile in raw_profiles:
            if not isinstance(raw_profile, dict):
                raise ValueError("profile must be an object")
            raw_id = raw_profile.get("id")
            if not isinstance(raw_id, str) or not raw_id.strip():
                raise ValueError("profile id must be a string")
            identity = raw_id.strip().casefold()
            if identity in seen:
                raise ValueError("duplicate profile id")
            seen.add(identity)
            profile = self._decode_profile_unlocked(
                raw_profile,
                schema_version=schema_version,
                warnings=warnings,
            )
            decoded.append(
                replace(
                    profile,
                    is_builtin=profile.id in self._builtin_ids,
                )
            )

        by_id = {profile.id: profile for profile in decoded}
        for builtin in self._builtins:
            by_id.setdefault(builtin.id, builtin)
        return self._sort_profiles(list(by_id.values()))

    def _decode_profile_unlocked(
        self,
        payload: Mapping[str, object],
        *,
        schema_version: int,
        warnings: list[str],
    ) -> TenderSearchProfile:
        if schema_version == self.SCHEMA_VERSION:
            missing = _V2_REQUIRED_PROFILE_FIELDS.difference(payload)
            if missing:
                raise ValueError("current profile is missing required fields")

        values = {key: value for key, value in payload.items() if key in _PROFILE_FIELDS}
        for field_name in _ARRAY_FIELDS:
            value = values.get(field_name)
            if value is None and schema_version == 1:
                continue
            if not isinstance(value, list) or any(
                not isinstance(item, str) or not item.strip() for item in value
            ):
                raise ValueError(f"{field_name} must be a string array")
        for field_name in _BOOLEAN_FIELDS:
            value = values.get(field_name)
            if value is None and schema_version == 1:
                continue
            if not isinstance(value, bool):
                raise ValueError(f"{field_name} must be a boolean")
        for field_name in _INTEGER_FIELDS:
            value = values.get(field_name)
            if value is None and schema_version == 1:
                continue
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{field_name} must be an integer")
        lookback = values.get("lookback_days", 30)
        if lookback is not None and (isinstance(lookback, bool) or not isinstance(lookback, int)):
            raise ValueError("lookback_days must be an integer or null")
        for field_name in _STRING_FIELDS:
            value = values.get(field_name)
            if value is None and schema_version == 1:
                continue
            if not isinstance(value, str):
                raise ValueError(f"{field_name} must be a string")

        for field_name in ("min_price", "max_price"):
            value = values.get(field_name)
            if schema_version == self.SCHEMA_VERSION:
                if value is not None and not isinstance(value, str):
                    raise ValueError(f"{field_name} must be a decimal string or null")
            elif value is not None and not isinstance(value, (str, int, float)):
                raise ValueError(f"{field_name} must be numeric, string or null")
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                _append_warning(
                    warnings,
                    "Legacy numeric money was converted with Decimal(str(value)).",
                )

        if schema_version == 1:
            if "price_currency" not in values:
                values["price_currency"] = "RUB"
                _append_warning(warnings, "Legacy missing currency defaulted to RUB.")
            values["runtime_query_policy"] = (
                SearchProfileRuntimeQueryPolicy.REPLACE_KEYWORDS_IF_PRESENT.value
            )
            for field_name in ("created_at", "updated_at"):
                value = values.get(field_name, "")
                values[field_name] = _legacy_timestamp(
                    value,
                    field_name=field_name,
                    warnings=warnings,
                )
        else:
            values["created_at"] = _aware_optional_timestamp(
                values.get("created_at"),
                field_name="created_at",
            )
            values["updated_at"] = _aware_optional_timestamp(
                values.get("updated_at"),
                field_name="updated_at",
            )

        return TenderSearchProfile.from_dict(values)

    def _commit_unlocked(
        self,
        profiles: Iterable[TenderSearchProfile],
        source_result: SearchProfileCatalogLoadResult,
        source: bytes | None,
    ) -> None:
        if source_result.status is SearchProfileCatalogLoadStatus.MIGRATED_V1:
            if source is None:
                raise SearchProfileCatalogMutationError(
                    "Не удалось сохранить резервную копию schema v1."
                )
            self._create_v1_backup_unlocked(source)
        self._write_unlocked(profiles)

    def _write_unlocked(self, profiles: Iterable[TenderSearchProfile]) -> None:
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "updated_at": _now_iso(),
            "profiles": [profile.to_dict() for profile in profiles],
        }
        try:
            rendered = json.dumps(payload, ensure_ascii=False, indent=2)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            try:
                temporary.write_text(rendered, encoding="utf-8")
                temporary.replace(self.path)
            finally:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
        except (OSError, TypeError, ValueError) as exc:
            raise SearchProfileCatalogMutationError(
                "Не удалось безопасно сохранить каталог профилей. Исходный файл не изменён."
            ) from exc

    def _create_v1_backup_unlocked(self, source: bytes) -> Path:
        destination = self._unique_sibling("v1-backup")
        try:
            with destination.open("xb") as stream:
                stream.write(source)
        except OSError as exc:
            raise SearchProfileCatalogMutationError(
                "Не удалось создать резервную копию schema v1."
            ) from exc
        return destination

    def _quarantine_copy_unlocked(self, source: bytes) -> Path | None:
        for existing in self.path.parent.glob(f"{self.path.stem}.corrupt-*{self.path.suffix}"):
            try:
                if existing.read_bytes() == source:
                    return existing
            except OSError:
                continue
        destination = self._unique_sibling("corrupt")
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as stream:
                stream.write(source)
        except OSError:
            return None
        return destination

    def _unique_sibling(self, label: str) -> Path:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        return self.path.with_name(f"{self.path.stem}.{label}-{stamp}{self.path.suffix}")

    def _validate_builtin_catalog(self) -> None:
        ids: set[str] = set()
        for profile in self._builtins:
            if not profile.is_builtin:
                raise ValueError(f"Built-in profile is not marked built-in: {profile.id}")
            if profile.id in ids:
                raise ValueError(f"Duplicate built-in profile id: {profile.id}")
            ids.add(profile.id)

    def _sort_tuple(
        self,
        profiles: Iterable[TenderSearchProfile],
    ) -> tuple[TenderSearchProfile, ...]:
        return tuple(self._sort_profiles(list(profiles)))

    def _sort_profiles(
        self,
        profiles: list[TenderSearchProfile],
    ) -> list[TenderSearchProfile]:
        builtin_order = {profile.id: index for index, profile in enumerate(self._builtins)}
        return sorted(
            profiles,
            key=lambda profile: (
                0 if profile.id in self._builtin_ids else 1,
                builtin_order.get(profile.id, 10_000),
                profile.name.casefold(),
                profile.id,
            ),
        )


def _append_warning(warnings: list[str], message: str) -> None:
    bounded = " ".join(message.split())[:300]
    if bounded not in warnings:
        warnings.append(bounded)


def _aware_timestamp(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be an aware timestamp")
    try:
        moment = datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO timestamp") from exc
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError(f"{field_name} must include timezone information")
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def _aware_optional_timestamp(value: object, *, field_name: str) -> str:
    if value in (None, ""):
        return ""
    return _aware_timestamp(value, field_name=field_name)


def _legacy_timestamp(
    value: object,
    *,
    field_name: str,
    warnings: list[str],
) -> str:
    if value in (None, ""):
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    try:
        moment = datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO timestamp") from exc
    if moment.tzinfo is None or moment.utcoffset() is None:
        _append_warning(
            warnings,
            "Legacy timestamp without timezone became explicitly unknown.",
        )
        return ""
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


__all__ = [
    "BuiltinSearchProfileError",
    "SearchProfileCatalogLoadResult",
    "SearchProfileCatalogLoadStatus",
    "SearchProfileCatalogMutationError",
    "SearchProfileNotFoundError",
    "TenderSearchProfileRepository",
]
