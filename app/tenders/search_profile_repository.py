"""Atomic JSON repository for saved tender-search profiles."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
from threading import RLock
from typing import Iterable

from app.tenders.search_profiles import (
    TenderSearchProfile,
    create_builtin_search_profiles,
)


class SearchProfileNotFoundError(KeyError):
    """Raised when a saved search profile does not exist."""


class BuiltinSearchProfileError(ValueError):
    """Raised when a protected built-in profile is deleted."""


class TenderSearchProfileRepository:
    """Persist built-in and user-created profiles in one JSON catalog."""

    SCHEMA_VERSION = 1

    def __init__(
        self,
        path: str | Path,
        *,
        builtins: Iterable[TenderSearchProfile] | None = None,
    ) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._builtins = tuple(
            builtins
            if builtins is not None
            else create_builtin_search_profiles()
        )
        self._validate_builtin_catalog()

    def initialize(self) -> tuple[TenderSearchProfile, ...]:
        with self._lock:
            profiles, changed = self._load_and_merge_unlocked()
            if changed or not self.path.exists():
                self._write_unlocked(profiles)
            return tuple(profiles)

    def list_profiles(
        self,
        *,
        include_disabled: bool = True,
    ) -> tuple[TenderSearchProfile, ...]:
        with self._lock:
            profiles, changed = self._load_and_merge_unlocked()
            if changed or not self.path.exists():
                self._write_unlocked(profiles)

        if include_disabled:
            return tuple(profiles)
        return tuple(profile for profile in profiles if profile.enabled)

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
        with self._lock:
            profiles, _ = self._load_and_merge_unlocked()
            index = next(
                (
                    position
                    for position, item in enumerate(profiles)
                    if item.id == profile.id
                ),
                None,
            )

            if index is not None and not replace_existing:
                raise ValueError(
                    f"Search profile already exists: {profile.id}"
                )

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
                if current.is_builtin and not profile.is_builtin:
                    raise BuiltinSearchProfileError(
                        "A built-in profile cannot be replaced "
                        "with a custom profile"
                    )
                saved = replace(
                    profile,
                    created_at=(
                        current.created_at
                        or profile.created_at
                        or timestamp
                    ),
                    updated_at=timestamp,
                    is_builtin=current.is_builtin,
                )
                profiles[index] = saved

            profiles = self._sort_profiles(profiles)
            self._write_unlocked(profiles)
            return saved

    def update(
        self,
        profile_id: str,
        **changes,
    ) -> TenderSearchProfile:
        forbidden = {
            "id",
            "is_builtin",
            "created_at",
            "updated_at",
        }
        invalid = forbidden.intersection(changes)
        if invalid:
            raise ValueError(
                "Protected profile fields cannot be updated: "
                + ", ".join(sorted(invalid))
            )

        current = self.get(profile_id)
        updated = replace(current, **changes)
        return self.save(updated)

    def set_enabled(
        self,
        profile_id: str,
        enabled: bool,
    ) -> TenderSearchProfile:
        return self.update(profile_id, enabled=bool(enabled))

    def delete(self, profile_id: str) -> TenderSearchProfile:
        normalized = profile_id.strip().casefold()
        with self._lock:
            profiles, _ = self._load_and_merge_unlocked()
            for index, profile in enumerate(profiles):
                if profile.id != normalized:
                    continue
                if profile.is_builtin:
                    raise BuiltinSearchProfileError(
                        "Built-in search profiles cannot be deleted"
                    )
                removed = profiles.pop(index)
                self._write_unlocked(profiles)
                return removed

        raise SearchProfileNotFoundError(normalized)

    def restore_builtin_profiles(
        self,
    ) -> tuple[TenderSearchProfile, ...]:
        with self._lock:
            profiles, _ = self._load_and_merge_unlocked()
            custom = [
                profile
                for profile in profiles
                if not profile.is_builtin
            ]
            restored = self._sort_profiles(
                [*self._builtins, *custom]
            )
            self._write_unlocked(restored)
            return tuple(restored)

    def _load_and_merge_unlocked(
        self,
    ) -> tuple[list[TenderSearchProfile], bool]:
        stored, recovered = self._read_unlocked()
        merged: dict[str, TenderSearchProfile] = {
            profile.id: profile for profile in stored
        }
        changed = recovered

        for builtin in self._builtins:
            existing = merged.get(builtin.id)
            if existing is None:
                merged[builtin.id] = builtin
                changed = True
                continue
            if not existing.is_builtin:
                merged[builtin.id] = builtin
                changed = True

        profiles = self._sort_profiles(list(merged.values()))
        if len(profiles) != len(stored):
            changed = True
        return profiles, changed

    def _read_unlocked(
        self,
    ) -> tuple[list[TenderSearchProfile], bool]:
        if not self.path.exists():
            return [], True

        try:
            payload = json.loads(
                self.path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            self._quarantine_corrupt_file_unlocked()
            return [], True

        if not isinstance(payload, dict):
            self._quarantine_corrupt_file_unlocked()
            return [], True

        raw_profiles = payload.get("profiles", [])
        if not isinstance(raw_profiles, list):
            self._quarantine_corrupt_file_unlocked()
            return [], True

        result: list[TenderSearchProfile] = []
        seen: set[str] = set()
        recovered = False
        for item in raw_profiles:
            if not isinstance(item, dict):
                recovered = True
                continue
            try:
                profile = TenderSearchProfile.from_dict(item)
            except (TypeError, ValueError):
                recovered = True
                continue
            if profile.id in seen:
                recovered = True
                continue
            seen.add(profile.id)
            result.append(profile)

        return result, recovered

    def _write_unlocked(
        self,
        profiles: Iterable[TenderSearchProfile],
    ) -> None:
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "updated_at": _now_iso(),
            "profiles": [
                profile.to_dict() for profile in profiles
            ],
        }
        temporary = self.path.with_suffix(
            self.path.suffix + ".tmp"
        )
        try:
            temporary.write_text(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def _quarantine_corrupt_file_unlocked(self) -> None:
        if not self.path.exists():
            return
        suffix = datetime.now(timezone.utc).strftime(
            "%Y%m%dT%H%M%SZ"
        )
        destination = self.path.with_name(
            f"{self.path.stem}.corrupt-{suffix}"
            f"{self.path.suffix}"
        )
        try:
            self.path.replace(destination)
        except OSError:
            pass

    def _validate_builtin_catalog(self) -> None:
        ids: set[str] = set()
        for profile in self._builtins:
            if not profile.is_builtin:
                raise ValueError(
                    f"Built-in profile is not marked built-in: "
                    f"{profile.id}"
                )
            if profile.id in ids:
                raise ValueError(
                    f"Duplicate built-in profile id: {profile.id}"
                )
            ids.add(profile.id)

    def _sort_profiles(
        self,
        profiles: list[TenderSearchProfile],
    ) -> list[TenderSearchProfile]:
        builtin_order = {
            profile.id: index
            for index, profile in enumerate(self._builtins)
        }
        return sorted(
            profiles,
            key=lambda profile: (
                0 if profile.is_builtin else 1,
                builtin_order.get(profile.id, 10_000),
                profile.name.casefold(),
                profile.id,
            ),
        )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )


__all__ = [
    "BuiltinSearchProfileError",
    "SearchProfileNotFoundError",
    "TenderSearchProfileRepository",
]
