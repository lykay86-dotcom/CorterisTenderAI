"""SQLite registry for tender-search results and search-run history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum, StrEnum
import json
from pathlib import Path
import sqlite3
from threading import RLock
from typing import TYPE_CHECKING, Any, Iterable, Mapping
from uuid import uuid4

from app.tenders.corteris_filter import EvaluatedTender
from app.tenders.models import (
    TenderCustomer,
    TenderDocument,
    TenderMoney,
    TenderProcedureType,
    TenderSource,
    TenderStatus,
    UnifiedTender,
)

if TYPE_CHECKING:
    from app.tenders.search_profile_runner import TenderSearchProfileRun


@dataclass(frozen=True, slots=True)
class TenderRegistrySaveSummary:
    run_id: str
    inserted_count: int
    updated_count: int
    occurrence_count: int
    accepted_count: int
    rejected_count: int

    @property
    def saved_count(self) -> int:
        return self.inserted_count + self.updated_count


@dataclass(frozen=True, slots=True)
class TenderRegistryRecord:
    registry_key: str
    procurement_number: str
    identity_key: str
    source: str
    external_id: str
    title: str
    customer_name: str
    customer_inn: str
    region: str
    price_amount: Decimal | None
    currency: str
    status: str
    application_deadline: str
    source_url: str
    first_seen_at: str
    last_seen_at: str
    seen_count: int
    relevance_score: int
    relevance_grade: str
    last_accepted: bool
    archived: bool


@dataclass(frozen=True, slots=True)
class TenderSearchRunRecord:
    run_id: str
    profile_id: str
    profile_name: str
    executed_at: str
    saved_at: str
    raw_item_count: int
    merged_item_count: int
    duplicate_count: int
    accepted_count: int
    rejected_count: int
    provider_count: int
    elapsed_ms: int
    timezone_status: str = "unknown"


class TenderRegistrySort(StrEnum):
    RELEVANCE_DESC = "relevance_desc"
    DEADLINE_ASC = "deadline_asc"
    LAST_SEEN_DESC = "last_seen_desc"
    FIRST_SEEN_DESC = "first_seen_desc"
    PRICE_DESC = "price_desc"
    TITLE_ASC = "title_asc"


@dataclass(frozen=True, slots=True)
class TenderRegistryQuery:
    text: str = ""
    include_archived: bool = False
    archived_only: bool = False
    accepted_only: bool = False
    minimum_score: int = 0
    sort: TenderRegistrySort = TenderRegistrySort.RELEVANCE_DESC
    limit: int = 500
    offset: int = 0

    def __post_init__(self) -> None:
        if not 0 <= self.minimum_score <= 100:
            raise ValueError("minimum_score must be between 0 and 100")
        if not 1 <= self.limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        if self.offset < 0:
            raise ValueError("offset must be non-negative")


@dataclass(frozen=True, slots=True)
class TenderRegistryOccurrence:
    run_id: str
    profile_id: str
    profile_name: str
    executed_at: str
    accepted: bool
    relevance_score: int
    relevance_grade: str
    directions: tuple[str, ...]
    reasons: tuple[str, ...]
    rejection_reasons: tuple[str, ...]
    timezone_status: str = "unknown"


@dataclass(frozen=True, slots=True)
class TenderRegistryStatistics:
    total_count: int
    active_count: int
    archived_count: int
    accepted_count: int
    search_run_count: int


class TenderRegistryRepository:
    """Persist canonical tenders without creating duplicate rows."""

    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS tender_registry_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tender_records (
                    registry_key TEXT PRIMARY KEY,
                    procurement_number TEXT NOT NULL,
                    identity_key TEXT NOT NULL,
                    source TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    customer_name TEXT NOT NULL,
                    customer_inn TEXT NOT NULL DEFAULT '',
                    customer_kpp TEXT NOT NULL DEFAULT '',
                    customer_region TEXT NOT NULL DEFAULT '',
                    region TEXT NOT NULL DEFAULT '',
                    price_amount TEXT,
                    currency TEXT NOT NULL DEFAULT '',
                    includes_vat INTEGER,
                    status TEXT NOT NULL,
                    procedure_type TEXT NOT NULL,
                    law TEXT NOT NULL DEFAULT '',
                    published_at TEXT NOT NULL DEFAULT '',
                    application_deadline TEXT NOT NULL DEFAULT '',
                    execution_deadline TEXT NOT NULL DEFAULT '',
                    source_url TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    seen_count INTEGER NOT NULL DEFAULT 1,
                    last_relevance_score INTEGER NOT NULL DEFAULT 0,
                    last_relevance_grade TEXT NOT NULL DEFAULT 'excluded',
                    last_accepted INTEGER NOT NULL DEFAULT 0,
                    archived INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_tender_records_number
                    ON tender_records(procurement_number COLLATE NOCASE);
                CREATE INDEX IF NOT EXISTS idx_tender_records_deadline
                    ON tender_records(application_deadline);
                CREATE INDEX IF NOT EXISTS idx_tender_records_score
                    ON tender_records(last_relevance_score DESC);
                CREATE INDEX IF NOT EXISTS idx_tender_records_seen
                    ON tender_records(last_seen_at DESC);

                CREATE TABLE IF NOT EXISTS tender_search_runs (
                    run_id TEXT PRIMARY KEY,
                    profile_id TEXT NOT NULL,
                    profile_name TEXT NOT NULL,
                    executed_at TEXT NOT NULL,
                    saved_at TEXT NOT NULL,
                    raw_item_count INTEGER NOT NULL,
                    merged_item_count INTEGER NOT NULL,
                    duplicate_count INTEGER NOT NULL,
                    accepted_count INTEGER NOT NULL,
                    rejected_count INTEGER NOT NULL,
                    provider_count INTEGER NOT NULL,
                    completed_provider_count INTEGER NOT NULL,
                    elapsed_ms INTEGER NOT NULL,
                    provider_outcomes_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_tender_runs_profile
                    ON tender_search_runs(profile_id, executed_at DESC);

                CREATE TABLE IF NOT EXISTS tender_search_run_items (
                    run_id TEXT NOT NULL,
                    registry_key TEXT NOT NULL,
                    accepted INTEGER NOT NULL,
                    relevance_score INTEGER NOT NULL,
                    relevance_grade TEXT NOT NULL,
                    directions_json TEXT NOT NULL,
                    reasons_json TEXT NOT NULL,
                    rejection_reasons_json TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    PRIMARY KEY (run_id, registry_key),
                    FOREIGN KEY (run_id)
                        REFERENCES tender_search_runs(run_id)
                        ON DELETE CASCADE,
                    FOREIGN KEY (registry_key)
                        REFERENCES tender_records(registry_key)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_tender_run_items_registry
                    ON tender_search_run_items(registry_key);
                """
            )
            connection.execute(
                """
                INSERT INTO tender_registry_meta(key, value)
                VALUES('schema_version', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (str(self.SCHEMA_VERSION),),
            )

    def record_profile_run(
        self,
        run: "TenderSearchProfileRun",
        *,
        run_id: str | None = None,
        saved_at: datetime | None = None,
    ) -> TenderRegistrySaveSummary:
        """Save one profile run atomically and upsert tender rows."""

        self.initialize()
        effective_run_id = run_id or uuid4().hex
        saved_timestamp = _iso_timestamp(saved_at)
        executed_at = (
            _aware_utc_timestamp_text(run.executed_at) if run.executed_at else saved_timestamp
        )

        evaluated = _unique_evaluated(
            (
                *run.result.filter_result.accepted,
                *run.result.filter_result.rejected,
            )
        )

        inserted = 0
        updated = 0

        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            provider_result = run.result.provider_result
            filter_result = run.result.filter_result
            connection.execute(
                """
                INSERT INTO tender_search_runs(
                    run_id,
                    profile_id,
                    profile_name,
                    executed_at,
                    saved_at,
                    raw_item_count,
                    merged_item_count,
                    duplicate_count,
                    accepted_count,
                    rejected_count,
                    provider_count,
                    completed_provider_count,
                    elapsed_ms,
                    provider_outcomes_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    effective_run_id,
                    run.profile.id,
                    run.profile.name,
                    executed_at,
                    saved_timestamp,
                    provider_result.raw_item_count,
                    len(provider_result.items),
                    provider_result.duplicate_count,
                    filter_result.accepted_count,
                    filter_result.rejected_count,
                    provider_result.provider_count,
                    provider_result.completed_provider_count,
                    provider_result.elapsed_ms,
                    _json_dumps(
                        [
                            {
                                "provider_id": outcome.provider_id,
                                "display_name": outcome.display_name,
                                "status": outcome.status.value,
                                "elapsed_ms": outcome.elapsed_ms,
                                "item_count": outcome.item_count,
                                "warnings": list(outcome.warnings),
                                "error_type": outcome.error_type,
                                "error_message": outcome.error_message,
                            }
                            for outcome in provider_result.outcomes
                        ]
                    ),
                ),
            )

            for position, item in enumerate(evaluated):
                registry_key = tender_registry_key(item.tender)
                exists = connection.execute(
                    """
                    SELECT 1
                    FROM tender_records
                    WHERE registry_key = ?
                    """,
                    (registry_key,),
                ).fetchone()

                values = _record_values(
                    registry_key,
                    item,
                    first_seen_at=executed_at,
                    last_seen_at=executed_at,
                )

                if exists is None:
                    connection.execute(
                        """
                        INSERT INTO tender_records(
                            registry_key,
                            procurement_number,
                            identity_key,
                            source,
                            external_id,
                            title,
                            customer_name,
                            customer_inn,
                            customer_kpp,
                            customer_region,
                            region,
                            price_amount,
                            currency,
                            includes_vat,
                            status,
                            procedure_type,
                            law,
                            published_at,
                            application_deadline,
                            execution_deadline,
                            source_url,
                            payload_json,
                            first_seen_at,
                            last_seen_at,
                            seen_count,
                            last_relevance_score,
                            last_relevance_grade,
                            last_accepted,
                            archived
                        ) VALUES (
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, 0
                        )
                        """,
                        values,
                    )
                    inserted += 1
                else:
                    connection.execute(
                        """
                        UPDATE tender_records
                        SET procurement_number = ?,
                            identity_key = ?,
                            source = ?,
                            external_id = ?,
                            title = ?,
                            customer_name = ?,
                            customer_inn = ?,
                            customer_kpp = ?,
                            customer_region = ?,
                            region = ?,
                            price_amount = ?,
                            currency = ?,
                            includes_vat = ?,
                            status = ?,
                            procedure_type = ?,
                            law = ?,
                            published_at = ?,
                            application_deadline = ?,
                            execution_deadline = ?,
                            source_url = ?,
                            payload_json = ?,
                            last_seen_at = ?,
                            seen_count = seen_count + 1,
                            last_relevance_score = ?,
                            last_relevance_grade = ?,
                            last_accepted = ?
                        WHERE registry_key = ?
                        """,
                        (
                            *values[1:22],
                            executed_at,
                            values[24],
                            values[25],
                            values[26],
                            registry_key,
                        ),
                    )
                    updated += 1

                connection.execute(
                    """
                    INSERT INTO tender_search_run_items(
                        run_id,
                        registry_key,
                        accepted,
                        relevance_score,
                        relevance_grade,
                        directions_json,
                        reasons_json,
                        rejection_reasons_json,
                        position
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        effective_run_id,
                        registry_key,
                        int(item.accepted),
                        item.relevance.score,
                        item.relevance.grade.value,
                        _json_dumps([direction.value for direction in item.relevance.directions]),
                        _json_dumps(list(item.relevance.reasons)),
                        _json_dumps(list(item.rejection_reasons)),
                        position,
                    ),
                )

        return TenderRegistrySaveSummary(
            run_id=effective_run_id,
            inserted_count=inserted,
            updated_count=updated,
            occurrence_count=len(evaluated),
            accepted_count=run.result.filter_result.accepted_count,
            rejected_count=run.result.filter_result.rejected_count,
        )

    def count_tenders(
        self,
        *,
        include_archived: bool = False,
        accepted_only: bool = False,
    ) -> int:
        self.initialize()
        conditions: list[str] = []
        if not include_archived:
            conditions.append("archived = 0")
        if accepted_only:
            conditions.append("last_accepted = 1")
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM tender_records" + where_clause
            ).fetchone()
        return int(row["total"] if row is not None else 0)

    def list_tenders(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        include_archived: bool = False,
        accepted_only: bool = False,
    ) -> tuple[TenderRegistryRecord, ...]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        if offset < 0:
            raise ValueError("offset must be non-negative")

        self.initialize()
        conditions: list[str] = []
        parameters: list[object] = []
        if not include_archived:
            conditions.append("archived = 0")
        if accepted_only:
            conditions.append("last_accepted = 1")
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        parameters.extend((limit, offset))

        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM tender_records
                """
                + where_clause
                + """
                ORDER BY last_relevance_score DESC,
                         CASE WHEN application_deadline = '' THEN 1 ELSE 0 END,
                         application_deadline ASC,
                         last_seen_at DESC
                LIMIT ? OFFSET ?
                """,
                tuple(parameters),
            ).fetchall()
        return tuple(_row_to_tender_record(row) for row in rows)

    def get_by_procurement_number(
        self,
        procurement_number: str,
    ) -> TenderRegistryRecord | None:
        normalized = normalize_registry_component(procurement_number)
        if not normalized:
            return None
        self.initialize()
        registry_key = f"procurement:{normalized}"
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM tender_records
                WHERE registry_key = ?
                """,
                (registry_key,),
            ).fetchone()
        return _row_to_tender_record(row) if row is not None else None

    def list_search_runs(
        self,
        *,
        limit: int = 50,
    ) -> tuple[TenderSearchRunRecord, ...]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        self.initialize()
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT run_id,
                       profile_id,
                       profile_name,
                       executed_at,
                       saved_at,
                       raw_item_count,
                       merged_item_count,
                       duplicate_count,
                       accepted_count,
                       rejected_count,
                       provider_count,
                       elapsed_ms
                FROM tender_search_runs
                ORDER BY executed_at DESC, saved_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return tuple(
            TenderSearchRunRecord(
                run_id=str(row["run_id"]),
                profile_id=str(row["profile_id"]),
                profile_name=str(row["profile_name"]),
                executed_at=str(row["executed_at"]),
                saved_at=str(row["saved_at"]),
                raw_item_count=int(row["raw_item_count"]),
                merged_item_count=int(row["merged_item_count"]),
                duplicate_count=int(row["duplicate_count"]),
                accepted_count=int(row["accepted_count"]),
                rejected_count=int(row["rejected_count"]),
                provider_count=int(row["provider_count"]),
                elapsed_ms=int(row["elapsed_ms"]),
                timezone_status=legacy_timestamp_status(str(row["executed_at"])),
            )
            for row in rows
        )

    def run_item_count(self, run_id: str) -> int:
        self.initialize()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM tender_search_run_items
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
        return int(row["total"] if row is not None else 0)

    def search_tenders(
        self,
        query: TenderRegistryQuery | None = None,
    ) -> tuple[TenderRegistryRecord, ...]:
        """Return registry rows matching text, state and score filters."""

        effective = query or TenderRegistryQuery()
        self.initialize()
        conditions, parameters = _registry_query_conditions(effective)
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        order_clause = _registry_order_clause(effective.sort)
        parameters.extend((effective.limit, effective.offset))

        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM tender_records
                """
                + where_clause
                + " ORDER BY "
                + order_clause
                + " LIMIT ? OFFSET ?",
                tuple(parameters),
            ).fetchall()
        return tuple(_row_to_tender_record(row) for row in rows)

    def count_search_results(
        self,
        query: TenderRegistryQuery | None = None,
    ) -> int:
        effective = query or TenderRegistryQuery()
        self.initialize()
        conditions, parameters = _registry_query_conditions(effective)
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM tender_records" + where_clause,
                tuple(parameters),
            ).fetchone()
        return int(row["total"] if row is not None else 0)

    def get_record(
        self,
        registry_key: str,
    ) -> TenderRegistryRecord | None:
        normalized = registry_key.strip()
        if not normalized:
            return None
        self.initialize()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM tender_records
                WHERE registry_key = ?
                """,
                (normalized,),
            ).fetchone()
        return _row_to_tender_record(row) if row is not None else None

    def get_tender(
        self,
        registry_key: str,
    ) -> UnifiedTender | None:
        """Restore the canonical UnifiedTender payload for one registry row."""

        normalized = registry_key.strip()
        if not normalized:
            return None
        self.initialize()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json
                FROM tender_records
                WHERE registry_key = ?
                """,
                (normalized,),
            ).fetchone()
        if row is None:
            return None
        try:
            payload = json.loads(str(row["payload_json"]))
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        try:
            return _payload_to_tender(payload)
        except (KeyError, TypeError, ValueError):
            return None

    def list_tender_occurrences(
        self,
        registry_key: str,
        *,
        limit: int = 100,
    ) -> tuple[TenderRegistryOccurrence, ...]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        normalized = registry_key.strip()
        if not normalized:
            return ()

        self.initialize()
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT items.run_id,
                       runs.profile_id,
                       runs.profile_name,
                       runs.executed_at,
                       items.accepted,
                       items.relevance_score,
                       items.relevance_grade,
                       items.directions_json,
                       items.reasons_json,
                       items.rejection_reasons_json
                FROM tender_search_run_items AS items
                JOIN tender_search_runs AS runs
                  ON runs.run_id = items.run_id
                WHERE items.registry_key = ?
                ORDER BY runs.executed_at DESC,
                         runs.saved_at DESC
                LIMIT ?
                """,
                (normalized, limit),
            ).fetchall()

        return tuple(
            TenderRegistryOccurrence(
                run_id=str(row["run_id"]),
                profile_id=str(row["profile_id"]),
                profile_name=str(row["profile_name"]),
                executed_at=str(row["executed_at"]),
                accepted=bool(row["accepted"]),
                relevance_score=int(row["relevance_score"]),
                relevance_grade=str(row["relevance_grade"]),
                directions=_json_string_tuple(row["directions_json"]),
                reasons=_json_string_tuple(row["reasons_json"]),
                rejection_reasons=_json_string_tuple(row["rejection_reasons_json"]),
                timezone_status=legacy_timestamp_status(str(row["executed_at"])),
            )
            for row in rows
        )

    def statistics(self) -> TenderRegistryStatistics:
        self.initialize()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total_count,
                       SUM(CASE WHEN archived = 0 THEN 1 ELSE 0 END)
                           AS active_count,
                       SUM(CASE WHEN archived = 1 THEN 1 ELSE 0 END)
                           AS archived_count,
                       SUM(CASE WHEN last_accepted = 1 THEN 1 ELSE 0 END)
                           AS accepted_count
                FROM tender_records
                """
            ).fetchone()
            run_row = connection.execute(
                "SELECT COUNT(*) AS total FROM tender_search_runs"
            ).fetchone()

        return TenderRegistryStatistics(
            total_count=int(row["total_count"] or 0),
            active_count=int(row["active_count"] or 0),
            archived_count=int(row["archived_count"] or 0),
            accepted_count=int(row["accepted_count"] or 0),
            search_run_count=int(run_row["total"] or 0),
        )

    def set_archived(
        self,
        registry_key: str,
        archived: bool,
    ) -> bool:
        self.initialize()
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE tender_records
                SET archived = ?
                WHERE registry_key = ?
                """,
                (int(archived), registry_key),
            )
        return cursor.rowcount > 0

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            timeout=10.0,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.create_function(
            "CASEFOLD",
            1,
            lambda value: str(value or "").casefold(),
            deterministic=True,
        )
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection


def _registry_query_conditions(
    query: TenderRegistryQuery,
) -> tuple[list[str], list[object]]:
    conditions: list[str] = []
    parameters: list[object] = []

    if query.archived_only:
        conditions.append("archived = 1")
    elif not query.include_archived:
        conditions.append("archived = 0")

    if query.accepted_only:
        conditions.append("last_accepted = 1")

    if query.minimum_score:
        conditions.append("last_relevance_score >= ?")
        parameters.append(query.minimum_score)

    for term in (item for item in query.text.casefold().split() if item.strip()):
        conditions.append(
            """
            CASEFOLD(
                procurement_number || ' ' ||
                title || ' ' ||
                customer_name || ' ' ||
                customer_inn || ' ' ||
                region || ' ' ||
                law || ' ' ||
                source
            ) LIKE ?
            """
        )
        parameters.append(f"%{term}%")

    return conditions, parameters


def _registry_order_clause(sort: TenderRegistrySort) -> str:
    mapping = {
        TenderRegistrySort.RELEVANCE_DESC: (
            "last_relevance_score DESC, "
            "CASE WHEN application_deadline = '' THEN 1 ELSE 0 END, "
            "application_deadline ASC, last_seen_at DESC"
        ),
        TenderRegistrySort.DEADLINE_ASC: (
            "CASE WHEN application_deadline = '' THEN 1 ELSE 0 END, "
            "application_deadline ASC, last_relevance_score DESC"
        ),
        TenderRegistrySort.LAST_SEEN_DESC: ("last_seen_at DESC, last_relevance_score DESC"),
        TenderRegistrySort.FIRST_SEEN_DESC: ("first_seen_at DESC, last_relevance_score DESC"),
        TenderRegistrySort.PRICE_DESC: (
            "CASE WHEN price_amount IS NULL OR price_amount = '' "
            "THEN 1 ELSE 0 END, "
            "CAST(price_amount AS REAL) DESC, last_relevance_score DESC"
        ),
        TenderRegistrySort.TITLE_ASC: ("CASEFOLD(title) ASC, last_relevance_score DESC"),
    }
    return mapping[TenderRegistrySort(sort)]


def _json_string_tuple(value: object) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    try:
        payload = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return ()
    if not isinstance(payload, list):
        return ()
    return tuple(str(item) for item in payload)


def tender_registry_key(tender: UnifiedTender) -> str:
    procurement_number = normalize_registry_component(tender.procurement_number)
    if procurement_number:
        return f"procurement:{procurement_number}"
    return f"identity:{normalize_registry_component(tender.identity_key)}"


def normalize_registry_component(value: str) -> str:
    return "".join(
        character
        for character in value.strip().casefold()
        if character.isalnum() or character in {"-", "_", ".", ":"}
    )


def _unique_evaluated(
    items: Iterable[EvaluatedTender],
) -> tuple[EvaluatedTender, ...]:
    by_key: dict[str, EvaluatedTender] = {}
    order: list[str] = []
    for item in items:
        key = tender_registry_key(item.tender)
        current = by_key.get(key)
        if current is None:
            by_key[key] = item
            order.append(key)
            continue
        if _evaluated_priority(item) > _evaluated_priority(current):
            by_key[key] = item
    return tuple(by_key[key] for key in order)


def _evaluated_priority(item: EvaluatedTender) -> tuple[int, int]:
    return (int(item.accepted), item.relevance.score)


def _record_values(
    registry_key: str,
    item: EvaluatedTender,
    *,
    first_seen_at: str,
    last_seen_at: str,
) -> tuple[object, ...]:
    tender = item.tender
    price_amount = str(tender.price.amount) if tender.price is not None else None
    currency = tender.price.currency if tender.price is not None else ""
    includes_vat = (
        None
        if tender.price is None or tender.price.includes_vat is None
        else int(tender.price.includes_vat)
    )
    return (
        registry_key,
        tender.procurement_number.strip(),
        tender.identity_key,
        tender.source.value,
        tender.external_id,
        tender.title,
        tender.customer.name,
        tender.customer.inn,
        tender.customer.kpp,
        tender.customer.region,
        tender.region,
        price_amount,
        currency,
        includes_vat,
        tender.status.value,
        tender.procedure_type.value,
        tender.law,
        _optional_iso(tender.published_at),
        _optional_iso(tender.application_deadline),
        _optional_iso(tender.execution_deadline),
        tender.source_url,
        _json_dumps(_tender_payload(tender)),
        first_seen_at,
        last_seen_at,
        item.relevance.score,
        item.relevance.grade.value,
        int(item.accepted),
    )


def _tender_payload(tender: UnifiedTender) -> dict[str, Any]:
    return {
        "source": tender.source.value,
        "external_id": tender.external_id,
        "procurement_number": tender.procurement_number,
        "title": tender.title,
        "customer": {
            "name": tender.customer.name,
            "inn": tender.customer.inn,
            "kpp": tender.customer.kpp,
            "region": tender.customer.region,
            "address": tender.customer.address,
        },
        "source_url": tender.source_url,
        "published_at": _optional_iso(tender.published_at),
        "application_deadline": _optional_iso(tender.application_deadline),
        "execution_deadline": _optional_iso(tender.execution_deadline),
        "price": (
            {
                "amount": str(tender.price.amount),
                "currency": tender.price.currency,
                "includes_vat": tender.price.includes_vat,
            }
            if tender.price is not None
            else None
        ),
        "status": tender.status.value,
        "procedure_type": tender.procedure_type.value,
        "law": tender.law,
        "region": tender.region,
        "description": tender.description,
        "classification_codes": list(tender.classification_codes),
        "tags": list(tender.tags),
        "documents": [
            {
                "id": document.id,
                "name": document.name,
                "url": document.url,
                "mime_type": document.mime_type,
                "size_bytes": document.size_bytes,
                "published_at": _optional_iso(document.published_at),
                "checksum_sha256": document.checksum_sha256,
            }
            for document in tender.documents
        ],
        "raw_metadata": _json_safe(tender.raw_metadata),
    }


def _payload_to_tender(payload: Mapping[str, Any]) -> UnifiedTender:
    customer_payload = payload.get("customer") or {}
    if not isinstance(customer_payload, Mapping):
        customer_payload = {}

    price_payload = payload.get("price")
    price = None
    if isinstance(price_payload, Mapping):
        price = TenderMoney.from_value(
            price_payload.get("amount", "0"),
            currency=str(price_payload.get("currency", "RUB")),
            includes_vat=price_payload.get("includes_vat"),
        )

    documents: list[TenderDocument] = []
    for item in payload.get("documents", ()) or ():
        if not isinstance(item, Mapping):
            continue
        published_raw = str(item.get("published_at", "") or "")
        documents.append(
            TenderDocument(
                id=str(item.get("id", "")),
                name=str(item.get("name", "")),
                url=str(item.get("url", "")),
                mime_type=str(item.get("mime_type", "")),
                size_bytes=(
                    int(item["size_bytes"]) if item.get("size_bytes") is not None else None
                ),
                published_at=(datetime.fromisoformat(published_raw) if published_raw else None),
                checksum_sha256=str(item.get("checksum_sha256", "")),
            )
        )

    published_at = str(payload.get("published_at", "") or "")
    deadline = str(payload.get("application_deadline", "") or "")
    execution = str(payload.get("execution_deadline", "") or "")

    return UnifiedTender(
        source=TenderSource(str(payload["source"])),
        external_id=str(payload["external_id"]),
        procurement_number=str(payload["procurement_number"]),
        title=str(payload["title"]),
        customer=TenderCustomer(
            name=str(customer_payload.get("name", "")),
            inn=str(customer_payload.get("inn", "")),
            kpp=str(customer_payload.get("kpp", "")),
            region=str(customer_payload.get("region", "")),
            address=str(customer_payload.get("address", "")),
        ),
        source_url=str(payload["source_url"]),
        published_at=(datetime.fromisoformat(published_at) if published_at else None),
        application_deadline=(datetime.fromisoformat(deadline) if deadline else None),
        execution_deadline=(date.fromisoformat(execution) if execution else None),
        price=price,
        status=TenderStatus(str(payload.get("status", "unknown"))),
        procedure_type=TenderProcedureType(str(payload.get("procedure_type", "unknown"))),
        law=str(payload.get("law", "")),
        region=str(payload.get("region", "")),
        description=str(payload.get("description", "")),
        classification_codes=tuple(str(item) for item in payload.get("classification_codes", ())),
        tags=tuple(str(item) for item in payload.get("tags", ())),
        documents=tuple(documents),
        raw_metadata=(
            payload.get("raw_metadata", {})
            if isinstance(payload.get("raw_metadata", {}), Mapping)
            else {}
        ),
    )


def _row_to_tender_record(row: sqlite3.Row) -> TenderRegistryRecord:
    amount_raw = row["price_amount"]
    return TenderRegistryRecord(
        registry_key=str(row["registry_key"]),
        procurement_number=str(row["procurement_number"]),
        identity_key=str(row["identity_key"]),
        source=str(row["source"]),
        external_id=str(row["external_id"]),
        title=str(row["title"]),
        customer_name=str(row["customer_name"]),
        customer_inn=str(row["customer_inn"]),
        region=str(row["region"] or row["customer_region"]),
        price_amount=(Decimal(str(amount_raw)) if amount_raw not in (None, "") else None),
        currency=str(row["currency"]),
        status=str(row["status"]),
        application_deadline=str(row["application_deadline"]),
        source_url=str(row["source_url"]),
        first_seen_at=str(row["first_seen_at"]),
        last_seen_at=str(row["last_seen_at"]),
        seen_count=int(row["seen_count"]),
        relevance_score=int(row["last_relevance_score"]),
        relevance_grade=str(row["last_relevance_grade"]),
        last_accepted=bool(row["last_accepted"]),
        archived=bool(row["archived"]),
    )


def _optional_iso(value: datetime | date | None) -> str:
    if value is None:
        return ""
    return value.isoformat()


def _iso_timestamp(value: datetime | None) -> str:
    moment = value or datetime.now(timezone.utc)
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("run timestamp must be timezone-aware")
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def _aware_utc_timestamp_text(value: str) -> str:
    try:
        moment = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("run timestamp must be a valid timezone-aware datetime") from exc
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("run timestamp must be timezone-aware")
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def legacy_timestamp_status(value: str) -> str:
    try:
        moment = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return "invalid"
    if moment.tzinfo is None or moment.utcoffset() is None:
        return "unknown"
    return "explicit"


def _json_dumps(value: object) -> str:
    return json.dumps(
        _json_safe(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _json_safe(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item) for item in value]
    return str(value)


__all__ = [
    "TenderRegistryOccurrence",
    "TenderRegistryQuery",
    "TenderRegistryRecord",
    "TenderRegistryRepository",
    "TenderRegistrySaveSummary",
    "TenderRegistrySort",
    "TenderRegistryStatistics",
    "TenderSearchRunRecord",
    "normalize_registry_component",
    "legacy_timestamp_status",
    "tender_registry_key",
]
