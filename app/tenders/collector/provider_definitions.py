"""Pure canonical provider identity used by every Collector consumer."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from app.tenders.collector.manual_provider_registration import (
    ManualProviderConflictError,
    ManualProviderErrorCategory,
    ManualProviderLifecycle,
    ManualProviderRegistration,
    manual_display_name_key,
    validate_manual_registration_uniqueness,
)
from app.tenders.models import TenderSource
from app.tenders.provider_base import ProviderCapabilities, ProviderDescriptor
from app.tenders.providers.commercial_catalog import (
    default_commercial_provider_definitions,
)
from app.tenders.providers.eis_async import AsyncEisTenderProvider
from app.tenders.providers.mos_supplier_api import AsyncMosSupplierTenderProvider


_PROVIDER_ALIASES = {
    "sber_a": "sber_commercial",
    "rts_tender": "rts_commercial",
    "roseltorg": "roseltorg_commercial",
}


class ProviderCatalogOrigin(StrEnum):
    BUILTIN = "builtin"
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class ProviderCatalogEntry:
    descriptor: ProviderDescriptor
    origin: ProviderCatalogOrigin
    lifecycle: ManualProviderLifecycle | None = None
    registration_only: bool = False
    runnable: bool = True
    protocol_configured: bool = True
    adapter_compiled: bool = True
    factory_available: bool = True
    credential_available: bool = False
    health_check_available: bool = True
    manual_registration: ManualProviderRegistration | None = None


def canonical_provider_definitions() -> tuple[ProviderDescriptor, ...]:
    """Return the single ordered async/Collector descriptor catalog."""

    definitions = (
        AsyncEisTenderProvider.descriptor,
        AsyncMosSupplierTenderProvider.descriptor,
        *(item.descriptor for item in default_commercial_provider_definitions()),
    )
    ids = tuple(item.id.strip().casefold() for item in definitions)
    sources = tuple(item.source for item in definitions)
    if len(ids) != len(set(ids)):
        raise ValueError("canonical provider ids must be unique")
    if len(sources) != len(set(sources)):
        raise ValueError("canonical provider sources must be unique")
    return definitions


def provider_aliases() -> dict[str, str]:
    """Return a copy of the audited legacy-to-canonical alias table."""

    return dict(_PROVIDER_ALIASES)


def resolved_provider_catalog(
    manual_registrations: Iterable[ManualProviderRegistration] = (),
) -> tuple[ProviderCatalogEntry, ...]:
    """Project built-ins and inert manual registrations through one read model."""

    builtins = canonical_provider_definitions()
    registrations = tuple(sorted(manual_registrations, key=lambda item: item.provider_id))
    validate_manual_registration_uniqueness(registrations)

    builtin_ids = {item.id.casefold() for item in builtins}
    aliases = provider_aliases()
    if set(aliases).intersection(builtin_ids):
        raise ValueError("provider alias collides with canonical provider id")
    if not set(aliases.values()).issubset(builtin_ids):
        raise ValueError("provider alias target is not canonical")
    builtin_name_keys = {manual_display_name_key(item.display_name) for item in builtins}
    for registration in registrations:
        if registration.provider_id in builtin_ids or registration.provider_id in aliases:
            raise ValueError("manual provider identity collides with canonical catalog")
        if registration.display_name_key in builtin_name_keys:
            raise ManualProviderConflictError(ManualProviderErrorCategory.DUPLICATE_NAME)

    entries = [
        ProviderCatalogEntry(
            descriptor=descriptor,
            origin=ProviderCatalogOrigin.BUILTIN,
            credential_available=descriptor.id != "eis",
        )
        for descriptor in builtins
    ]
    entries.extend(
        ProviderCatalogEntry(
            descriptor=ProviderDescriptor(
                id=registration.provider_id,
                display_name=registration.display_name,
                source=TenderSource.CUSTOM,
                homepage_url=registration.homepage_url,
                capabilities=ProviderCapabilities(),
                enabled_by_default=False,
                priority=1000,
                implementation_status="manual_registration",
            ),
            origin=ProviderCatalogOrigin.MANUAL,
            lifecycle=registration.lifecycle_state,
            registration_only=True,
            runnable=False,
            protocol_configured=registration.protocol_selection is not None,
            adapter_compiled=registration.adapter_spec is not None,
            factory_available=registration.adapter_spec is not None,
            credential_available=False,
            health_check_available=False,
            manual_registration=registration,
        )
        for registration in registrations
    )
    return tuple(entries)


def canonical_provider_id(provider_id: str) -> str:
    """Resolve a known canonical ID or explicit audited alias."""

    normalized = str(provider_id).strip().casefold()
    known = {item.id.casefold() for item in canonical_provider_definitions()}
    if normalized in known:
        return normalized
    try:
        return _PROVIDER_ALIASES[normalized]
    except KeyError as exc:
        raise KeyError(provider_id) from exc


def resolve_provider_ids(provider_ids: Iterable[object]) -> tuple[str, ...]:
    """Resolve and first-seen deduplicate a provider selection."""

    resolved: list[str] = []
    seen: set[str] = set()
    for provider_id in provider_ids:
        canonical = canonical_provider_id(str(provider_id))
        if canonical not in seen:
            seen.add(canonical)
            resolved.append(canonical)
    return tuple(resolved)


__all__ = [
    "ProviderCatalogEntry",
    "ProviderCatalogOrigin",
    "canonical_provider_definitions",
    "canonical_provider_id",
    "provider_aliases",
    "resolved_provider_catalog",
    "resolve_provider_ids",
]
