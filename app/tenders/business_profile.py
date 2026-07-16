"""Pure application projection of confirmed company capability facts.

The persisted :class:`CompanyCapabilityProfile` remains the raw fact model.  This
module owns the current participation completeness policy and exposes only facts
whose content-bound confirmation is valid.  It deliberately performs no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.tenders.collector.company_capability import CompanyCapabilityProfile


@dataclass(frozen=True, slots=True)
class BusinessCapabilityProjection:
    """Immutable, fail-closed snapshot used by score and stop-factor paths."""

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
    base_currency: str = "RUB"
    evidence_note: str = ""
    confirmed_at: str = ""
    confirmed_by: str = ""
    updated_at: str = ""
    confirmation_version: int | None = None
    confirmation_fingerprint: str = ""
    confirmation_source: str = ""
    is_confirmed: bool = False

    @classmethod
    def from_capability(
        cls,
        capability: "CompanyCapabilityProfile",
    ) -> "BusinessCapabilityProjection":
        """Build a snapshot without consulting persistence or other services.

        A stale or absent content confirmation yields a neutral projection.  RUB
        remains only as the valid placeholder required by the existing scoring
        value object; no capability or financial limit is exposed in that state.
        """

        if not capability.is_confirmed:
            return cls()
        return cls(
            company_name=capability.company_name.strip(),
            business_directions=tuple(capability.business_directions),
            self_install_regions=tuple(capability.self_install_regions),
            partner_regions=tuple(capability.partner_regions),
            licenses=tuple(capability.licenses),
            license_work_types=tuple(capability.license_work_types),
            sro_memberships=tuple(capability.sro_memberships),
            employee_qualifications=tuple(capability.employee_qualifications),
            installation_crew_count=capability.installation_crew_count,
            completed_contracts=tuple(capability.completed_contracts),
            confirmed_experience=tuple(capability.confirmed_experience),
            max_project_amount=capability.max_project_amount,
            working_capital=capability.working_capital,
            max_bid_security=capability.max_bid_security,
            max_contract_security=capability.max_contract_security,
            bank_guarantee_limit=capability.bank_guarantee_limit,
            equipment=tuple(capability.equipment),
            brands=tuple(capability.brands),
            suppliers=tuple(capability.suppliers),
            stock_items=tuple(capability.stock_items),
            minimum_margin_percent=capability.minimum_margin_percent,
            acceptable_payment_days=capability.acceptable_payment_days,
            maximum_deferment_days=capability.maximum_deferment_days,
            self_performed_directions=tuple(capability.self_performed_directions),
            subcontracted_directions=tuple(capability.subcontracted_directions),
            undesired_object_types=tuple(capability.undesired_object_types),
            has_designers=capability.has_designers,
            regional_partners=tuple(capability.regional_partners),
            base_currency=capability.base_currency,
            evidence_note=capability.evidence_note,
            confirmed_at=capability.confirmed_at,
            confirmed_by=capability.confirmed_by,
            updated_at=capability.updated_at,
            confirmation_version=capability.confirmation_version,
            confirmation_fingerprint=capability.confirmation_fingerprint,
            confirmation_source=capability.confirmation_source,
            is_confirmed=True,
        )

    @property
    def is_configured(self) -> bool:
        """Preserve the established partial-profile participation predicate."""

        return bool(
            self.company_name
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
        """Return the existing eight-section Corteris participation policy."""

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
        """Return a deterministic JSON-compatible snapshot for fingerprints."""

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


__all__ = ["BusinessCapabilityProjection"]
