"""Editable, explicitly confirmed company capability profile."""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from threading import RLock
from typing import Mapping


@dataclass(frozen=True, slots=True)
class CompanyCapabilityProfile:
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
    updated_at: str = ""

    def __post_init__(self) -> None:
        for name in _TUPLE_FIELDS:
            object.__setattr__(self, name, _string_tuple(getattr(self, name)))
        for name in _MONEY_FIELDS:
            object.__setattr__(self, name, _optional_decimal(getattr(self, name)))
        for name in _INTEGER_FIELDS:
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} must be non-negative")
        if (
            self.minimum_margin_percent is not None
            and self.minimum_margin_percent > 100
        ):
            raise ValueError("minimum_margin_percent cannot exceed 100")
        for name in ("confirmed_at", "updated_at"):
            value = getattr(self, name)
            if value:
                object.__setattr__(self, name, _aware_iso(value, field_name=name))

    @property
    def is_confirmed(self) -> bool:
        return bool(self.confirmed_at and self.confirmed_by.strip())

    @property
    def is_configured(self) -> bool:
        return bool(
            self.company_name.strip()
            and self.is_confirmed
            and any(
                (
                    self.business_directions,
                    self.licenses,
                    self.sro_memberships,
                    self.confirmed_experience,
                    self.self_install_regions,
                    self.partner_regions,
                    self.equipment,
                    self.suppliers,
                    self.max_project_amount is not None,
                    self.working_capital is not None,
                )
            )
        )

    @property
    def missing_sections(self) -> tuple[str, ...]:
        missing: list[str] = []
        if not self.business_directions:
            missing.append("направления деятельности")
        if not self.self_install_regions and not self.partner_regions:
            missing.append("регионы выполнения работ")
        if not self.licenses and not self.sro_memberships:
            missing.append("лицензии и СРО")
        if not self.confirmed_experience:
            missing.append("подтверждённый опыт")
        if self.installation_crew_count is None:
            missing.append("монтажные бригады")
        if self.max_project_amount is None or self.working_capital is None:
            missing.append("финансовые возможности")
        if not self.equipment and not self.brands:
            missing.append("оборудование и бренды")
        if not self.suppliers:
            missing.append("поставщики")
        return tuple(missing)

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
    def from_dict(cls, payload: Mapping[str, object]) -> "CompanyCapabilityProfile":
        known = {item.name for item in fields(cls)}
        return cls(**{key: value for key, value in payload.items() if key in known})


class CompanyCapabilityProfileRepository:
    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self._lock = RLock()

    def load(self) -> CompanyCapabilityProfile:
        with self._lock:
            if not self.path.is_file():
                return CompanyCapabilityProfile()
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
                raw_profile = payload.get("profile", {})
                if not isinstance(raw_profile, dict):
                    raise ValueError("profile must be an object")
                return CompanyCapabilityProfile.from_dict(raw_profile)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                return CompanyCapabilityProfile()

    def save(self, profile: CompanyCapabilityProfile) -> None:
        if not profile.is_confirmed:
            raise ValueError("Профиль должен быть явно подтверждён пользователем")
        if not profile.company_name.strip():
            raise ValueError("Укажите название компании")
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        stored = CompanyCapabilityProfile.from_dict(
            {**profile.to_dict(), "updated_at": timestamp}
        )
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "profile": stored.to_dict(),
        }
        with self._lock:
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


_TUPLE_FIELDS = {
    "business_directions", "self_install_regions", "partner_regions",
    "licenses", "license_work_types", "sro_memberships",
    "employee_qualifications", "completed_contracts", "confirmed_experience",
    "equipment", "brands", "suppliers", "stock_items",
    "self_performed_directions", "subcontracted_directions",
    "undesired_object_types", "regional_partners",
}
_MONEY_FIELDS = {
    "max_project_amount", "working_capital", "max_bid_security",
    "max_contract_security", "bank_guarantee_limit", "minimum_margin_percent",
}
_INTEGER_FIELDS = {
    "installation_crew_count", "acceptable_payment_days", "maximum_deferment_days",
}


def _string_tuple(value: object) -> tuple[str, ...]:
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
    try:
        parsed = Decimal(str(value).replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid decimal value: {value!r}") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ValueError("Capability money values must be finite and non-negative")
    return parsed


def _aware_iso(value: str, *, field_name: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")


__all__ = ["CompanyCapabilityProfile", "CompanyCapabilityProfileRepository"]
