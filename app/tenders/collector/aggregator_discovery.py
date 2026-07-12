"""C20 aggregator discovery queue; aggregator values never become official data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
import json
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Callable
from uuid import uuid4

from app.tenders.collector.codec import tender_from_payload, tender_to_payload
from app.tenders.models import TenderSource, UnifiedTender
from app.tenders.provider_base import TenderSearchQuery


class AggregatorDiscoveryStatus(StrEnum):
    PENDING_OFFICIAL_VERIFICATION = "pending_official_verification"
    OFFICIAL_MATCH_FOUND = "official_match_found"
    OFFICIAL_MATCH_NOT_FOUND = "official_match_not_found"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class AggregatorDiscoveryRecord:
    discovery_id: str
    aggregator_source: str
    aggregator_external_id: str
    source_url: str
    title: str
    procurement_number_hint: str
    official_query: str
    status: AggregatorDiscoveryStatus
    first_discovered_at: str
    last_discovered_at: str
    candidate: UnifiedTender
    official_registry_key: str = ""
    verification_note: str = ""

    def __post_init__(self) -> None:
        if not self.discovery_id.strip() or not self.aggregator_source.strip():
            raise ValueError("discovery_id and aggregator_source must not be empty")
        if not is_aggregator_discovery(self.candidate):
            raise ValueError("candidate must be explicitly marked discovery-only")

    @property
    def can_influence_decision(self) -> bool:
        return False


class AggregatorDiscoveryRepository:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self._lock = RLock()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS collector_aggregator_discoveries (
                    discovery_id TEXT PRIMARY KEY,
                    aggregator_source TEXT NOT NULL,
                    aggregator_external_id TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    procurement_number_hint TEXT NOT NULL DEFAULT '',
                    official_query TEXT NOT NULL,
                    status TEXT NOT NULL,
                    first_discovered_at TEXT NOT NULL,
                    last_discovered_at TEXT NOT NULL,
                    candidate_json TEXT NOT NULL,
                    official_registry_key TEXT NOT NULL DEFAULT '',
                    verification_note TEXT NOT NULL DEFAULT '',
                    UNIQUE(aggregator_source, aggregator_external_id)
                );
                CREATE INDEX IF NOT EXISTS idx_aggregator_discovery_queue
                    ON collector_aggregator_discoveries(
                        status,
                        last_discovered_at
                    );
            """)

    def enqueue(
        self,
        tender: UnifiedTender,
        *,
        discovered_at: str | None = None,
    ) -> AggregatorDiscoveryRecord:
        if not is_aggregator_discovery(tender):
            raise ValueError("only explicit aggregator discovery can enter this queue")
        moment = discovered_at or _now()
        source = tender.source.value
        query = tender.procurement_number.strip() or tender.title.strip()
        self.initialize()
        with self._lock, self._connect() as connection:
            existing = connection.execute(
                """SELECT discovery_id, first_discovered_at
                FROM collector_aggregator_discoveries
                WHERE aggregator_source=? AND aggregator_external_id=?""",
                (source, tender.external_id),
            ).fetchone()
            discovery_id = str(existing["discovery_id"]) if existing else uuid4().hex
            first = str(existing["first_discovered_at"]) if existing else moment
            connection.execute(
                """INSERT INTO collector_aggregator_discoveries(
                    discovery_id, aggregator_source, aggregator_external_id,
                    source_url, title, procurement_number_hint, official_query,
                    status, first_discovered_at, last_discovered_at,
                    candidate_json, official_registry_key, verification_note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', '')
                ON CONFLICT(aggregator_source, aggregator_external_id) DO UPDATE SET
                    source_url=excluded.source_url,
                    title=excluded.title,
                    procurement_number_hint=excluded.procurement_number_hint,
                    official_query=excluded.official_query,
                    status=excluded.status,
                    last_discovered_at=excluded.last_discovered_at,
                    candidate_json=excluded.candidate_json,
                    official_registry_key='',
                    verification_note=''""",
                (
                    discovery_id, source, tender.external_id, tender.source_url,
                    tender.title, tender.procurement_number, query,
                    AggregatorDiscoveryStatus.PENDING_OFFICIAL_VERIFICATION.value,
                    first, moment,
                    json.dumps(tender_to_payload(tender), ensure_ascii=False, sort_keys=True),
                ),
            )
        return self.get(discovery_id)

    def get(self, discovery_id: str) -> AggregatorDiscoveryRecord:
        self.initialize()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM collector_aggregator_discoveries WHERE discovery_id=?",
                (discovery_id.strip(),),
            ).fetchone()
        if row is None:
            raise KeyError(discovery_id)
        return _row_to_record(row)

    def list_pending(self, *, limit: int = 100) -> tuple[AggregatorDiscoveryRecord, ...]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        self.initialize()
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM collector_aggregator_discoveries
                WHERE status=? ORDER BY last_discovered_at, discovery_id LIMIT ?""",
                (AggregatorDiscoveryStatus.PENDING_OFFICIAL_VERIFICATION.value, limit),
            ).fetchall()
        return tuple(_row_to_record(row) for row in rows)

    def list_all(self, *, limit: int = 500) -> tuple[AggregatorDiscoveryRecord, ...]:
        self.initialize()
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM collector_aggregator_discoveries ORDER BY last_discovered_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return tuple(_row_to_record(row) for row in rows)

    def resolve(
        self,
        discovery_id: str,
        *,
        official_tender: UnifiedTender | None,
        note: str = "",
    ) -> AggregatorDiscoveryRecord:
        if official_tender is not None and official_tender.source not in {
            TenderSource.EIS,
            TenderSource.MOS_SUPPLIER,
        }:
            raise ValueError("official match must come from EIS or Supplier Portal")
        status = (
            AggregatorDiscoveryStatus.OFFICIAL_MATCH_FOUND
            if official_tender is not None
            else AggregatorDiscoveryStatus.OFFICIAL_MATCH_NOT_FOUND
        )
        registry_key = official_tender.identity_key if official_tender is not None else ""
        self.initialize()
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """UPDATE collector_aggregator_discoveries
                SET status=?, official_registry_key=?, verification_note=?
                WHERE discovery_id=?""",
                (status.value, registry_key, note.strip(), discovery_id.strip()),
            )
            if cursor.rowcount != 1:
                raise KeyError(discovery_id)
        return self.get(discovery_id)

    def mark_failed(self, discovery_id: str, error: str) -> AggregatorDiscoveryRecord:
        self.initialize()
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """UPDATE collector_aggregator_discoveries
                SET status=?, verification_note=? WHERE discovery_id=?""",
                (AggregatorDiscoveryStatus.FAILED.value, error.strip(), discovery_id.strip()),
            )
            if cursor.rowcount != 1:
                raise KeyError(discovery_id)
        return self.get(discovery_id)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        return connection


OfficialLookup = Callable[[TenderSearchQuery], UnifiedTender | None]


class AggregatorOfficialVerificationService:
    def __init__(
        self,
        repository: AggregatorDiscoveryRepository,
        official_lookup: OfficialLookup,
    ) -> None:
        self.repository = repository
        self.official_lookup = official_lookup

    def verify_pending(self, *, limit: int = 100) -> tuple[AggregatorDiscoveryRecord, ...]:
        results = []
        for record in self.repository.list_pending(limit=limit):
            query = TenderSearchQuery(
                keywords=(record.official_query,),
                page=1,
                page_size=10,
                extra={"official_verification": True, "incremental": False},
            )
            try:
                official = self.official_lookup(query)
                results.append(self.repository.resolve(
                    record.discovery_id,
                    official_tender=official,
                    note=(
                        "Подтверждено официальным источником."
                        if official is not None
                        else "Совпадение в официальном источнике не найдено."
                    ),
                ))
            except Exception as exc:
                results.append(self.repository.mark_failed(
                    record.discovery_id,
                    f"{type(exc).__name__}: {exc}",
                ))
        return tuple(results)


def is_aggregator_discovery(tender: UnifiedTender) -> bool:
    metadata = tender.raw_metadata
    return bool(
        metadata.get("aggregator")
        or metadata.get("discovery_only")
        or str(metadata.get("source_kind", "")).casefold()
        in {"aggregator", "discovery_aggregator"}
    )


def _row_to_record(row: sqlite3.Row) -> AggregatorDiscoveryRecord:
    return AggregatorDiscoveryRecord(
        discovery_id=str(row["discovery_id"]),
        aggregator_source=str(row["aggregator_source"]),
        aggregator_external_id=str(row["aggregator_external_id"]),
        source_url=str(row["source_url"]),
        title=str(row["title"]),
        procurement_number_hint=str(row["procurement_number_hint"]),
        official_query=str(row["official_query"]),
        status=AggregatorDiscoveryStatus(str(row["status"])),
        first_discovered_at=str(row["first_discovered_at"]),
        last_discovered_at=str(row["last_discovered_at"]),
        candidate=tender_from_payload(json.loads(str(row["candidate_json"]))),
        official_registry_key=str(row["official_registry_key"]),
        verification_note=str(row["verification_note"]),
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


__all__ = [
    "AggregatorDiscoveryRecord", "AggregatorDiscoveryRepository",
    "AggregatorDiscoveryStatus", "AggregatorOfficialVerificationService",
    "is_aggregator_discovery",
]
