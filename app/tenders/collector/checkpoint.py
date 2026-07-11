"""Incremental provider checkpoint model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True, slots=True)
class CollectorCheckpoint:
    provider_id: str
    scope_key: str = "default"
    cursor: str = ""
    watermark: str = ""
    state: Mapping[str, object] = field(default_factory=dict)
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id must not be empty")
        if not self.scope_key.strip():
            raise ValueError("scope_key must not be empty")


__all__ = ["CollectorCheckpoint"]
