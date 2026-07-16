"""Pure canonical provider identity used by every Collector consumer."""

from __future__ import annotations

from collections.abc import Iterable

from app.tenders.provider_base import ProviderDescriptor
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
    "canonical_provider_definitions",
    "canonical_provider_id",
    "provider_aliases",
    "resolve_provider_ids",
]
