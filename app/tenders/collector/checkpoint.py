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
    contract_version: str = ""
    parser_version: str = ""
    query_fingerprint: str = ""
    last_accepted_page_id: str = ""
    accepted_page_count: int = 0
    accepted_item_count: int = 0
    replay_generation: int = 0
    committed_at: str = ""
    state: Mapping[str, object] = field(default_factory=dict)
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id must not be empty")
        if not self.scope_key.strip():
            raise ValueError("scope_key must not be empty")
        if self.query_fingerprint and len(self.query_fingerprint) != 64:
            raise ValueError("query_fingerprint must be SHA-256")
        if self.accepted_page_count < 0 or self.accepted_item_count < 0:
            raise ValueError("accepted checkpoint counters must be non-negative")
        if self.replay_generation < 0:
            raise ValueError("replay_generation must be non-negative")


@dataclass(frozen=True, slots=True)
class AcceptedPageReceipt:
    run_id: str
    provider_id: str
    page_identity: str
    content_digest: str
    item_count: int
    artifact_count: int
    accepted_at: str
    checkpoint: CollectorCheckpoint

    def __post_init__(self) -> None:
        if not self.run_id.strip() or not self.page_identity.strip():
            raise ValueError("accepted page receipt identity is required")
        if len(self.content_digest) != 64:
            raise ValueError("accepted page receipt digest must be SHA-256")
        if self.item_count < 0 or self.artifact_count < 0:
            raise ValueError("accepted page receipt counters must be non-negative")


__all__ = ["AcceptedPageReceipt", "CollectorCheckpoint"]
