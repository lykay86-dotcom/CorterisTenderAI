"""Transactional persistence for collector runs, aliases and changes."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
from threading import RLock
from typing import Iterable, Mapping, Sequence
from uuid import uuid4

from app.tenders.collector.change_tracker import (
    TenderChange,
    TenderChangeTracker,
)
from app.tenders.collector.checkpoint import CollectorCheckpoint
from app.tenders.collector.codec import (
    query_to_payload,
    stable_json,
    tender_from_payload,
    tender_to_payload,
)
from app.tenders.collector.participation_score import (
    CorterisParticipationScore,
    ParticipationRecommendation,
)
from app.tenders.collector.models import (
    CollectionPersistenceSummary,
    CollectionRunRecord,
    CollectionRunStatus,
    CollectorSourceReference,
    DeduplicationResult,
    NormalizedTender,
    TenderObservationStatus,
)
from app.tenders.collector.schema import CollectorSchemaMigrator
from app.tenders.models import UnifiedTender
from app.tenders.provider_base import TenderSearchQuery
from app.tenders.tender_registry import TenderRegistryRepository


class CollectorStateRepository:
    """Store collector state in the existing ``tender_registry.sqlite3``."""

    def __init__(
        self,
        path: str | Path,
        *,
        change_tracker: TenderChangeTracker | None = None,
        migrator: CollectorSchemaMigrator | None = None,
    ) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.change_tracker = change_tracker or TenderChangeTracker()
        self.migrator = migrator or CollectorSchemaMigrator()
        self._lock = RLock()

    def initialize(self) -> None:
        TenderRegistryRepository(self.path).initialize()
        with self._lock, self._connect() as connection:
            self.migrator.migrate(connection)

    def start_run(
        self,
        query: TenderSearchQuery,
        *,
        provider_ids: Sequence[str] = (),
        run_id: str | None = None,
        started_at: str | None = None,
    ) -> str:
        self.initialize()
        effective_id = run_id or uuid4().hex
        moment = started_at or _utc_now()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO collector_runs(
                    run_id,
                    status,
                    started_at,
                    query_json,
                    requested_provider_ids_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    effective_id,
                    CollectionRunStatus.RUNNING.value,
                    moment,
                    stable_json(query_to_payload(query)),
                    stable_json(list(provider_ids)),
                ),
            )
        return effective_id

    def save_batch(
        self,
        run_id: str,
        result: DeduplicationResult,
        *,
        observed_at: str | None = None,
        rankings: Mapping[
            str,
            CorterisParticipationScore,
        ] | None = None,
    ) -> CollectionPersistenceSummary:
        self.initialize()
        moment = observed_at or _utc_now()
        new_count = 0
        unchanged_count = 0
        changed_count = 0
        change_count = 0
        version_count = 0
        alias_conflicts = 0
        ranked_count = 0
        recommended_count = 0
        manual_review_count = 0
        possible_count = 0
        not_recommended_count = 0
        rankings = rankings or {}

        groups_by_key = {
            group.item.canonical_key: group
            for group in result.groups
        }

        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                for item in result.items:
                    registry_key, conflicts = self._resolve_registry_key(
                        connection,
                        item,
                    )
                    alias_conflicts += conflicts
                    old_tender = self._load_existing_tender(
                        connection,
                        registry_key,
                    )
                    change_set = self.change_tracker.compare(
                        old_tender,
                        item.tender,
                        detected_at=moment,
                    )
                    self._upsert_tender_record(
                        connection,
                        registry_key,
                        item,
                        observed_at=moment,
                        is_new=old_tender is None,
                    )
                    alias_conflicts += self._upsert_aliases(
                        connection,
                        registry_key,
                        item,
                        observed_at=moment,
                    )
                    self._upsert_sources(
                        connection,
                        registry_key,
                        item,
                        observed_at=moment,
                    )
                    inserted_version = self._insert_version(
                        connection,
                        registry_key,
                        item,
                        observed_at=moment,
                    )
                    version_count += int(inserted_version)
                    self._insert_changes(
                        connection,
                        run_id,
                        registry_key,
                        change_set.changes,
                    )
                    change_count += len(change_set.changes)

                    if change_set.status == TenderObservationStatus.NEW:
                        new_count += 1
                    elif (
                        change_set.status
                        == TenderObservationStatus.UNCHANGED
                    ):
                        unchanged_count += 1
                    else:
                        changed_count += 1

                    group = groups_by_key.get(item.canonical_key)
                    source_count = (
                        len(group.source_items) if group is not None else 1
                    )
                    duplicate_count = (
                        group.duplicate_count if group is not None else 0
                    )
                    ranking = rankings.get(item.canonical_key)
                    if ranking is not None:
                        self._upsert_score(
                            connection,
                            registry_key,
                            ranking,
                            run_id=run_id,
                            source="collector",
                        )
                        ranked_count += 1
                        if (
                            ranking.recommendation
                            == ParticipationRecommendation.RECOMMENDED
                        ):
                            recommended_count += 1
                        elif (
                            ranking.recommendation
                            == ParticipationRecommendation.MANUAL_REVIEW
                        ):
                            manual_review_count += 1
                        elif (
                            ranking.recommendation
                            == ParticipationRecommendation.POSSIBLE_WITH_CONDITIONS
                        ):
                            possible_count += 1
                        else:
                            not_recommended_count += 1

                    connection.execute(
                        """
                        INSERT INTO collector_run_items(
                            run_id,
                            registry_key,
                            observation_status,
                            content_hash,
                            source_count,
                            duplicate_count
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(run_id, registry_key) DO UPDATE SET
                            observation_status=excluded.observation_status,
                            content_hash=excluded.content_hash,
                            source_count=excluded.source_count,
                            duplicate_count=excluded.duplicate_count
                        """,
                        (
                            run_id,
                            registry_key,
                            change_set.status.value,
                            item.content_hash,
                            source_count,
                            duplicate_count,
                        ),
                    )

                connection.execute(
                    """
                    UPDATE collector_runs
                    SET raw_count = ?,
                        merged_count = ?,
                        duplicate_count = ?,
                        new_count = ?,
                        unchanged_count = ?,
                        changed_count = ?
                    WHERE run_id = ?
                    """,
                    (
                        result.raw_count,
                        result.merged_count,
                        result.duplicate_count,
                        new_count,
                        unchanged_count,
                        changed_count,
                        run_id,
                    ),
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise

        return CollectionPersistenceSummary(
            run_id=run_id,
            new_count=new_count,
            unchanged_count=unchanged_count,
            changed_count=changed_count,
            merged_count=result.merged_count,
            duplicate_count=result.duplicate_count,
            change_count=change_count,
            version_count=version_count,
            alias_conflict_count=alias_conflicts,
            ranked_count=ranked_count,
            recommended_count=recommended_count,
            manual_review_count=manual_review_count,
            possible_count=possible_count,
            not_recommended_count=not_recommended_count,
        )

    def complete_run(
        self,
        run_id: str,
        *,
        status: CollectionRunStatus,
        provider_outcomes: Iterable[object] = (),
        completed_at: str | None = None,
        elapsed_ms: int = 0,
        error: BaseException | None = None,
    ) -> None:
        self.initialize()
        outcomes = tuple(provider_outcomes)
        successful = sum(
            bool(getattr(outcome, "successful", False))
            for outcome in outcomes
        )
        failed = len(outcomes) - successful
        moment = completed_at or _utc_now()

        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                for outcome in outcomes:
                    connection.execute(
                        """
                        INSERT INTO collector_run_providers(
                            run_id,
                            provider_id,
                            display_name,
                            status,
                            item_count,
                            elapsed_ms,
                            warnings_json,
                            error_type,
                            error_message
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(run_id, provider_id) DO UPDATE SET
                            display_name=excluded.display_name,
                            status=excluded.status,
                            item_count=excluded.item_count,
                            elapsed_ms=excluded.elapsed_ms,
                            warnings_json=excluded.warnings_json,
                            error_type=excluded.error_type,
                            error_message=excluded.error_message
                        """,
                        (
                            run_id,
                            str(getattr(outcome, "provider_id", "")),
                            str(getattr(outcome, "display_name", "")),
                            _enum_value(getattr(outcome, "status", "")),
                            int(getattr(outcome, "item_count", 0)),
                            int(getattr(outcome, "elapsed_ms", 0)),
                            stable_json(
                                list(getattr(outcome, "warnings", ()))
                            ),
                            str(getattr(outcome, "error_type", "")),
                            str(getattr(outcome, "error_message", "")),
                        ),
                    )

                connection.execute(
                    """
                    UPDATE collector_runs
                    SET status = ?,
                        completed_at = ?,
                        provider_count = ?,
                        successful_provider_count = ?,
                        failed_provider_count = ?,
                        elapsed_ms = ?,
                        error_type = ?,
                        error_message = ?
                    WHERE run_id = ?
                    """,
                    (
                        status.value,
                        moment,
                        len(outcomes),
                        successful,
                        failed,
                        max(0, int(elapsed_ms)),
                        type(error).__name__ if error is not None else "",
                        str(error) if error is not None else "",
                        run_id,
                    ),
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise

    def get_run(self, run_id: str) -> CollectionRunRecord | None:
        self.initialize()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM collector_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return _row_to_run(row) if row is not None else None

    def list_changes(
        self,
        registry_key: str,
        *,
        limit: int = 100,
    ) -> tuple[TenderChange, ...]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        self.initialize()
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM collector_tender_changes
                WHERE registry_key = ?
                ORDER BY detected_at DESC, change_id DESC
                LIMIT ?
                """,
                (registry_key, limit),
            ).fetchall()
        from app.tenders.collector.change_tracker import TenderChangeType

        return tuple(
            TenderChange(
                change_id=str(row["change_id"]),
                change_type=TenderChangeType(str(row["change_type"])),
                field_name=str(row["field_name"]),
                old_value=str(row["old_value"]),
                new_value=str(row["new_value"]),
                detected_at=str(row["detected_at"]),
                source=str(row["source"]),
            )
            for row in rows
        )

    def list_sources(
        self,
        registry_key: str,
    ) -> tuple[CollectorSourceReference, ...]:
        self.initialize()
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM collector_tender_sources
                WHERE registry_key = ?
                ORDER BY source, external_id
                """,
                (registry_key,),
            ).fetchall()
        return tuple(
            CollectorSourceReference(
                registry_key=str(row["registry_key"]),
                source=str(row["source"]),
                external_id=str(row["external_id"]),
                source_url=str(row["source_url"]),
                first_seen_at=str(row["first_seen_at"]),
                last_seen_at=str(row["last_seen_at"]),
                content_hash=str(row["content_hash"]),
                active=bool(row["active"]),
            )
            for row in rows
        )

    def save_score(
        self,
        registry_key: str,
        score: CorterisParticipationScore,
        *,
        run_id: str = "",
        source: str = "manual",
    ) -> CorterisParticipationScore:
        """Persist a recalculated score and update registry summary fields."""

        normalized = registry_key.strip()
        if not normalized:
            raise ValueError("registry_key must not be empty")
        self.initialize()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                exists = connection.execute(
                    """
                    SELECT 1 FROM tender_records
                    WHERE registry_key = ?
                    """,
                    (normalized,),
                ).fetchone()
                if exists is None:
                    raise KeyError(normalized)
                self._upsert_score(
                    connection,
                    normalized,
                    score,
                    run_id=run_id,
                    source=source,
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
        return score

    def get_latest_score(
        self,
        registry_key: str,
    ) -> CorterisParticipationScore | None:
        normalized = registry_key.strip()
        if not normalized:
            return None
        self.initialize()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json
                FROM collector_tender_scores
                WHERE registry_key = ?
                ORDER BY scored_at DESC, rowid DESC
                LIMIT 1
                """,
                (normalized,),
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(str(row["payload_json"]))
        if not isinstance(payload, Mapping):
            return None
        return CorterisParticipationScore.from_payload(payload)

    def list_run_scores(
        self,
        run_id: str,
    ) -> tuple[CorterisParticipationScore, ...]:
        self.initialize()
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json
                FROM collector_tender_scores
                WHERE run_id = ?
                ORDER BY total_score DESC, scored_at DESC
                """,
                (run_id.strip(),),
            ).fetchall()
        result = []
        for row in rows:
            payload = json.loads(str(row["payload_json"]))
            if isinstance(payload, Mapping):
                result.append(
                    CorterisParticipationScore.from_payload(payload)
                )
        return tuple(result)

    @staticmethod
    def _upsert_score(
        connection: sqlite3.Connection,
        registry_key: str,
        score: CorterisParticipationScore,
        *,
        run_id: str,
        source: str,
    ) -> None:
        payload = stable_json(score.to_payload())
        connection.execute(
            """
            INSERT INTO collector_tender_scores(
                score_id,
                run_id,
                registry_key,
                source,
                scored_at,
                total_score,
                recommendation,
                hard_excluded,
                profile_version,
                input_fingerprint,
                payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(
                registry_key,
                source,
                input_fingerprint
            ) DO UPDATE SET
                run_id=excluded.run_id,
                scored_at=excluded.scored_at,
                total_score=excluded.total_score,
                recommendation=excluded.recommendation,
                hard_excluded=excluded.hard_excluded,
                profile_version=excluded.profile_version,
                payload_json=excluded.payload_json
            """,
            (
                uuid4().hex,
                run_id.strip(),
                registry_key,
                source.strip() or "manual",
                score.scored_at,
                score.total_score,
                score.recommendation.value,
                int(score.hard_excluded),
                score.profile_version,
                score.input_fingerprint,
                payload,
            ),
        )
        connection.execute(
            """
            UPDATE tender_records
            SET last_relevance_score = ?,
                last_relevance_grade = ?,
                last_accepted = ?
            WHERE registry_key = ?
            """,
            (
                score.total_score,
                score.recommendation.value,
                int(score.accepted_for_registry),
                registry_key,
            ),
        )

    def save_checkpoint(
        self,
        checkpoint: CollectorCheckpoint,
        *,
        updated_at: str | None = None,
    ) -> CollectorCheckpoint:
        self.initialize()
        moment = updated_at or checkpoint.updated_at or _utc_now()
        stored = CollectorCheckpoint(
            provider_id=checkpoint.provider_id.strip().casefold(),
            scope_key=checkpoint.scope_key.strip().casefold(),
            cursor=checkpoint.cursor,
            watermark=checkpoint.watermark,
            state=dict(checkpoint.state),
            updated_at=moment,
        )
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO collector_checkpoints(
                    provider_id,
                    scope_key,
                    cursor,
                    watermark,
                    state_json,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider_id, scope_key) DO UPDATE SET
                    cursor=excluded.cursor,
                    watermark=excluded.watermark,
                    state_json=excluded.state_json,
                    updated_at=excluded.updated_at
                """,
                (
                    stored.provider_id,
                    stored.scope_key,
                    stored.cursor,
                    stored.watermark,
                    stable_json(stored.state),
                    stored.updated_at,
                ),
            )
        return stored

    def get_checkpoint(
        self,
        provider_id: str,
        *,
        scope_key: str = "default",
    ) -> CollectorCheckpoint | None:
        self.initialize()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM collector_checkpoints
                WHERE provider_id = ? AND scope_key = ?
                """,
                (
                    provider_id.strip().casefold(),
                    scope_key.strip().casefold(),
                ),
            ).fetchone()
        if row is None:
            return None
        state = json.loads(str(row["state_json"] or "{}"))
        if not isinstance(state, Mapping):
            state = {}
        return CollectorCheckpoint(
            provider_id=str(row["provider_id"]),
            scope_key=str(row["scope_key"]),
            cursor=str(row["cursor"]),
            watermark=str(row["watermark"]),
            state=dict(state),
            updated_at=str(row["updated_at"]),
        )

    def _resolve_registry_key(
        self,
        connection: sqlite3.Connection,
        item: NormalizedTender,
    ) -> tuple[str, int]:
        placeholders = ",".join("?" for _ in item.aliases)
        rows = connection.execute(
            f"""
            SELECT alias_key, registry_key
            FROM collector_tender_aliases
            WHERE alias_key IN ({placeholders})
            """,
            tuple(alias.key for alias in item.aliases),
        ).fetchall()
        mapped = {str(row["registry_key"]) for row in rows}
        if not mapped:
            existing = connection.execute(
                """
                SELECT registry_key
                FROM tender_records
                WHERE registry_key = ?
                   OR procurement_number = ? COLLATE NOCASE
                   OR identity_key = ?
                ORDER BY
                    CASE
                        WHEN registry_key = ? THEN 0
                        WHEN identity_key = ? THEN 1
                        ELSE 2
                    END
                LIMIT 1
                """,
                (
                    item.canonical_key,
                    item.tender.procurement_number.strip(),
                    item.tender.identity_key,
                    item.canonical_key,
                    item.tender.identity_key,
                ),
            ).fetchone()
            if existing is not None:
                return str(existing["registry_key"]), 0
            return item.canonical_key, 0
        if len(mapped) == 1:
            return next(iter(mapped)), 0
        if item.canonical_key in mapped:
            return item.canonical_key, len(mapped) - 1
        return sorted(mapped)[0], len(mapped) - 1

    @staticmethod
    def _load_existing_tender(
        connection: sqlite3.Connection,
        registry_key: str,
    ) -> UnifiedTender | None:
        row = connection.execute(
            """
            SELECT payload_json
            FROM tender_records
            WHERE registry_key = ?
            """,
            (registry_key,),
        ).fetchone()
        if row is None:
            return None
        payload = json.loads(str(row["payload_json"]))
        if not isinstance(payload, Mapping):
            return None
        return tender_from_payload(payload)

    @staticmethod
    def _upsert_tender_record(
        connection: sqlite3.Connection,
        registry_key: str,
        item: NormalizedTender,
        *,
        observed_at: str,
        is_new: bool,
    ) -> None:
        tender = item.tender
        payload = stable_json(tender_to_payload(tender))
        price_amount = (
            str(tender.price.amount) if tender.price is not None else None
        )
        currency = tender.price.currency if tender.price is not None else ""
        includes_vat = (
            None
            if tender.price is None or tender.price.includes_vat is None
            else int(tender.price.includes_vat)
        )
        values = (
            registry_key,
            tender.procurement_number,
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
            _iso(tender.published_at),
            _iso(tender.application_deadline),
            _iso(tender.execution_deadline),
            tender.source_url,
            payload,
            observed_at,
            observed_at,
        )
        if is_new:
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
                    last_seen_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?
                )
                """,
                values,
            )
            return

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
                seen_count = seen_count + 1
            WHERE registry_key = ?
            """,
            (
                tender.procurement_number,
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
                _iso(tender.published_at),
                _iso(tender.application_deadline),
                _iso(tender.execution_deadline),
                tender.source_url,
                payload,
                observed_at,
                registry_key,
            ),
        )

    @staticmethod
    def _upsert_aliases(
        connection: sqlite3.Connection,
        registry_key: str,
        item: NormalizedTender,
        *,
        observed_at: str,
    ) -> int:
        conflicts = 0
        for alias in item.aliases:
            existing = connection.execute(
                """
                SELECT registry_key
                FROM collector_tender_aliases
                WHERE alias_key = ?
                """,
                (alias.key,),
            ).fetchone()
            if (
                existing is not None
                and str(existing["registry_key"]) != registry_key
            ):
                conflicts += 1
                continue
            connection.execute(
                """
                INSERT INTO collector_tender_aliases(
                    alias_key,
                    alias_type,
                    registry_key,
                    strength,
                    first_seen_at,
                    last_seen_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(alias_key) DO UPDATE SET
                    last_seen_at=excluded.last_seen_at,
                    strength=MAX(
                        collector_tender_aliases.strength,
                        excluded.strength
                    )
                """,
                (
                    alias.key,
                    alias.alias_type.value,
                    registry_key,
                    alias.strength,
                    observed_at,
                    observed_at,
                ),
            )
        return conflicts

    @staticmethod
    def _upsert_sources(
        connection: sqlite3.Connection,
        registry_key: str,
        item: NormalizedTender,
        *,
        observed_at: str,
    ) -> None:
        sources = _source_payloads(item)
        for source in sources:
            connection.execute(
                """
                INSERT INTO collector_tender_sources(
                    registry_key,
                    source,
                    external_id,
                    procurement_number,
                    source_url,
                    content_hash,
                    first_seen_at,
                    last_seen_at,
                    active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(registry_key, source, external_id) DO UPDATE SET
                    procurement_number=excluded.procurement_number,
                    source_url=excluded.source_url,
                    content_hash=excluded.content_hash,
                    last_seen_at=excluded.last_seen_at,
                    active=1
                """,
                (
                    registry_key,
                    source["source"],
                    source["external_id"],
                    source["procurement_number"],
                    source["source_url"],
                    item.content_hash,
                    observed_at,
                    observed_at,
                ),
            )

    @staticmethod
    def _insert_version(
        connection: sqlite3.Connection,
        registry_key: str,
        item: NormalizedTender,
        *,
        observed_at: str,
    ) -> bool:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO collector_tender_versions(
                version_id,
                registry_key,
                content_hash,
                observed_at,
                source,
                payload_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                uuid4().hex,
                registry_key,
                item.content_hash,
                observed_at,
                item.tender.source.value,
                stable_json(tender_to_payload(item.tender)),
            ),
        )
        return cursor.rowcount > 0

    @staticmethod
    def _insert_changes(
        connection: sqlite3.Connection,
        run_id: str,
        registry_key: str,
        changes: Iterable[TenderChange],
    ) -> None:
        connection.executemany(
            """
            INSERT INTO collector_tender_changes(
                change_id,
                run_id,
                registry_key,
                detected_at,
                source,
                change_type,
                field_name,
                old_value,
                new_value
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    change.change_id,
                    run_id,
                    registry_key,
                    change.detected_at,
                    change.source,
                    change.change_type.value,
                    change.field_name,
                    change.old_value,
                    change.new_value,
                )
                for change in changes
            ),
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            timeout=10.0,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection


def _source_payloads(item: NormalizedTender) -> tuple[dict[str, str], ...]:
    raw_sources = item.tender.raw_metadata.get("collector_sources")
    result: list[dict[str, str]] = []
    if isinstance(raw_sources, (list, tuple)):
        for raw in raw_sources:
            if not isinstance(raw, Mapping):
                continue
            source = str(raw.get("source", "")).strip()
            external_id = str(raw.get("external_id", "")).strip()
            source_url = str(raw.get("source_url", "")).strip()
            if not source or not external_id or not source_url:
                continue
            result.append(
                {
                    "source": source,
                    "external_id": external_id,
                    "procurement_number": str(
                        raw.get("procurement_number", "")
                    ),
                    "source_url": source_url,
                }
            )
    if not result:
        result.append(
            {
                "source": item.tender.source.value,
                "external_id": item.tender.external_id,
                "procurement_number": item.tender.procurement_number,
                "source_url": item.tender.source_url,
            }
        )
    unique: dict[tuple[str, str], dict[str, str]] = {}
    for source in result:
        unique[(source["source"], source["external_id"])] = source
    return tuple(unique.values())


def _row_to_run(row: sqlite3.Row) -> CollectionRunRecord:
    providers = json.loads(str(row["requested_provider_ids_json"] or "[]"))
    if not isinstance(providers, list):
        providers = []
    return CollectionRunRecord(
        run_id=str(row["run_id"]),
        status=CollectionRunStatus(str(row["status"])),
        started_at=str(row["started_at"]),
        completed_at=str(row["completed_at"]),
        query_json=str(row["query_json"]),
        requested_provider_ids=tuple(str(item) for item in providers),
        raw_count=int(row["raw_count"]),
        merged_count=int(row["merged_count"]),
        duplicate_count=int(row["duplicate_count"]),
        new_count=int(row["new_count"]),
        unchanged_count=int(row["unchanged_count"]),
        changed_count=int(row["changed_count"]),
        provider_count=int(row["provider_count"]),
        successful_provider_count=int(row["successful_provider_count"]),
        failed_provider_count=int(row["failed_provider_count"]),
        elapsed_ms=int(row["elapsed_ms"]),
        error_type=str(row["error_type"]),
        error_message=str(row["error_message"]),
    )


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))


def _iso(value: object) -> str:
    return value.isoformat() if value is not None else ""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


__all__ = ["CollectorStateRepository"]
