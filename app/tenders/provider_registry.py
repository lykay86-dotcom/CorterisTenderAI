"""Registry for tender platform provider adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.tenders.provider_base import TenderProvider


@dataclass(frozen=True, slots=True)
class RegisteredProvider:
    provider: TenderProvider
    enabled: bool
    priority: int

    @property
    def id(self) -> str:
        return self.provider.descriptor.id


class TenderProviderRegistry:
    """Register, configure and enumerate provider adapters."""

    def __init__(
        self,
        providers: Iterable[TenderProvider] = (),
    ) -> None:
        self._providers: dict[str, RegisteredProvider] = {}
        for provider in providers:
            self.register(provider)

    def register(
        self,
        provider: TenderProvider,
        *,
        enabled: bool | None = None,
        priority: int | None = None,
        replace: bool = False,
    ) -> None:
        provider_id = provider.descriptor.id.strip()
        if provider_id in self._providers and not replace:
            raise ValueError(f"Provider already registered: {provider_id}")

        effective_enabled = (
            provider.descriptor.enabled_by_default if enabled is None else bool(enabled)
        )
        effective_priority = provider.descriptor.priority if priority is None else int(priority)
        if effective_priority < 0:
            raise ValueError("priority must be non-negative")

        self._providers[provider_id] = RegisteredProvider(
            provider=provider,
            enabled=effective_enabled,
            priority=effective_priority,
        )

    def unregister(self, provider_id: str) -> TenderProvider:
        try:
            entry = self._providers.pop(provider_id)
        except KeyError as exc:
            raise KeyError(f"Unknown provider: {provider_id}") from exc
        return entry.provider

    def get(self, provider_id: str) -> TenderProvider:
        try:
            return self._providers[provider_id].provider
        except KeyError as exc:
            raise KeyError(f"Unknown provider: {provider_id}") from exc

    def set_enabled(
        self,
        provider_id: str,
        enabled: bool,
    ) -> None:
        entry = self._entry(provider_id)
        self._providers[provider_id] = RegisteredProvider(
            provider=entry.provider,
            enabled=bool(enabled),
            priority=entry.priority,
        )

    def set_priority(
        self,
        provider_id: str,
        priority: int,
    ) -> None:
        if priority < 0:
            raise ValueError("priority must be non-negative")
        entry = self._entry(provider_id)
        self._providers[provider_id] = RegisteredProvider(
            provider=entry.provider,
            enabled=entry.enabled,
            priority=int(priority),
        )

    def is_enabled(self, provider_id: str) -> bool:
        return self._entry(provider_id).enabled

    def list_registered(self) -> tuple[RegisteredProvider, ...]:
        return tuple(
            sorted(
                self._providers.values(),
                key=lambda item: (
                    item.priority,
                    item.provider.descriptor.display_name.casefold(),
                    item.id,
                ),
            )
        )

    def list_enabled(self) -> tuple[TenderProvider, ...]:
        return tuple(entry.provider for entry in self.list_registered() if entry.enabled)

    def descriptors(self):
        return tuple(entry.provider.descriptor for entry in self.list_registered())

    def validate_unique_sources(
        self,
    ) -> dict[str, tuple[str, ...]]:
        """Return source values mapped to provider ids sharing them."""
        grouped: dict[str, list[str]] = {}
        for entry in self._providers.values():
            grouped.setdefault(
                entry.provider.descriptor.source.value,
                [],
            ).append(entry.id)
        return {source: tuple(sorted(ids)) for source, ids in grouped.items() if len(ids) > 1}

    def _entry(self, provider_id: str) -> RegisteredProvider:
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise KeyError(f"Unknown provider: {provider_id}") from exc


__all__ = [
    "RegisteredProvider",
    "TenderProviderRegistry",
]
