"""C20 aggregator discovery queue; aggregator values never become official data."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from difflib import SequenceMatcher
from enum import StrEnum
import json
from pathlib import Path
import re
import sqlite3
from threading import RLock
from typing import Callable
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from app.tenders.collector.async_http import sanitize_url
from app.tenders.collector.codec import tender_from_payload, tender_to_payload
from app.tenders.collector.search_errors import classify_search_error, safe_provider_warnings
from app.tenders.collector_database import initialize_collector_database
from app.tenders.corteris_filter import normalize_text
from app.tenders.models import TenderSource, UnifiedTender, is_timezone_aware
from app.tenders.provider_base import TenderSearchQuery


class AggregatorDiscoveryStatus(StrEnum):
    PENDING_OFFICIAL_VERIFICATION = "pending_official_verification"
    OFFICIAL_MATCH_FOUND = "official_match_found"
    OFFICIAL_MATCH_NOT_FOUND = "official_match_not_found"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"
    FAILED = "failed"


class OfficialIdentityDecision(StrEnum):
    MATCH = "match"
    REJECT = "reject"
    MANUAL_REVIEW = "manual_review"


class AggregatorDiscoveryCapacityError(RuntimeError):
    """Fail closed when the bounded discovery queue cannot safely accept data."""

    def __init__(self) -> None:
        super().__init__("Очередь discovery превысила безопасный лимит.")


@dataclass(frozen=True, slots=True)
class OfficialIdentityMatch:
    decision: OfficialIdentityDecision
    reasons: tuple[str, ...]

    @property
    def confirmed(self) -> bool:
        return self.decision == OfficialIdentityDecision.MATCH


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
    def __init__(
        self,
        path: str | Path,
        *,
        max_records: int = 10_000,
        max_attempts_per_discovery: int = 100,
        max_payload_bytes: int = 64 * 1024,
    ) -> None:
        if max_records < 1:
            raise ValueError("max_records must be positive")
        if max_attempts_per_discovery < 1:
            raise ValueError("max_attempts_per_discovery must be positive")
        if max_payload_bytes < 1:
            raise ValueError("max_payload_bytes must be positive")
        self.path = Path(path).expanduser()
        self.max_records = max_records
        self.max_attempts_per_discovery = max_attempts_per_discovery
        self.max_payload_bytes = max_payload_bytes
        self._lock = RLock()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            initialize_collector_database(self.path)

    def enqueue(
        self,
        tender: UnifiedTender,
        *,
        discovered_at: str | None = None,
    ) -> AggregatorDiscoveryRecord:
        if not is_aggregator_discovery(tender):
            raise ValueError("only explicit aggregator discovery can enter this queue")
        candidate = _minimize_discovery_candidate(tender)
        candidate_json = json.dumps(
            tender_to_payload(candidate),
            ensure_ascii=False,
            sort_keys=True,
        )
        if len(candidate_json.encode("utf-8")) > self.max_payload_bytes:
            raise AggregatorDiscoveryCapacityError()
        moment = discovered_at or _now()
        source = candidate.source.value
        query = candidate.procurement_number.strip() or candidate.title.strip()
        self.initialize()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """SELECT discovery_id, first_discovered_at
                FROM collector_aggregator_discoveries
                WHERE aggregator_source=? AND aggregator_external_id=?""",
                (source, candidate.external_id),
            ).fetchone()
            if existing is None:
                self._ensure_capacity(connection)
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
                    discovery_id,
                    source,
                    candidate.external_id,
                    candidate.source_url,
                    candidate.title,
                    candidate.procurement_number,
                    query,
                    AggregatorDiscoveryStatus.PENDING_OFFICIAL_VERIFICATION.value,
                    first,
                    moment,
                    candidate_json,
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
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
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
        self.initialize()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM collector_aggregator_discoveries WHERE discovery_id=?",
                (discovery_id.strip(),),
            ).fetchone()
            if row is None:
                raise KeyError(discovery_id)
            match = (
                match_official_identity(_row_to_record(row).candidate, official_tender)
                if official_tender is not None
                else OfficialIdentityMatch(
                    OfficialIdentityDecision.REJECT,
                    ("Официальный кандидат не найден.",),
                )
            )
            if match.decision == OfficialIdentityDecision.MATCH:
                status = AggregatorDiscoveryStatus.OFFICIAL_MATCH_FOUND
                registry_key = official_tender.identity_key if official_tender else ""
            elif match.decision == OfficialIdentityDecision.MANUAL_REVIEW:
                status = AggregatorDiscoveryStatus.MANUAL_REVIEW_REQUIRED
                registry_key = ""
            else:
                status = AggregatorDiscoveryStatus.OFFICIAL_MATCH_NOT_FOUND
                registry_key = ""
            safe_note = _safe_discovery_note(note)
            rendered_note = _safe_discovery_note(
                " ".join(part for part in (safe_note, *match.reasons) if part)
            )
            cursor = connection.execute(
                """UPDATE collector_aggregator_discoveries
                SET status=?, official_registry_key=?, verification_note=?
                WHERE discovery_id=?""",
                (status.value, registry_key, rendered_note, discovery_id.strip()),
            )
            if cursor.rowcount != 1:
                raise KeyError(discovery_id)
            connection.execute(
                """INSERT INTO collector_aggregator_verification_attempts(
                    attempt_id, discovery_id, attempted_at, outcome,
                    official_registry_key, note, evidence_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    uuid4().hex,
                    discovery_id.strip(),
                    _now(),
                    match.decision.value,
                    official_tender.identity_key if official_tender is not None else "",
                    safe_note,
                    json.dumps(match.reasons, ensure_ascii=False),
                ),
            )
            self._prune_attempts(connection, discovery_id)
        return self.get(discovery_id)

    def list_attempts(self, discovery_id: str) -> tuple[dict[str, object], ...]:
        self.initialize()
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """SELECT attempt_id, attempted_at, outcome, official_registry_key,
                          note, evidence_json
                FROM collector_aggregator_verification_attempts
                WHERE discovery_id=? ORDER BY attempted_at, rowid""",
                (discovery_id.strip(),),
            ).fetchall()
        return tuple(
            {
                "attempt_id": str(row["attempt_id"]),
                "attempted_at": str(row["attempted_at"]),
                "outcome": str(row["outcome"]),
                "official_registry_key": str(row["official_registry_key"]),
                "note": str(row["note"]),
                "evidence": tuple(json.loads(str(row["evidence_json"]))),
            }
            for row in rows
        )

    def mark_failed(
        self,
        discovery_id: str,
        error: BaseException | str,
    ) -> AggregatorDiscoveryRecord:
        if isinstance(error, BaseException):
            failure = classify_search_error(error)
            safe_error = failure.message
            evidence = (failure.code,)
        else:
            safe_error = "Официальная проверка завершилась с безопасно скрытой ошибкой."
            evidence = ("provider_internal_error",)
        self.initialize()
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """UPDATE collector_aggregator_discoveries
                SET status=?, verification_note=? WHERE discovery_id=?""",
                (AggregatorDiscoveryStatus.FAILED.value, safe_error, discovery_id.strip()),
            )
            if cursor.rowcount != 1:
                raise KeyError(discovery_id)
            connection.execute(
                """INSERT INTO collector_aggregator_verification_attempts(
                    attempt_id, discovery_id, attempted_at, outcome, note, evidence_json
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    uuid4().hex,
                    discovery_id.strip(),
                    _now(),
                    AggregatorDiscoveryStatus.FAILED.value,
                    safe_error,
                    json.dumps(evidence, ensure_ascii=False),
                ),
            )
            self._prune_attempts(connection, discovery_id)
        return self.get(discovery_id)

    def _ensure_capacity(self, connection: sqlite3.Connection) -> None:
        total = int(
            connection.execute("SELECT COUNT(*) FROM collector_aggregator_discoveries").fetchone()[
                0
            ]
        )
        if total < self.max_records:
            return
        required_evictions = total - self.max_records + 1
        terminal_rows = connection.execute(
            """SELECT discovery_id
            FROM collector_aggregator_discoveries
            WHERE status IN (?, ?, ?)
            ORDER BY last_discovered_at, discovery_id
            LIMIT ?""",
            (
                AggregatorDiscoveryStatus.OFFICIAL_MATCH_FOUND.value,
                AggregatorDiscoveryStatus.OFFICIAL_MATCH_NOT_FOUND.value,
                AggregatorDiscoveryStatus.FAILED.value,
                required_evictions,
            ),
        ).fetchall()
        if len(terminal_rows) != required_evictions:
            raise AggregatorDiscoveryCapacityError()
        for terminal in terminal_rows:
            discovery_id = str(terminal["discovery_id"])
            connection.execute(
                "DELETE FROM collector_aggregator_verification_attempts WHERE discovery_id=?",
                (discovery_id,),
            )
            connection.execute(
                "DELETE FROM collector_aggregator_discoveries WHERE discovery_id=?",
                (discovery_id,),
            )

    def _prune_attempts(
        self,
        connection: sqlite3.Connection,
        discovery_id: str,
    ) -> None:
        connection.execute(
            """DELETE FROM collector_aggregator_verification_attempts
            WHERE discovery_id=?
              AND rowid NOT IN (
                SELECT rowid
                FROM collector_aggregator_verification_attempts
                WHERE discovery_id=?
                ORDER BY rowid DESC
                LIMIT ?
              )""",
            (
                discovery_id.strip(),
                discovery_id.strip(),
                self.max_attempts_per_discovery,
            ),
        )

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
                results.append(
                    self.repository.resolve(
                        record.discovery_id,
                        official_tender=official,
                        note=(
                            "Подтверждено официальным источником."
                            if official is not None
                            else "Совпадение в официальном источнике не найдено."
                        ),
                    )
                )
            except Exception as exc:
                results.append(
                    self.repository.mark_failed(
                        record.discovery_id,
                        exc,
                    )
                )
        return tuple(results)


def is_aggregator_discovery(tender: UnifiedTender) -> bool:
    metadata = tender.raw_metadata
    return bool(
        metadata.get("aggregator")
        or metadata.get("discovery_only")
        or str(metadata.get("source_kind", "")).casefold() in {"aggregator", "discovery_aggregator"}
    )


def _minimize_discovery_candidate(tender: UnifiedTender) -> UnifiedTender:
    metadata: dict[str, object] = {}
    if bool(tender.raw_metadata.get("aggregator")):
        metadata["aggregator"] = True
    if bool(tender.raw_metadata.get("discovery_only")):
        metadata["discovery_only"] = True
    source_kind = str(tender.raw_metadata.get("source_kind", "")).strip().casefold()
    if source_kind in {"aggregator", "discovery_aggregator"}:
        metadata["source_kind"] = source_kind
    return replace(
        tender,
        customer=replace(
            tender.customer,
            kpp="",
            region="",
            address="",
        ),
        source_url=_safe_discovery_url(tender.source_url),
        description="",
        classification_codes=(),
        tags=(),
        documents=(),
        raw_metadata=metadata,
    )


def _safe_discovery_url(value: str) -> str:
    parsed = urlsplit(sanitize_url(value))
    hostname = parsed.hostname or ""
    if ":" in hostname:
        hostname = f"[{hostname}]"
    port = f":{parsed.port}" if parsed.port is not None else ""
    return urlunsplit((parsed.scheme, f"{hostname}{port}", parsed.path, parsed.query, ""))


def _safe_discovery_note(value: object, *, fallback: str = "") -> str:
    rendered = safe_provider_warnings((str(value),))
    return rendered[0] if rendered else fallback


def match_official_identity(
    discovery: UnifiedTender,
    official: UnifiedTender,
) -> OfficialIdentityMatch:
    """Confirm identity without importing aggregator values as official facts."""

    hint = _normalized_procurement_number(discovery.procurement_number)
    official_number = _normalized_procurement_number(official.procurement_number)
    if _is_strong_procurement_number(hint):
        if hint == official_number:
            return OfficialIdentityMatch(
                OfficialIdentityDecision.MATCH,
                ("Совпадает нормализованный номер закупки.",),
            )
        return OfficialIdentityMatch(
            OfficialIdentityDecision.REJECT,
            ("Номер закупки официального кандидата не совпадает.",),
        )

    discovery_inn = re.sub(r"\D", "", discovery.customer.inn)
    official_inn = re.sub(r"\D", "", official.customer.inn)
    if not discovery_inn or discovery_inn != official_inn:
        return OfficialIdentityMatch(
            OfficialIdentityDecision.MANUAL_REVIEW,
            ("Нет подтверждённого совпадения номера закупки и ИНН заказчика.",),
        )

    title_similarity = SequenceMatcher(
        None,
        normalize_text(discovery.title),
        normalize_text(official.title),
    ).ratio()
    price_matches = bool(
        discovery.price
        and official.price
        and discovery.price.currency == official.price.currency
        and discovery.price.amount == official.price.amount
    )
    deadline_matches = bool(
        discovery.application_deadline
        and official.application_deadline
        and is_timezone_aware(discovery.application_deadline)
        and is_timezone_aware(official.application_deadline)
        and discovery.application_deadline.astimezone(timezone.utc)
        == official.application_deadline.astimezone(timezone.utc)
    )
    supporting = sum((title_similarity >= 0.8, price_matches, deadline_matches))
    if supporting >= 2:
        return OfficialIdentityMatch(
            OfficialIdentityDecision.MATCH,
            ("Совпали ИНН заказчика и не менее двух вторичных признаков.",),
        )
    return OfficialIdentityMatch(
        OfficialIdentityDecision.MANUAL_REVIEW,
        ("Совпадение по ИНН недостаточно подтверждено вторичными признаками.",),
    )


def _normalized_procurement_number(value: str) -> str:
    return re.sub(r"[^0-9a-zа-я]", "", value.casefold())


def _is_strong_procurement_number(value: str) -> bool:
    return len(value) >= 10 and sum(character.isdigit() for character in value) >= 8


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
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


__all__ = [
    "AggregatorDiscoveryCapacityError",
    "AggregatorDiscoveryRecord",
    "AggregatorDiscoveryRepository",
    "AggregatorDiscoveryStatus",
    "AggregatorOfficialVerificationService",
    "OfficialIdentityDecision",
    "OfficialIdentityMatch",
    "is_aggregator_discovery",
    "match_official_identity",
]
