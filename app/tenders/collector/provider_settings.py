"""Persistent, non-secret source enablement for Tender Collector."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from threading import RLock
from typing import Mapping

from app.tenders.provider_base import ProviderDescriptor


@dataclass(frozen=True, slots=True)
class ProviderEnablement:
    """A single user-controlled provider switch."""

    provider_id: str
    enabled: bool

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id must not be empty")


class ProviderEnablementRepository:
    """Store source switches atomically without credentials or tokens."""

    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self._lock = RLock()

    def load(self) -> dict[str, bool]:
        with self._lock:
            if not self.path.is_file():
                return {}
            try:
                payload = json.loads(
                    self.path.read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError, TypeError):
                return {}
            if not isinstance(payload, dict):
                return {}
            providers = payload.get("providers", {})
            if not isinstance(providers, dict):
                return {}
            return {
                str(provider_id).strip().casefold(): bool(enabled)
                for provider_id, enabled in providers.items()
                if str(provider_id).strip()
            }

    def save(self, values: Mapping[str, bool]) -> None:
        normalized = {
            str(provider_id).strip().casefold(): bool(enabled)
            for provider_id, enabled in values.items()
            if str(provider_id).strip()
        }
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema_version": self.SCHEMA_VERSION,
                "providers": dict(sorted(normalized.items())),
            }
            temporary = self.path.with_suffix(
                self.path.suffix + ".tmp"
            )
            temporary.write_text(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            temporary.replace(self.path)

    def set_enabled(
        self,
        provider_id: str,
        enabled: bool,
    ) -> ProviderEnablement:
        normalized = provider_id.strip().casefold()
        if not normalized:
            raise ValueError("provider_id must not be empty")
        values = self.load()
        values[normalized] = bool(enabled)
        self.save(values)
        return ProviderEnablement(normalized, bool(enabled))

    def is_enabled(
        self,
        descriptor: ProviderDescriptor,
    ) -> bool:
        values = self.load()
        return values.get(
            descriptor.id.strip().casefold(),
            descriptor.enabled_by_default,
        )


__all__ = [
    "ProviderEnablement",
    "ProviderEnablementRepository",
]
