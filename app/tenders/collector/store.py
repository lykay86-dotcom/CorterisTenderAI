"""Transactional persistence for collector runs, aliases and changes."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
from threading import RLock
from typing import TYPE_CHECKING, Iterable, Mapping, Sequence
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
from app.tenders.collector.freshness import (
    DeadlineTimezoneStatus,
    FreshnessBatchResult,
    TenderFreshnessState,
    TenderFreshnessStatus,
)
from app.tenders.collector.stop_factor import StopFactorAssessment
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
from app.tenders.collector.verification import (
    FieldCandidate,
    FieldConflict,
    FieldConflictType,
    FieldProvenance,
    FieldResolutionAction,
    FieldResolutionRecord,
    SourceTrustLevel,
    TenderVerificationHistory,
    TenderVerificationResult,
    TenderVerificationState,
    TenderVerificationStatus,
    VerificationBatchResult,
    apply_selected_field_values,
    determine_verification_status,
    field_candidate_priority,
)
from app.tenders.models import UnifiedTender
from app.tenders.provider_base import TenderSearchQuery
from app.tenders.tender_registry import TenderRegistryRepository

if TYPE_CHECKING:
    from app.tenders.participation_decision import ParticipationDecision
    from app.tenders.tender_summary import TenderSummary


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
        verification: VerificationBatchResult | None = None,
        freshness: FreshnessBatchResult | None = None,
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
        verification_run_id = ""
        verified_field_count = 0
        conflict_count = 0
        unresolved_conflict_count = 0
        verification_incomplete_count = 0
        stale_count = 0
        due_soon_count = 0
        expired_count = 0
        reverification_due_count = 0
        rankings = rankings or {}
        verification_by_key = (
            verification.by_canonical_key
            if verification is not None
            else {}
        )
        freshness_by_key = (
            freshness.by_canonical_key
            if freshness is not None
            else {}
        )

        groups_by_key = {
            group.item.canonical_key: group
            for group in result.groups
        }

        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                if verification is not None:
                    verification_run_id = uuid4().hex
                    connection.execute(
                        """
                        INSERT INTO collector_verification_runs(
                            verification_run_id,
                            collector_run_id,
                            started_at,
                            completed_at,
                            status,
                            item_count,
                            verified_field_count,
                            conflict_count,
                            unresolved_conflict_count
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            verification_run_id,
                            run_id,
                            verification.verified_at,
                            verification.verified_at,
                            "completed",
                            len(verification.items),
                            verification.verified_field_count,
                            verification.conflict_count,
                            verification.unresolved_conflict_count,
                        ),
                    )
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
                    verification_item = verification_by_key.get(
                        item.canonical_key
                    )
                    if (
                        verification_item is not None
                        and verification_run_id
                    ):
                        self._persist_verification(
                            connection,
                            verification_run_id,
                            registry_key,
                            verification_item,
                        )
                        verified_field_count += (
                            verification_item.verified_field_count
                        )
                        conflict_count += (
                            verification_item.conflict_count
                        )
                        unresolved_conflict_count += (
                            verification_item.unresolved_conflict_count
                        )
                        verification_incomplete_count += int(
                            verification_item.status
                            in {
                                TenderVerificationStatus.INCOMPLETE,
                                TenderVerificationStatus.MISSING,
                                TenderVerificationStatus.CONFLICT,
                            }
                        )
                    freshness_item = freshness_by_key.get(
                        item.canonical_key
                    )
                    if freshness_item is not None:
                        self._persist_freshness(
                            connection,
                            registry_key,
                            freshness_item,
                            verification_run_id=verification_run_id,
                        )
                        stale_count += int(freshness_item.is_stale)
                        due_soon_count += int(
                            freshness_item.status
                            == TenderFreshnessStatus.DUE_SOON
                        )
                        expired_count += int(
                            freshness_item.deadline_expired
                        )
                        reverification_due_count += int(
                            freshness_item.requires_reverification
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
            verification_run_id=verification_run_id,
            verified_field_count=verified_field_count,
            conflict_count=conflict_count,
            unresolved_conflict_count=unresolved_conflict_count,
            verification_incomplete_count=(
                verification_incomplete_count
            ),
            stale_count=stale_count,
            due_soon_count=due_soon_count,
            expired_count=expired_count,
            reverification_due_count=reverification_due_count,
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

    def get_verification_history(
        self,
        item: NormalizedTender,
    ) -> TenderVerificationHistory | None:
        """Load the latest selected field evidence for downgrade protection."""

        self.initialize()
        with self._lock, self._connect() as connection:
            registry_key, _ = self._resolve_registry_key(
                connection,
                item,
            )
            tender = self._load_existing_tender(
                connection,
                registry_key,
            )
            if tender is None:
                return None
            rows = connection.execute(
                """
                SELECT values_table.*,
                       CASE
                           WHEN manual.candidate_id = values_table.candidate_id
                           THEN 1 ELSE 0
                       END AS manual_selected
                FROM collector_tender_field_values AS values_table
                LEFT JOIN collector_tender_field_manual_selections AS manual
                  ON manual.registry_key = values_table.registry_key
                 AND manual.field_name = values_table.field_name
                WHERE values_table.registry_key = ?
                  AND (
                      values_table.selected = 1
                      OR manual.candidate_id = values_table.candidate_id
                  )
                ORDER BY manual_selected DESC, values_table.rowid DESC
                """,
                (registry_key,),
            ).fetchall()
        selected: dict[str, FieldCandidate] = {}
        for row in rows:
            field_name = str(row["field_name"])
            if field_name in selected:
                continue
            try:
                payload = json.loads(str(row["value_json"]))
            except json.JSONDecodeError:
                payload = str(row["value_json"])
            selected[field_name] = FieldCandidate(
                candidate_id=str(row["candidate_id"]),
                field_name=field_name,
                value=payload,
                normalized_value=str(row["normalized_value"]),
                value_hash=str(row["value_hash"]),
                source_id=str(row["source_id"]),
                source_url=str(row["source_url"]),
                retrieved_at=str(row["retrieved_at"]),
                trust_level=SourceTrustLevel(
                    int(row["trust_level"])
                ),
                official=bool(row["official"]),
                verified=bool(row["verified"]),
                confidence=float(row["confidence"]),
                selected=True,
                historical=True,
                manual_override=bool(row["manual_selected"]),
            )
        if not selected:
            return None
        return TenderVerificationHistory(
            registry_key=registry_key,
            tender=tender,
            selected_candidates=selected,
        )

    def get_verification_state(
        self,
        registry_key: str,
    ) -> TenderVerificationState | None:
        normalized = registry_key.strip()
        if not normalized:
            return None
        self.initialize()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM collector_tender_verification_state
                WHERE registry_key = ?
                """,
                (normalized,),
            ).fetchone()
        return _row_to_verification_state(row) if row is not None else None

    def list_verification_states(
        self,
        registry_keys: Sequence[str],
    ) -> Mapping[str, TenderVerificationState]:
        """Load verification badges for a registry page in one query."""

        normalized = tuple(
            dict.fromkeys(
                item.strip() for item in registry_keys if item.strip()
            )
        )
        if not normalized:
            return {}
        self.initialize()
        placeholders = ",".join("?" for _ in normalized)
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM collector_tender_verification_state
                WHERE registry_key IN ({placeholders})
                """,
                normalized,
            ).fetchall()
        return {
            str(row["registry_key"]): _row_to_verification_state(row)
            for row in rows
        }

    def get_freshness_state(
        self,
        registry_key: str,
        *,
        now: str | None = None,
    ) -> TenderFreshnessState | None:
        normalized = registry_key.strip()
        if not normalized:
            return None
        self.initialize()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM collector_tender_freshness_state
                WHERE registry_key = ?
                """,
                (normalized,),
            ).fetchone()
        if row is None:
            return None
        return _effective_freshness_state(
            _row_to_freshness_state(row),
            now=now,
        )

    def list_freshness_states(
        self,
        registry_keys: Sequence[str],
        *,
        now: str | None = None,
    ) -> Mapping[str, TenderFreshnessState]:
        normalized = tuple(
            dict.fromkeys(
                item.strip() for item in registry_keys if item.strip()
            )
        )
        if not normalized:
            return {}
        self.initialize()
        placeholders = ",".join("?" for _ in normalized)
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM collector_tender_freshness_state
                WHERE registry_key IN ({placeholders})
                """,
                normalized,
            ).fetchall()
        return {
            str(row["registry_key"]): _effective_freshness_state(
                _row_to_freshness_state(row),
                now=now,
            )
            for row in rows
        }

    def list_due_reverification(
        self,
        *,
        now: str | None = None,
        limit: int = 500,
    ) -> tuple[TenderFreshnessState, ...]:
        if not 1 <= limit <= 5000:
            raise ValueError("limit must be between 1 and 5000")
        moment = now or _utc_now()
        self.initialize()
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM collector_tender_freshness_state
                WHERE deadline_expired = 0
                  AND (
                      is_stale = 1
                      OR (
                          verification_due_at <> ''
                          AND verification_due_at <= ?
                      )
                  )
                ORDER BY
                    CASE WHEN is_stale = 1 THEN 0 ELSE 1 END,
                    verification_due_at ASC,
                    rowid ASC
                LIMIT ?
                """,
                (moment, limit),
            ).fetchall()
        return tuple(_row_to_freshness_state(row) for row in rows)

    def list_field_provenance(
        self,
        registry_key: str,
        *,
        field_name: str = "",
    ) -> tuple[FieldProvenance, ...]:
        self.initialize()
        sql = """
            SELECT *
            FROM collector_tender_field_provenance
            WHERE registry_key = ?
        """
        params: list[object] = [registry_key.strip()]
        if field_name.strip():
            sql += " AND field_name = ?"
            params.append(field_name.strip())
        sql += " ORDER BY retrieved_at DESC, rowid DESC"
        with self._lock, self._connect() as connection:
            rows = connection.execute(sql, tuple(params)).fetchall()
        return tuple(
            FieldProvenance(
                field_name=str(row["field_name"]),
                value_hash=str(row["value_hash"]),
                source_id=str(row["source_id"]),
                source_url=str(row["source_url"]),
                retrieved_at=str(row["retrieved_at"]),
                verified=bool(row["verified"]),
                official=bool(row["official"]),
                confidence=float(row["confidence"]),
                trust_level=SourceTrustLevel(
                    int(row["trust_level"])
                ),
                candidate_id=str(row["candidate_id"]),
            )
            for row in rows
        )

    def list_field_conflicts(
        self,
        registry_key: str,
        *,
        unresolved_only: bool = False,
    ) -> tuple[FieldConflict, ...]:
        self.initialize()
        sql = """
            SELECT conflicts.*,
                   CASE
                       WHEN manual.candidate_id IS NOT NULL THEN 1
                       ELSE 0
                   END AS manually_resolved
            FROM collector_tender_field_conflicts AS conflicts
            LEFT JOIN collector_tender_field_manual_selections AS manual
              ON manual.registry_key = conflicts.registry_key
             AND manual.field_name = conflicts.field_name
            WHERE conflicts.registry_key = ?
        """
        if unresolved_only:
            sql += (
                " AND conflicts.unresolved = 1"
                " AND manual.candidate_id IS NULL"
            )
        sql += " ORDER BY conflicts.detected_at DESC, conflicts.rowid DESC"
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                sql,
                (registry_key.strip(),),
            ).fetchall()
        result: list[FieldConflict] = []
        for row in rows:
            try:
                ids = json.loads(str(row["candidate_ids_json"]))
            except json.JSONDecodeError:
                ids = []
            if not isinstance(ids, list) or len(ids) < 2:
                continue
            result.append(
                FieldConflict(
                    conflict_id=str(row["conflict_id"]),
                    field_name=str(row["field_name"]),
                    conflict_type=FieldConflictType(
                        str(row["conflict_type"])
                    ),
                    candidate_ids=tuple(str(item) for item in ids),
                    selected_candidate_id=str(
                        row["selected_candidate_id"]
                    ),
                    detected_at=str(row["detected_at"]),
                    critical=bool(row["critical"]),
                    unresolved=(
                        bool(row["unresolved"])
                        and not bool(row["manually_resolved"])
                    ),
                    message=str(row["message"]),
                )
            )
        return tuple(result)

    def list_field_candidates(
        self,
        registry_key: str,
        *,
        field_name: str = "",
        current_only: bool = True,
    ) -> tuple[FieldCandidate, ...]:
        """Return field candidates with current/manual selection markers."""

        normalized = registry_key.strip()
        if not normalized:
            return ()
        self.initialize()
        sql = """
            SELECT values_table.*,
                   CASE
                       WHEN manual.candidate_id = values_table.candidate_id
                       THEN 1 ELSE 0
                   END AS manual_selected
            FROM collector_tender_field_values AS values_table
            LEFT JOIN collector_tender_field_manual_selections AS manual
              ON manual.registry_key = values_table.registry_key
             AND manual.field_name = values_table.field_name
            WHERE values_table.registry_key = ?
        """
        params: list[object] = [normalized]
        if current_only:
            sql += """
                AND values_table.verification_run_id = (
                    SELECT verification_run_id
                    FROM collector_tender_verification_state
                    WHERE registry_key = ?
                )
            """
            params.append(normalized)
        if field_name.strip():
            sql += " AND values_table.field_name = ?"
            params.append(field_name.strip())
        sql += """
            ORDER BY values_table.field_name,
                     manual_selected DESC,
                     values_table.selected DESC,
                     values_table.trust_level DESC,
                     values_table.confidence DESC,
                     values_table.retrieved_at DESC
        """
        with self._lock, self._connect() as connection:
            rows = connection.execute(sql, tuple(params)).fetchall()
        return tuple(_row_to_field_candidate(row) for row in rows)

    def list_field_resolutions(
        self,
        registry_key: str,
        *,
        limit: int = 200,
    ) -> tuple[FieldResolutionRecord, ...]:
        if not 1 <= limit <= 2000:
            raise ValueError("limit must be between 1 and 2000")
        normalized = registry_key.strip()
        if not normalized:
            return ()
        self.initialize()
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM collector_tender_field_resolution_history
                WHERE registry_key = ?
                ORDER BY resolved_at DESC, rowid DESC
                LIMIT ?
                """,
                (normalized, limit),
            ).fetchall()
        return tuple(_row_to_field_resolution(row) for row in rows)

    def resolve_field_candidate(
        self,
        registry_key: str,
        field_name: str,
        candidate_id: str,
        *,
        resolved_by: str = "user",
        note: str = "",
        resolved_at: str | None = None,
    ) -> FieldResolutionRecord:
        """Select one candidate manually and write an immutable audit row."""

        normalized_key = registry_key.strip()
        normalized_field = field_name.strip()
        normalized_candidate = candidate_id.strip()
        if not normalized_key or not normalized_field or not normalized_candidate:
            raise ValueError(
                "registry_key, field_name and candidate_id are required"
            )
        moment = resolved_at or _utc_now()
        actor = resolved_by.strip() or "user"
        safe_note = note.strip()[:4000]
        self.initialize()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                state = connection.execute(
                    """
                    SELECT verification_run_id
                    FROM collector_tender_verification_state
                    WHERE registry_key = ?
                    """,
                    (normalized_key,),
                ).fetchone()
                if state is None:
                    raise KeyError(normalized_key)
                verification_run_id = str(state["verification_run_id"])
                row = connection.execute(
                    """
                    SELECT *
                    FROM collector_tender_field_values
                    WHERE candidate_id = ?
                      AND registry_key = ?
                      AND field_name = ?
                      AND verification_run_id = ?
                    """,
                    (
                        normalized_candidate,
                        normalized_key,
                        normalized_field,
                        verification_run_id,
                    ),
                ).fetchone()
                if row is None:
                    raise KeyError(normalized_candidate)
                previous = connection.execute(
                    """
                    SELECT candidate_id
                    FROM collector_tender_field_values
                    WHERE registry_key = ?
                      AND field_name = ?
                      AND verification_run_id = ?
                      AND selected = 1
                    ORDER BY rowid DESC
                    LIMIT 1
                    """,
                    (normalized_key, normalized_field, verification_run_id),
                ).fetchone()
                previous_id = (
                    str(previous["candidate_id"]) if previous is not None else ""
                )
                connection.execute(
                    """
                    UPDATE collector_tender_field_values
                    SET selected = CASE WHEN candidate_id = ? THEN 1 ELSE 0 END
                    WHERE registry_key = ?
                      AND field_name = ?
                      AND verification_run_id = ?
                    """,
                    (
                        normalized_candidate,
                        normalized_key,
                        normalized_field,
                        verification_run_id,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO collector_tender_field_manual_selections(
                        registry_key, field_name, candidate_id, selected_at,
                        selected_by, note
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(registry_key, field_name) DO UPDATE SET
                        candidate_id=excluded.candidate_id,
                        selected_at=excluded.selected_at,
                        selected_by=excluded.selected_by,
                        note=excluded.note
                    """,
                    (
                        normalized_key,
                        normalized_field,
                        normalized_candidate,
                        moment,
                        actor,
                        safe_note,
                    ),
                )
                conflict = connection.execute(
                    """
                    SELECT conflict_id
                    FROM collector_tender_field_conflicts
                    WHERE registry_key = ?
                      AND field_name = ?
                      AND verification_run_id = ?
                    ORDER BY detected_at DESC, rowid DESC
                    LIMIT 1
                    """,
                    (normalized_key, normalized_field, verification_run_id),
                ).fetchone()
                conflict_id = (
                    str(conflict["conflict_id"]) if conflict is not None else ""
                )
                connection.execute(
                    """
                    UPDATE collector_tender_field_conflicts
                    SET selected_candidate_id = ?
                    WHERE registry_key = ?
                      AND field_name = ?
                      AND verification_run_id = ?
                    """,
                    (
                        normalized_candidate,
                        normalized_key,
                        normalized_field,
                        verification_run_id,
                    ),
                )
                candidate = _row_to_field_candidate(row)
                resolution = FieldResolutionRecord(
                    resolution_id=uuid4().hex,
                    registry_key=normalized_key,
                    field_name=normalized_field,
                    action=FieldResolutionAction.SELECTED,
                    previous_candidate_id=previous_id,
                    selected_candidate_id=normalized_candidate,
                    selected_value=candidate.value_payload(),
                    selected_source_id=candidate.source_id,
                    resolved_at=moment,
                    resolved_by=actor,
                    note=safe_note,
                    conflict_id=conflict_id,
                )
                self._insert_resolution_history(connection, resolution)
                self._apply_manual_candidate_to_record(
                    connection,
                    normalized_key,
                    candidate.with_selected(True),
                )
                self._recalculate_verification_state(
                    connection,
                    normalized_key,
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
        return resolution

    def clear_manual_field_resolution(
        self,
        registry_key: str,
        field_name: str,
        *,
        resolved_by: str = "user",
        note: str = "",
        resolved_at: str | None = None,
    ) -> FieldResolutionRecord | None:
        """Remove a manual override and restore automatic source priority."""

        normalized_key = registry_key.strip()
        normalized_field = field_name.strip()
        if not normalized_key or not normalized_field:
            raise ValueError("registry_key and field_name are required")
        moment = resolved_at or _utc_now()
        actor = resolved_by.strip() or "user"
        safe_note = note.strip()[:4000]
        self.initialize()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                manual = connection.execute(
                    """
                    SELECT *
                    FROM collector_tender_field_manual_selections
                    WHERE registry_key = ? AND field_name = ?
                    """,
                    (normalized_key, normalized_field),
                ).fetchone()
                if manual is None:
                    connection.execute("COMMIT")
                    return None
                state = connection.execute(
                    """
                    SELECT verification_run_id
                    FROM collector_tender_verification_state
                    WHERE registry_key = ?
                    """,
                    (normalized_key,),
                ).fetchone()
                if state is None:
                    raise KeyError(normalized_key)
                verification_run_id = str(state["verification_run_id"])
                rows = connection.execute(
                    """
                    SELECT values_table.*, 0 AS manual_selected
                    FROM collector_tender_field_values AS values_table
                    WHERE registry_key = ?
                      AND field_name = ?
                      AND verification_run_id = ?
                    """,
                    (normalized_key, normalized_field, verification_run_id),
                ).fetchall()
                if not rows:
                    raise KeyError(normalized_field)
                candidates = tuple(_row_to_field_candidate(row) for row in rows)
                automatic = max(candidates, key=field_candidate_priority)
                previous_id = str(manual["candidate_id"])
                connection.execute(
                    """
                    DELETE FROM collector_tender_field_manual_selections
                    WHERE registry_key = ? AND field_name = ?
                    """,
                    (normalized_key, normalized_field),
                )
                connection.execute(
                    """
                    UPDATE collector_tender_field_values
                    SET selected = CASE WHEN candidate_id = ? THEN 1 ELSE 0 END
                    WHERE registry_key = ?
                      AND field_name = ?
                      AND verification_run_id = ?
                    """,
                    (
                        automatic.candidate_id,
                        normalized_key,
                        normalized_field,
                        verification_run_id,
                    ),
                )
                connection.execute(
                    """
                    UPDATE collector_tender_field_conflicts
                    SET selected_candidate_id = ?
                    WHERE registry_key = ?
                      AND field_name = ?
                      AND verification_run_id = ?
                    """,
                    (
                        automatic.candidate_id,
                        normalized_key,
                        normalized_field,
                        verification_run_id,
                    ),
                )
                resolution = FieldResolutionRecord(
                    resolution_id=uuid4().hex,
                    registry_key=normalized_key,
                    field_name=normalized_field,
                    action=FieldResolutionAction.CLEARED,
                    previous_candidate_id=previous_id,
                    selected_candidate_id=automatic.candidate_id,
                    selected_value=automatic.value_payload(),
                    selected_source_id=automatic.source_id,
                    resolved_at=moment,
                    resolved_by=actor,
                    note=safe_note,
                )
                self._insert_resolution_history(connection, resolution)
                self._apply_manual_candidate_to_record(
                    connection,
                    normalized_key,
                    automatic.with_selected(True),
                )
                self._recalculate_verification_state(
                    connection,
                    normalized_key,
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
        return resolution

    @staticmethod
    def _insert_resolution_history(
        connection: sqlite3.Connection,
        resolution: FieldResolutionRecord,
    ) -> None:
        connection.execute(
            """
            INSERT INTO collector_tender_field_resolution_history(
                resolution_id, registry_key, field_name, action, conflict_id,
                previous_candidate_id, selected_candidate_id,
                selected_value_json, selected_source_id, resolved_at,
                resolved_by, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resolution.resolution_id,
                resolution.registry_key,
                resolution.field_name,
                resolution.action.value,
                resolution.conflict_id,
                resolution.previous_candidate_id,
                resolution.selected_candidate_id,
                stable_json(resolution.selected_value),
                resolution.selected_source_id,
                resolution.resolved_at,
                resolution.resolved_by,
                resolution.note,
            ),
        )

    @staticmethod
    def _apply_manual_candidate_to_record(
        connection: sqlite3.Connection,
        registry_key: str,
        candidate: FieldCandidate,
    ) -> None:
        tender = CollectorStateRepository._load_existing_tender(
            connection,
            registry_key,
        )
        if tender is None:
            raise KeyError(registry_key)
        updated = apply_selected_field_values(
            tender,
            {candidate.field_name: candidate},
        )
        payload = stable_json(tender_to_payload(updated))
        price_amount = (
            str(updated.price.amount) if updated.price is not None else None
        )
        currency = updated.price.currency if updated.price is not None else ""
        includes_vat = (
            None
            if updated.price is None or updated.price.includes_vat is None
            else int(updated.price.includes_vat)
        )
        connection.execute(
            """
            UPDATE tender_records
            SET procurement_number = ?,
                customer_name = ?,
                customer_inn = ?,
                price_amount = ?,
                currency = ?,
                includes_vat = ?,
                status = ?,
                law = ?,
                application_deadline = ?,
                source_url = ?,
                payload_json = ?
            WHERE registry_key = ?
            """,
            (
                updated.procurement_number,
                updated.customer.name,
                updated.customer.inn,
                price_amount,
                currency,
                includes_vat,
                updated.status.value,
                updated.law,
                _iso(updated.application_deadline),
                updated.source_url,
                payload,
                registry_key,
            ),
        )

    @staticmethod
    def _recalculate_verification_state(
        connection: sqlite3.Connection,
        registry_key: str,
    ) -> None:
        state = connection.execute(
            """
            SELECT *
            FROM collector_tender_verification_state
            WHERE registry_key = ?
            """,
            (registry_key,),
        ).fetchone()
        if state is None:
            return
        run_id = str(state["verification_run_id"])
        rows = connection.execute(
            """
            SELECT values_table.*,
                   CASE
                       WHEN manual.candidate_id = values_table.candidate_id
                       THEN 1 ELSE 0
                   END AS manual_selected
            FROM collector_tender_field_values AS values_table
            LEFT JOIN collector_tender_field_manual_selections AS manual
              ON manual.registry_key = values_table.registry_key
             AND manual.field_name = values_table.field_name
            WHERE values_table.registry_key = ?
              AND values_table.verification_run_id = ?
              AND values_table.selected = 1
            """,
            (registry_key, run_id),
        ).fetchall()
        selected = tuple(_row_to_field_candidate(row) for row in rows)
        try:
            missing_raw = json.loads(str(state["missing_fields_json"] or "[]"))
        except json.JSONDecodeError:
            missing_raw = []
        missing = (
            tuple(str(item) for item in missing_raw)
            if isinstance(missing_raw, list)
            else ()
        )
        unresolved = int(
            connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM collector_tender_field_conflicts AS conflicts
                LEFT JOIN collector_tender_field_manual_selections AS manual
                  ON manual.registry_key = conflicts.registry_key
                 AND manual.field_name = conflicts.field_name
                WHERE conflicts.registry_key = ?
                  AND conflicts.verification_run_id = ?
                  AND conflicts.unresolved = 1
                  AND manual.candidate_id IS NULL
                """,
                (registry_key, run_id),
            ).fetchone()["total"]
        )
        conflict_count = int(
            connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM collector_tender_field_conflicts
                WHERE registry_key = ? AND verification_run_id = ?
                """,
                (registry_key, run_id),
            ).fetchone()["total"]
        )
        status = determine_verification_status(
            selected,
            missing_fields=missing,
            unresolved_conflict=bool(unresolved),
        )
        connection.execute(
            """
            UPDATE collector_tender_verification_state
            SET status = ?,
                verified_field_count = ?,
                official_field_count = ?,
                conflict_count = ?,
                unresolved_conflict_count = ?,
                minimum_confidence = ?
            WHERE registry_key = ?
            """,
            (
                status.value,
                sum(item.verified for item in selected),
                sum(item.official for item in selected),
                conflict_count,
                unresolved,
                min((item.confidence for item in selected), default=0.0),
                registry_key,
            ),
        )

    @staticmethod
    def _persist_verification(
        connection: sqlite3.Connection,
        verification_run_id: str,
        registry_key: str,
        verification: TenderVerificationResult,
    ) -> None:
        candidate_ids: dict[str, str] = {}
        for candidate in verification.candidates:
            storage_id = _verification_storage_id(
                verification_run_id,
                candidate.candidate_id,
            )
            candidate_ids[candidate.candidate_id] = storage_id
            connection.execute(
                """
                INSERT INTO collector_tender_field_values(
                    candidate_id,
                    verification_run_id,
                    registry_key,
                    field_name,
                    value_json,
                    normalized_value,
                    value_hash,
                    selected,
                    historical,
                    trust_level,
                    confidence,
                    official,
                    verified,
                    source_id,
                    source_url,
                    retrieved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    storage_id,
                    verification_run_id,
                    registry_key,
                    candidate.field_name,
                    stable_json(candidate.value_payload()),
                    candidate.normalized_value,
                    candidate.value_hash,
                    int(candidate.selected),
                    int(candidate.historical),
                    int(candidate.trust_level),
                    candidate.confidence,
                    int(candidate.official),
                    int(candidate.verified),
                    candidate.source_id,
                    candidate.source_url,
                    candidate.retrieved_at,
                ),
            )
            connection.execute(
                """
                INSERT INTO collector_tender_field_provenance(
                    provenance_id,
                    candidate_id,
                    verification_run_id,
                    registry_key,
                    field_name,
                    value_hash,
                    source_id,
                    source_url,
                    retrieved_at,
                    verified,
                    official,
                    confidence,
                    trust_level
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _verification_storage_id(
                        verification_run_id,
                        f"provenance:{candidate.candidate_id}",
                    ),
                    storage_id,
                    verification_run_id,
                    registry_key,
                    candidate.field_name,
                    candidate.value_hash,
                    candidate.source_id,
                    candidate.source_url,
                    candidate.retrieved_at,
                    int(candidate.verified),
                    int(candidate.official),
                    candidate.confidence,
                    int(candidate.trust_level),
                ),
            )

        for candidate in verification.candidates:
            if not candidate.selected or not candidate.manual_override:
                continue
            storage_id = candidate_ids.get(candidate.candidate_id)
            if not storage_id:
                continue
            connection.execute(
                """
                UPDATE collector_tender_field_manual_selections
                SET candidate_id = ?
                WHERE registry_key = ? AND field_name = ?
                """,
                (storage_id, registry_key, candidate.field_name),
            )

        for conflict in verification.conflicts:
            storage_ids = tuple(
                candidate_ids[item]
                for item in conflict.candidate_ids
                if item in candidate_ids
            )
            selected_id = candidate_ids.get(
                conflict.selected_candidate_id,
                "",
            )
            if len(storage_ids) < 2 or not selected_id:
                continue
            connection.execute(
                """
                INSERT INTO collector_tender_field_conflicts(
                    conflict_id,
                    verification_run_id,
                    registry_key,
                    field_name,
                    conflict_type,
                    candidate_ids_json,
                    selected_candidate_id,
                    detected_at,
                    critical,
                    unresolved,
                    message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _verification_storage_id(
                        verification_run_id,
                        conflict.conflict_id,
                    ),
                    verification_run_id,
                    registry_key,
                    conflict.field_name,
                    conflict.conflict_type.value,
                    stable_json(list(storage_ids)),
                    selected_id,
                    conflict.detected_at,
                    int(conflict.critical),
                    int(conflict.unresolved),
                    conflict.message,
                ),
            )

        connection.execute(
            """
            INSERT INTO collector_tender_verification_state(
                registry_key,
                verification_run_id,
                status,
                last_verified_at,
                critical_field_count,
                verified_field_count,
                official_field_count,
                missing_fields_json,
                conflict_count,
                unresolved_conflict_count,
                minimum_confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(registry_key) DO UPDATE SET
                verification_run_id=excluded.verification_run_id,
                status=excluded.status,
                last_verified_at=excluded.last_verified_at,
                critical_field_count=excluded.critical_field_count,
                verified_field_count=excluded.verified_field_count,
                official_field_count=excluded.official_field_count,
                missing_fields_json=excluded.missing_fields_json,
                conflict_count=excluded.conflict_count,
                unresolved_conflict_count=(
                    excluded.unresolved_conflict_count
                ),
                minimum_confidence=excluded.minimum_confidence
            """,
            (
                registry_key,
                verification_run_id,
                verification.status.value,
                verification.verified_at,
                verification.critical_field_count,
                verification.verified_field_count,
                verification.official_field_count,
                stable_json(list(verification.missing_fields)),
                verification.conflict_count,
                verification.unresolved_conflict_count,
                verification.minimum_confidence,
            ),
        )

    def _persist_freshness(
        self,
        connection: sqlite3.Connection,
        registry_key: str,
        freshness: TenderFreshnessState,
        *,
        verification_run_id: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO collector_tender_freshness_state(
                registry_key,
                verification_run_id,
                status,
                last_verified_at,
                verification_due_at,
                is_stale,
                stale_reason,
                deadline_original,
                source_timezone,
                timezone_status,
                deadline_utc,
                user_timezone,
                deadline_user_local,
                seconds_remaining,
                recheck_interval_minutes,
                deadline_expired,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(registry_key) DO UPDATE SET
                verification_run_id=excluded.verification_run_id,
                status=excluded.status,
                last_verified_at=excluded.last_verified_at,
                verification_due_at=excluded.verification_due_at,
                is_stale=excluded.is_stale,
                stale_reason=excluded.stale_reason,
                deadline_original=excluded.deadline_original,
                source_timezone=excluded.source_timezone,
                timezone_status=excluded.timezone_status,
                deadline_utc=excluded.deadline_utc,
                user_timezone=excluded.user_timezone,
                deadline_user_local=excluded.deadline_user_local,
                seconds_remaining=excluded.seconds_remaining,
                recheck_interval_minutes=excluded.recheck_interval_minutes,
                deadline_expired=excluded.deadline_expired,
                updated_at=excluded.updated_at
            """,
            (
                registry_key,
                verification_run_id,
                freshness.status.value,
                freshness.last_verified_at,
                freshness.verification_due_at,
                int(freshness.is_stale),
                freshness.stale_reason,
                freshness.deadline_original,
                freshness.source_timezone,
                freshness.timezone_status.value,
                freshness.deadline_utc,
                freshness.user_timezone,
                freshness.deadline_user_local,
                freshness.seconds_remaining,
                freshness.recheck_interval_minutes,
                int(freshness.deadline_expired),
                freshness.updated_at,
            ),
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

    def save_participation_decision(
        self,
        decision: "ParticipationDecision",
    ) -> "ParticipationDecision":
        """Persist one RM-107 decision in the existing registry database."""
        self.initialize()
        payload = stable_json(decision.to_payload())
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO collector_participation_decisions(
                    decision_id, registry_key, recommendation, confidence,
                    summary, policy_version, decided_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision.decision_id,
                    decision.registry_key,
                    decision.recommendation.value,
                    decision.confidence,
                    decision.summary,
                    decision.policy_version,
                    decision.decided_at,
                    payload,
                ),
            )
        return decision

    def get_latest_participation_decision_payload(
        self,
        registry_key: str,
    ) -> Mapping[str, object] | None:
        normalized = registry_key.strip()
        if not normalized:
            return None
        self.initialize()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json
                FROM collector_participation_decisions
                WHERE registry_key = ?
                ORDER BY decided_at DESC, rowid DESC
                LIMIT 1
                """,
                (normalized,),
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(str(row["payload_json"]))
        return dict(payload) if isinstance(payload, Mapping) else None

    def save_tender_summary(self, summary: "TenderSummary") -> None:
        self.initialize()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO collector_tender_summaries(
                    summary_id, registry_key, source, generated_at, payload_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    uuid4().hex,
                    summary.registry_key,
                    summary.source.value,
                    summary.generated_at,
                    stable_json(summary.to_payload()),
                ),
            )

    def get_latest_tender_summary_payload(
        self,
        registry_key: str,
    ) -> Mapping[str, object] | None:
        normalized = registry_key.strip()
        if not normalized:
            return None
        self.initialize()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json
                FROM collector_tender_summaries
                WHERE registry_key = ?
                ORDER BY generated_at DESC, rowid DESC
                LIMIT 1
                """,
                (normalized,),
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(str(row["payload_json"]))
        return dict(payload) if isinstance(payload, Mapping) else None

    def get_latest_stop_factor_assessment(
        self,
        registry_key: str,
    ) -> StopFactorAssessment | None:
        normalized = registry_key.strip()
        if not normalized:
            return None
        self.initialize()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json
                FROM collector_stop_factor_assessments
                WHERE registry_key = ?
                ORDER BY evaluated_at DESC, rowid DESC
                LIMIT 1
                """,
                (normalized,),
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(str(row["payload_json"]))
        return (
            StopFactorAssessment.from_payload(dict(payload))
            if isinstance(payload, Mapping)
            else None
        )

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
        if score.stop_factor_assessment is not None:
            CollectorStateRepository._upsert_stop_factor_assessment(
                connection,
                registry_key,
                score.stop_factor_assessment,
                run_id=run_id,
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

    @staticmethod
    def _upsert_stop_factor_assessment(
        connection: sqlite3.Connection,
        registry_key: str,
        assessment: StopFactorAssessment,
        *,
        run_id: str,
    ) -> None:
        assessment_id = uuid4().hex
        existing = connection.execute(
            """
            SELECT assessment_id
            FROM collector_stop_factor_assessments
            WHERE registry_key = ? AND input_fingerprint = ?
            """,
            (registry_key, assessment.input_fingerprint),
        ).fetchone()
        if existing is not None:
            assessment_id = str(existing["assessment_id"])
        connection.execute(
            """
            INSERT INTO collector_stop_factor_assessments(
                assessment_id, run_id, registry_key, status,
                evaluated_at, input_fingerprint, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(registry_key, input_fingerprint) DO UPDATE SET
                run_id=excluded.run_id,
                status=excluded.status,
                evaluated_at=excluded.evaluated_at,
                payload_json=excluded.payload_json
            """,
            (
                assessment_id,
                run_id.strip(),
                registry_key,
                assessment.status.value,
                assessment.evaluated_at,
                assessment.input_fingerprint,
                stable_json(assessment.to_payload()),
            ),
        )
        connection.execute(
            "DELETE FROM collector_stop_factors WHERE assessment_id = ?",
            (assessment_id,),
        )
        for factor in assessment.factors:
            evidence = factor.evidence
            connection.execute(
                """
                INSERT INTO collector_stop_factors(
                    factor_id, assessment_id, registry_key, kind, status,
                    title, description, criticality, document_name,
                    page_reference, section_name, quote_fragment,
                    confidence, remediation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    factor.factor_id,
                    assessment_id,
                    registry_key,
                    factor.kind.value,
                    factor.status.value,
                    factor.title,
                    factor.description,
                    factor.criticality,
                    evidence.document,
                    evidence.page,
                    evidence.section,
                    evidence.quote,
                    evidence.confidence,
                    evidence.remediation,
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


def _row_to_field_candidate(row: sqlite3.Row) -> FieldCandidate:
    try:
        payload = json.loads(str(row["value_json"]))
    except (TypeError, ValueError, json.JSONDecodeError):
        payload = str(row["value_json"])
    keys = set(row.keys())
    return FieldCandidate(
        candidate_id=str(row["candidate_id"]),
        field_name=str(row["field_name"]),
        value=payload,
        normalized_value=str(row["normalized_value"]),
        value_hash=str(row["value_hash"]),
        source_id=str(row["source_id"]),
        source_url=str(row["source_url"]),
        retrieved_at=str(row["retrieved_at"]),
        trust_level=SourceTrustLevel(int(row["trust_level"])),
        official=bool(row["official"]),
        verified=bool(row["verified"]),
        confidence=float(row["confidence"]),
        selected=bool(row["selected"]),
        historical=bool(row["historical"]),
        manual_override=(
            bool(row["manual_selected"])
            if "manual_selected" in keys
            else False
        ),
    )


def _row_to_field_resolution(
    row: sqlite3.Row,
) -> FieldResolutionRecord:
    try:
        selected_value = json.loads(
            str(row["selected_value_json"] or "null")
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        selected_value = str(row["selected_value_json"] or "")
    return FieldResolutionRecord(
        resolution_id=str(row["resolution_id"]),
        registry_key=str(row["registry_key"]),
        field_name=str(row["field_name"]),
        action=FieldResolutionAction(str(row["action"])),
        previous_candidate_id=str(row["previous_candidate_id"]),
        selected_candidate_id=str(row["selected_candidate_id"]),
        selected_value=selected_value,
        selected_source_id=str(row["selected_source_id"]),
        resolved_at=str(row["resolved_at"]),
        resolved_by=str(row["resolved_by"]),
        note=str(row["note"]),
        conflict_id=str(row["conflict_id"]),
    )


def _effective_freshness_state(
    state: TenderFreshnessState,
    *,
    now: str | None = None,
) -> TenderFreshnessState:
    if state.deadline_expired or not state.verification_due_at:
        return state
    try:
        current = datetime.fromisoformat(
            (now or _utc_now()).replace("Z", "+00:00")
        )
        due = datetime.fromisoformat(
            state.verification_due_at.replace("Z", "+00:00")
        )
    except ValueError:
        return state
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
    if current.astimezone(timezone.utc) < due.astimezone(timezone.utc):
        return state
    if state.is_stale and state.status == TenderFreshnessStatus.STALE:
        return state
    return replace(
        state,
        status=TenderFreshnessStatus.STALE,
        is_stale=True,
        stale_reason="Наступило время повторной проверки.",
    )


def _row_to_freshness_state(
    row: sqlite3.Row,
) -> TenderFreshnessState:
    seconds = row["seconds_remaining"]
    return TenderFreshnessState(
        canonical_key=str(row["registry_key"]),
        status=TenderFreshnessStatus(str(row["status"])),
        last_verified_at=str(row["last_verified_at"]),
        verification_due_at=str(row["verification_due_at"]),
        is_stale=bool(row["is_stale"]),
        stale_reason=str(row["stale_reason"]),
        deadline_original=str(row["deadline_original"]),
        source_timezone=str(row["source_timezone"]),
        timezone_status=DeadlineTimezoneStatus(
            str(row["timezone_status"])
        ),
        deadline_utc=str(row["deadline_utc"]),
        user_timezone=str(row["user_timezone"]),
        deadline_user_local=str(row["deadline_user_local"]),
        seconds_remaining=(
            int(seconds) if seconds is not None else None
        ),
        recheck_interval_minutes=int(
            row["recheck_interval_minutes"]
        ),
        deadline_expired=bool(row["deadline_expired"]),
        updated_at=str(row["updated_at"]),
    )


def _row_to_verification_state(
    row: sqlite3.Row,
) -> TenderVerificationState:
    try:
        missing = json.loads(str(row["missing_fields_json"] or "[]"))
    except json.JSONDecodeError:
        missing = []
    if not isinstance(missing, list):
        missing = []
    return TenderVerificationState(
        registry_key=str(row["registry_key"]),
        verification_run_id=str(row["verification_run_id"]),
        status=TenderVerificationStatus(str(row["status"])),
        last_verified_at=str(row["last_verified_at"]),
        critical_field_count=int(row["critical_field_count"]),
        verified_field_count=int(row["verified_field_count"]),
        official_field_count=int(row["official_field_count"]),
        missing_fields=tuple(str(item) for item in missing),
        conflict_count=int(row["conflict_count"]),
        unresolved_conflict_count=int(row["unresolved_conflict_count"]),
        minimum_confidence=float(row["minimum_confidence"]),
    )


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


def _verification_storage_id(
    verification_run_id: str,
    identity: str,
) -> str:
    import hashlib

    return hashlib.sha256(
        f"{verification_run_id}|{identity}".encode("utf-8")
    ).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


__all__ = ["CollectorStateRepository"]
