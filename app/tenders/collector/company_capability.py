"""Editable, explicitly confirmed company capability profile."""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from hashlib import sha256
import hmac
import json
from pathlib import Path
import re
from threading import RLock
from typing import Any, Iterable, Mapping

from app.tenders.models import normalize_currency_code


_CONFIRMATION_VERSION = 1
_CONFIRMATION_SOURCES = frozenset({"user", "migrated_v1"})
_CONFIRMATION_METADATA_FIELDS = frozenset(
    {
        "confirmed_at",
        "confirmed_by",
        "evidence_note",
        "confirmation_version",
        "confirmation_fingerprint",
        "confirmation_source",
        "updated_at",
    }
)


@dataclass(frozen=True, slots=True)
class CompanyCapabilityProfile:
    """Normalized company facts with content-bound confirmation metadata."""

    company_name: str = ""
    business_directions: tuple[str, ...] = ()
    self_install_regions: tuple[str, ...] = ()
    partner_regions: tuple[str, ...] = ()
    licenses: tuple[str, ...] = ()
    license_work_types: tuple[str, ...] = ()
    sro_memberships: tuple[str, ...] = ()
    employee_qualifications: tuple[str, ...] = ()
    installation_crew_count: int | None = None
    completed_contracts: tuple[str, ...] = ()
    confirmed_experience: tuple[str, ...] = ()
    max_project_amount: Decimal | None = None
    working_capital: Decimal | None = None
    max_bid_security: Decimal | None = None
    max_contract_security: Decimal | None = None
    bank_guarantee_limit: Decimal | None = None
    base_currency: str = "RUB"
    equipment: tuple[str, ...] = ()
    brands: tuple[str, ...] = ()
    suppliers: tuple[str, ...] = ()
    stock_items: tuple[str, ...] = ()
    minimum_margin_percent: Decimal | None = None
    acceptable_payment_days: int | None = None
    maximum_deferment_days: int | None = None
    self_performed_directions: tuple[str, ...] = ()
    subcontracted_directions: tuple[str, ...] = ()
    undesired_object_types: tuple[str, ...] = ()
    has_designers: bool | None = None
    regional_partners: tuple[str, ...] = ()
    evidence_note: str = ""
    confirmed_at: str = ""
    confirmed_by: str = ""
    confirmation_version: int = _CONFIRMATION_VERSION
    confirmation_fingerprint: str = ""
    confirmation_source: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        for name in _STRING_FIELDS:
            value = getattr(self, name)
            if not isinstance(value, str):
                raise ValueError(f"{name} must be a string")
        for name in _TUPLE_FIELDS:
            object.__setattr__(self, name, _string_tuple(getattr(self, name)))
        for name in _MONEY_FIELDS:
            object.__setattr__(self, name, _optional_decimal(getattr(self, name)))
        for name in _INTEGER_FIELDS:
            object.__setattr__(
                self,
                name,
                _optional_non_negative_int(getattr(self, name), field_name=name),
            )
        if self.has_designers is not None and not isinstance(self.has_designers, bool):
            raise ValueError("has_designers must be a boolean or null")
        if self.minimum_margin_percent is not None and self.minimum_margin_percent > 100:
            raise ValueError("minimum_margin_percent cannot exceed 100")
        object.__setattr__(
            self,
            "base_currency",
            normalize_currency_code(self.base_currency),
        )
        if isinstance(self.confirmation_version, bool) or not isinstance(
            self.confirmation_version, int
        ):
            raise ValueError("confirmation_version must be an integer")
        if self.confirmation_version < 1:
            raise ValueError("confirmation_version must be positive")
        fingerprint = self.confirmation_fingerprint.strip().lower()
        if fingerprint and not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
            raise ValueError("confirmation_fingerprint must be a SHA-256 hex digest")
        object.__setattr__(self, "confirmation_fingerprint", fingerprint)
        source = self.confirmation_source.strip().lower()
        if source and source not in _CONFIRMATION_SOURCES:
            raise ValueError("confirmation_source is not supported")
        object.__setattr__(self, "confirmation_source", source)
        for name in ("confirmed_at", "updated_at"):
            value = getattr(self, name)
            if value:
                object.__setattr__(self, name, _aware_iso(value, field_name=name))

    @property
    def content_fingerprint(self) -> str:
        """Return a deterministic SHA-256 digest of decision-relevant facts."""

        canonical: dict[str, object] = {}
        for item in fields(self):
            if item.name in _CONFIRMATION_METADATA_FIELDS:
                continue
            value = getattr(self, item.name)
            if isinstance(value, Decimal):
                canonical[item.name] = _canonical_decimal(value)
            elif isinstance(value, tuple):
                canonical[item.name] = sorted(
                    value,
                    key=lambda entry: (entry.casefold(), entry),
                )
            else:
                canonical[item.name] = value
        rendered = json.dumps(
            canonical,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return sha256(rendered).hexdigest()

    @property
    def is_confirmed(self) -> bool:
        return bool(
            self.confirmed_at
            and self.confirmed_by.strip()
            and self.confirmation_version == _CONFIRMATION_VERSION
            and self.confirmation_source in _CONFIRMATION_SOURCES
            and self.confirmation_fingerprint
            and hmac.compare_digest(
                self.confirmation_fingerprint,
                self.content_fingerprint,
            )
        )

    def confirm(
        self,
        *,
        confirmed_by: str,
        confirmed_at: datetime,
        evidence_note: str = "",
    ) -> CompanyCapabilityProfile:
        """Return a copy explicitly confirmed against its current facts."""

        if not isinstance(confirmed_by, str) or not confirmed_by.strip():
            raise ValueError("confirmed_by must not be empty")
        if not isinstance(confirmed_at, datetime):
            raise ValueError("confirmed_at must be a datetime")
        if confirmed_at.tzinfo is None or confirmed_at.utcoffset() is None:
            raise ValueError("confirmed_at timezone must be explicit")
        if not isinstance(evidence_note, str):
            raise ValueError("evidence_note must be a string")
        candidate = replace(
            self,
            confirmed_at=confirmed_at.astimezone(timezone.utc).isoformat(timespec="seconds"),
            confirmed_by=confirmed_by.strip(),
            evidence_note=evidence_note,
            confirmation_version=_CONFIRMATION_VERSION,
            confirmation_fingerprint="",
            confirmation_source="user",
        )
        return replace(
            candidate,
            confirmation_fingerprint=candidate.content_fingerprint,
        )

    @property
    def is_configured(self) -> bool:
        """Compatibility view delegated to the policy-level projection."""

        from app.tenders.business_profile import BusinessCapabilityProjection

        return BusinessCapabilityProjection.from_capability(self).is_configured

    @property
    def missing_sections(self) -> tuple[str, ...]:
        """Compatibility view delegated to the policy-level projection."""

        from app.tenders.business_profile import BusinessCapabilityProjection

        return BusinessCapabilityProjection.from_capability(self).missing_sections

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {}
        for item in fields(self):
            value = getattr(self, item.name)
            if isinstance(value, Decimal):
                payload[item.name] = str(value)
            elif isinstance(value, tuple):
                payload[item.name] = list(value)
            else:
                payload[item.name] = value
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> CompanyCapabilityProfile:
        """Build a profile from validated persisted field shapes."""

        if not isinstance(payload, Mapping):
            raise ValueError("profile must be an object")
        _validate_persisted_field_shapes(payload)
        known = {item.name for item in fields(cls)}
        values: dict[str, Any] = {key: value for key, value in payload.items() if key in known}
        return cls(**values)


class CompanyCapabilityLoadStatus(StrEnum):
    MISSING = "missing"
    CURRENT = "current"
    MIGRATED_V1 = "migrated_v1"
    CORRUPT = "corrupt"
    UNSUPPORTED_FUTURE = "unsupported_future"


@dataclass(frozen=True, slots=True)
class CompanyCapabilityLoadResult:
    profile: CompanyCapabilityProfile
    status: CompanyCapabilityLoadStatus
    source_schema_version: int | None
    warnings: tuple[str, ...] = ()


class CompanyCapabilityProfileRepository:
    """Single-file repository with explicit schema and fail-closed writes."""

    SCHEMA_VERSION = 2

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self._lock = RLock()

    def load_result(self) -> CompanyCapabilityLoadResult:
        with self._lock:
            if not self.path.is_file():
                return CompanyCapabilityLoadResult(
                    profile=CompanyCapabilityProfile(),
                    status=CompanyCapabilityLoadStatus.MISSING,
                    source_schema_version=None,
                )
            source_schema_version: int | None = None
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("payload must be an object")
                raw_version = payload.get("schema_version")
                if isinstance(raw_version, bool) or not isinstance(raw_version, int):
                    raise ValueError("schema_version must be an integer")
                source_schema_version = raw_version
                if raw_version > self.SCHEMA_VERSION:
                    return CompanyCapabilityLoadResult(
                        profile=CompanyCapabilityProfile(),
                        status=CompanyCapabilityLoadStatus.UNSUPPORTED_FUTURE,
                        source_schema_version=raw_version,
                        warnings=(f"Unsupported company capability schema version: {raw_version}",),
                    )
                if raw_version == 1:
                    return CompanyCapabilityLoadResult(
                        profile=migrate_company_capability_v1(payload),
                        status=CompanyCapabilityLoadStatus.MIGRATED_V1,
                        source_schema_version=raw_version,
                    )
                if raw_version != self.SCHEMA_VERSION:
                    raise ValueError(f"Unsupported schema version: {raw_version}")
                raw_profile = payload.get("profile")
                if not isinstance(raw_profile, dict):
                    raise ValueError("profile must be an object")
                missing = _V2_REQUIRED_FIELDS.difference(raw_profile)
                if missing:
                    raise ValueError(
                        "current profile is missing required fields: " + ", ".join(sorted(missing))
                    )
                profile = CompanyCapabilityProfile.from_dict(raw_profile)
                if not profile.is_confirmed:
                    raise ValueError("current profile confirmation is invalid or stale")
                return CompanyCapabilityLoadResult(
                    profile=profile,
                    status=CompanyCapabilityLoadStatus.CURRENT,
                    source_schema_version=raw_version,
                )
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                return CompanyCapabilityLoadResult(
                    profile=CompanyCapabilityProfile(),
                    status=CompanyCapabilityLoadStatus.CORRUPT,
                    source_schema_version=source_schema_version,
                    warnings=("Company capability profile is corrupt or unreadable.",),
                )

    def load(self) -> CompanyCapabilityProfile:
        """Compatibility API returning only the fail-closed profile."""

        return self.load_result().profile

    def save(self, profile: CompanyCapabilityProfile) -> None:
        if not isinstance(profile, CompanyCapabilityProfile):
            raise TypeError("profile must be a CompanyCapabilityProfile")
        if not profile.is_confirmed:
            raise ValueError("Профиль должен быть явно подтверждён пользователем")
        if not profile.company_name.strip():
            raise ValueError("Укажите название компании")
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        stored = replace(profile, updated_at=timestamp)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "profile": stored.to_dict(),
        }
        with self._lock:
            self._assert_safe_to_overwrite()
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

    def _assert_safe_to_overwrite(self) -> None:
        if not self.path.exists():
            return
        result = self.load_result()
        if result.status in {
            CompanyCapabilityLoadStatus.CORRUPT,
            CompanyCapabilityLoadStatus.UNSUPPORTED_FUTURE,
        }:
            raise ValueError(
                "Refusing to overwrite a corrupt or unsupported company capability file"
            )


def migrate_company_capability_v1(
    payload: Mapping[str, object],
) -> CompanyCapabilityProfile:
    """Purely migrate a valid v1 envelope to the current in-memory profile."""

    if not isinstance(payload, Mapping):
        raise ValueError("payload must be an object")
    raw_version = payload.get("schema_version")
    if isinstance(raw_version, bool) or not isinstance(raw_version, int):
        raise ValueError("schema_version must be an integer")
    raw_profile = payload.get("profile")
    if not isinstance(raw_profile, Mapping):
        raise ValueError("profile must be an object")
    if raw_version == CompanyCapabilityProfileRepository.SCHEMA_VERSION:
        missing = _V2_REQUIRED_FIELDS.difference(raw_profile)
        if missing:
            raise ValueError("current profile is missing required fields")
        current = CompanyCapabilityProfile.from_dict(raw_profile)
        if not current.is_confirmed:
            raise ValueError("current profile confirmation is invalid or stale")
        return current
    if raw_version != 1:
        raise ValueError(f"Cannot migrate schema version: {raw_version}")

    v1_payload = {key: value for key, value in raw_profile.items() if key in _V1_FIELDS}
    legacy = CompanyCapabilityProfile.from_dict(v1_payload)
    if not legacy.confirmed_by.strip() or not legacy.confirmed_at:
        raise ValueError("v1 confirmation metadata is incomplete")
    migrated = replace(
        legacy,
        base_currency="RUB",
        confirmation_version=_CONFIRMATION_VERSION,
        confirmation_fingerprint="",
        confirmation_source="migrated_v1",
    )
    return replace(
        migrated,
        confirmation_fingerprint=migrated.content_fingerprint,
    )


_TUPLE_FIELDS = {
    "business_directions",
    "self_install_regions",
    "partner_regions",
    "licenses",
    "license_work_types",
    "sro_memberships",
    "employee_qualifications",
    "completed_contracts",
    "confirmed_experience",
    "equipment",
    "brands",
    "suppliers",
    "stock_items",
    "self_performed_directions",
    "subcontracted_directions",
    "undesired_object_types",
    "regional_partners",
}
_MONEY_FIELDS = {
    "max_project_amount",
    "working_capital",
    "max_bid_security",
    "max_contract_security",
    "bank_guarantee_limit",
    "minimum_margin_percent",
}
_INTEGER_FIELDS = {
    "installation_crew_count",
    "acceptable_payment_days",
    "maximum_deferment_days",
}
_STRING_FIELDS = {
    "company_name",
    "base_currency",
    "evidence_note",
    "confirmed_at",
    "confirmed_by",
    "confirmation_fingerprint",
    "confirmation_source",
    "updated_at",
}
_V2_ONLY_FIELDS = {
    "base_currency",
    "confirmation_version",
    "confirmation_fingerprint",
    "confirmation_source",
}
_V2_REQUIRED_FIELDS = frozenset(_V2_ONLY_FIELDS)
_V1_FIELDS = frozenset(item.name for item in fields(CompanyCapabilityProfile)) - _V2_ONLY_FIELDS


def _validate_persisted_field_shapes(payload: Mapping[str, object]) -> None:
    for name in _STRING_FIELDS:
        if name in payload and not isinstance(payload[name], str):
            raise ValueError(f"{name} must be a string")
    for name in _TUPLE_FIELDS:
        if name not in payload:
            continue
        value = payload[name]
        if not isinstance(value, (list, tuple)) or any(
            not isinstance(entry, str) for entry in value
        ):
            raise ValueError(f"{name} must be an array of strings")
    for name in _MONEY_FIELDS:
        if (
            name in payload
            and payload[name] is not None
            and not isinstance(payload[name], (str, Decimal))
        ):
            raise ValueError(f"{name} must be a decimal string or null")
    for name in _INTEGER_FIELDS:
        if name not in payload or payload[name] is None:
            continue
        value = payload[name]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{name} must be an integer or null")
    if "has_designers" in payload:
        value = payload["has_designers"]
        if value is not None and not isinstance(value, bool):
            raise ValueError("has_designers must be a boolean or null")
    if "confirmation_version" in payload:
        value = payload["confirmation_version"]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("confirmation_version must be an integer")


def _string_tuple(value: object) -> tuple[str, ...]:
    values: Iterable[object]
    if isinstance(value, str):
        values = value.replace(";", "\n").splitlines()
    elif isinstance(value, (list, tuple, set)):
        values = value
    else:
        return ()
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        rendered = str(item).strip()
        identity = rendered.casefold()
        if rendered and identity not in seen:
            seen.add(identity)
            result.append(rendered)
    return tuple(result)


def _optional_decimal(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    if isinstance(value, (bool, float)):
        raise ValueError("Capability money values must use Decimal or decimal strings")
    try:
        parsed = Decimal(str(value).replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid decimal value: {value!r}") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ValueError("Capability money values must be finite and non-negative")
    return parsed


def _optional_non_negative_int(value: object, *, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be a non-negative integer or null")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return value


def _canonical_decimal(value: Decimal) -> str:
    if value.is_zero():
        return "0"
    return format(value.normalize(), "f")


def _aware_iso(value: str, *, field_name: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")


__all__ = [
    "CompanyCapabilityLoadResult",
    "CompanyCapabilityLoadStatus",
    "CompanyCapabilityProfile",
    "CompanyCapabilityProfileRepository",
    "migrate_company_capability_v1",
]
