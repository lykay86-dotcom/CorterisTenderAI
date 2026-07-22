"""Low-level canonical provider identity helpers without provider imports."""

from __future__ import annotations

from collections.abc import Iterable


CANONICAL_PROVIDER_IDS = (
    "eis",
    "mos_supplier",
    "zakaz_rf",
    "roseltorg",
    "rad",
    "tek_torg",
    "ets_nep",
    "sber_a",
    "rts_tender",
    "gazprombank",
    "b2b_center",
    "fabrikant",
    "otc",
)

_PROVIDER_ALIASES = {
    "sber_commercial": "sber_a",
    "rts_commercial": "rts_tender",
    "roseltorg_commercial": "roseltorg",
}
_CANONICAL_PROVIDER_ID_SET = frozenset(CANONICAL_PROVIDER_IDS)


def provider_aliases() -> dict[str, str]:
    """Return a copy of the audited legacy-to-canonical alias table."""

    return dict(_PROVIDER_ALIASES)


def canonical_provider_id(provider_id: str) -> str:
    """Resolve a known canonical ID or explicit audited alias."""

    normalized = str(provider_id).strip().casefold()
    if normalized in _CANONICAL_PROVIDER_ID_SET:
        return normalized
    try:
        return _PROVIDER_ALIASES[normalized]
    except KeyError as exc:
        raise KeyError(provider_id) from exc


def canonicalize_known_provider_id(provider_id: object) -> str:
    """Canonicalize an audited alias while retaining an unknown normalized ID."""

    normalized = str(provider_id).strip().casefold()
    return _PROVIDER_ALIASES.get(normalized, normalized)


def canonicalize_provider_ids(provider_ids: Iterable[object]) -> tuple[str, ...]:
    """Canonicalize known aliases and first-seen deduplicate provider IDs."""

    resolved: list[str] = []
    seen: set[str] = set()
    for provider_id in provider_ids:
        canonical = canonicalize_known_provider_id(provider_id)
        if canonical and canonical not in seen:
            seen.add(canonical)
            resolved.append(canonical)
    return tuple(resolved)


def provider_storage_ids(provider_id: object) -> tuple[str, ...]:
    """Return canonical and historical aliases accepted by a read filter."""

    normalized = canonicalize_known_provider_id(provider_id)
    aliases = tuple(
        alias for alias, canonical in _PROVIDER_ALIASES.items() if canonical == normalized
    )
    return (normalized, *aliases)


def resolve_provider_ids(provider_ids: Iterable[object]) -> tuple[str, ...]:
    """Strictly resolve and first-seen deduplicate a provider selection."""

    resolved: list[str] = []
    seen: set[str] = set()
    for provider_id in provider_ids:
        canonical = canonical_provider_id(str(provider_id))
        if canonical not in seen:
            seen.add(canonical)
            resolved.append(canonical)
    return tuple(resolved)


__all__ = [
    "CANONICAL_PROVIDER_IDS",
    "canonical_provider_id",
    "canonicalize_known_provider_id",
    "canonicalize_provider_ids",
    "provider_aliases",
    "provider_storage_ids",
    "resolve_provider_ids",
]
