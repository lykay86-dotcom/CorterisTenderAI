"""Idempotent SQLite schema migration for collector persistence."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

from app.tenders.collector.provider_identity import provider_aliases

COLLECTOR_SCHEMA_VERSION = 16


@dataclass(frozen=True, slots=True)
class CollectorMigrationInventory:
    database_path: str
    current_version: int
    target_version: int
    requires_migration: bool
    requires_backup: bool


class CollectorSchemaMigrator:
    """Create collector tables inside the existing tender registry DB."""

    def migrate(self, connection: sqlite3.Connection) -> int:
        inventory = self.inspect(connection)
        current_version = inventory.current_version
        if 0 < current_version < COLLECTOR_SCHEMA_VERSION:
            self._create_verified_backup(connection, current_version)
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS collector_runs (
                run_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT NOT NULL DEFAULT '',
                query_json TEXT NOT NULL,
                requested_provider_ids_json TEXT NOT NULL,
                raw_count INTEGER NOT NULL DEFAULT 0,
                merged_count INTEGER NOT NULL DEFAULT 0,
                duplicate_count INTEGER NOT NULL DEFAULT 0,
                new_count INTEGER NOT NULL DEFAULT 0,
                unchanged_count INTEGER NOT NULL DEFAULT 0,
                changed_count INTEGER NOT NULL DEFAULT 0,
                provider_count INTEGER NOT NULL DEFAULT 0,
                successful_provider_count INTEGER NOT NULL DEFAULT 0,
                failed_provider_count INTEGER NOT NULL DEFAULT 0,
                elapsed_ms INTEGER NOT NULL DEFAULT 0,
                error_type TEXT NOT NULL DEFAULT '',
                error_message TEXT NOT NULL DEFAULT ''
            );

            CREATE INDEX IF NOT EXISTS idx_collector_runs_started
                ON collector_runs(started_at DESC);
            CREATE INDEX IF NOT EXISTS idx_collector_runs_status
                ON collector_runs(status, started_at DESC);

            CREATE TABLE IF NOT EXISTS collector_run_providers (
                run_id TEXT NOT NULL,
                provider_id TEXT NOT NULL,
                display_name TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                item_count INTEGER NOT NULL DEFAULT 0,
                page_count INTEGER NOT NULL DEFAULT 0,
                artifact_count INTEGER NOT NULL DEFAULT 0,
                elapsed_ms INTEGER NOT NULL DEFAULT 0,
                warnings_json TEXT NOT NULL DEFAULT '[]',
                error_type TEXT NOT NULL DEFAULT '',
                error_message TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (run_id, provider_id),
                FOREIGN KEY (run_id)
                    REFERENCES collector_runs(run_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS collector_run_items (
                run_id TEXT NOT NULL,
                registry_key TEXT NOT NULL,
                observation_status TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                source_count INTEGER NOT NULL DEFAULT 1,
                duplicate_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (run_id, registry_key),
                FOREIGN KEY (run_id)
                    REFERENCES collector_runs(run_id)
                    ON DELETE CASCADE,
                FOREIGN KEY (registry_key)
                    REFERENCES tender_records(registry_key)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_collector_run_items_registry
                ON collector_run_items(registry_key);

            CREATE TABLE IF NOT EXISTS collector_tender_aliases (
                alias_key TEXT PRIMARY KEY,
                alias_type TEXT NOT NULL,
                registry_key TEXT NOT NULL,
                strength INTEGER NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                FOREIGN KEY (registry_key)
                    REFERENCES tender_records(registry_key)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_collector_alias_registry
                ON collector_tender_aliases(registry_key);

            CREATE TABLE IF NOT EXISTS collector_tender_sources (
                registry_key TEXT NOT NULL,
                source TEXT NOT NULL,
                external_id TEXT NOT NULL,
                procurement_number TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (registry_key, source, external_id),
                FOREIGN KEY (registry_key)
                    REFERENCES tender_records(registry_key)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_collector_sources_external
                ON collector_tender_sources(source, external_id);

            CREATE TABLE IF NOT EXISTS collector_tender_versions (
                version_id TEXT PRIMARY KEY,
                registry_key TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                source TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                UNIQUE (registry_key, content_hash),
                FOREIGN KEY (registry_key)
                    REFERENCES tender_records(registry_key)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_collector_versions_registry
                ON collector_tender_versions(registry_key, observed_at DESC);

            CREATE TABLE IF NOT EXISTS collector_tender_changes (
                change_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                registry_key TEXT NOT NULL,
                detected_at TEXT NOT NULL,
                source TEXT NOT NULL,
                change_type TEXT NOT NULL,
                field_name TEXT NOT NULL,
                old_value TEXT NOT NULL DEFAULT '',
                new_value TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (run_id)
                    REFERENCES collector_runs(run_id)
                    ON DELETE CASCADE,
                FOREIGN KEY (registry_key)
                    REFERENCES tender_records(registry_key)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_collector_changes_registry
                ON collector_tender_changes(registry_key, detected_at DESC);
            CREATE INDEX IF NOT EXISTS idx_collector_changes_run
                ON collector_tender_changes(run_id);


            CREATE TABLE IF NOT EXISTS collector_tender_scores (
                score_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL DEFAULT '',
                registry_key TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'collector',
                scored_at TEXT NOT NULL,
                total_score INTEGER NOT NULL,
                recommendation TEXT NOT NULL,
                hard_excluded INTEGER NOT NULL DEFAULT 0,
                profile_version TEXT NOT NULL,
                input_fingerprint TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                UNIQUE(registry_key, source, input_fingerprint),
                FOREIGN KEY (registry_key)
                    REFERENCES tender_records(registry_key)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_collector_scores_registry
                ON collector_tender_scores(registry_key, scored_at DESC);

            CREATE TABLE IF NOT EXISTS collector_stop_factor_assessments (
                assessment_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL DEFAULT '',
                registry_key TEXT NOT NULL,
                status TEXT NOT NULL,
                evaluated_at TEXT NOT NULL,
                input_fingerprint TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                UNIQUE (registry_key, input_fingerprint),
                FOREIGN KEY (registry_key)
                    REFERENCES tender_records(registry_key)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_collector_stop_assessments_registry
                ON collector_stop_factor_assessments(
                    registry_key,
                    evaluated_at DESC
                );
            CREATE INDEX IF NOT EXISTS idx_collector_stop_assessments_status
                ON collector_stop_factor_assessments(status, evaluated_at DESC);

            CREATE TABLE IF NOT EXISTS collector_stop_factors (
                factor_id TEXT NOT NULL,
                assessment_id TEXT NOT NULL,
                registry_key TEXT NOT NULL,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                criticality TEXT NOT NULL,
                document_name TEXT NOT NULL,
                page_reference TEXT NOT NULL,
                section_name TEXT NOT NULL,
                quote_fragment TEXT NOT NULL,
                confidence REAL NOT NULL,
                remediation TEXT NOT NULL,
                PRIMARY KEY (assessment_id, factor_id),
                FOREIGN KEY (assessment_id)
                    REFERENCES collector_stop_factor_assessments(assessment_id)
                    ON DELETE CASCADE,
                FOREIGN KEY (registry_key)
                    REFERENCES tender_records(registry_key)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_collector_stop_factors_registry
                ON collector_stop_factors(registry_key, status, kind);

            CREATE TABLE IF NOT EXISTS collector_matching_catalog_entries (
                entry_id TEXT PRIMARY KEY,
                group_key TEXT NOT NULL,
                term TEXT NOT NULL,
                kind TEXT NOT NULL,
                direction TEXT NOT NULL DEFAULT '',
                canonical_term TEXT NOT NULL DEFAULT '',
                weight_percent INTEGER NOT NULL DEFAULT 100,
                category TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT 'user',
                active INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL,
                UNIQUE(group_key, term, kind, direction)
            );
            CREATE INDEX IF NOT EXISTS idx_matching_catalog_active
                ON collector_matching_catalog_entries(active, kind, direction);
            CREATE TABLE IF NOT EXISTS collector_matching_catalog_settings (
                singleton_id INTEGER PRIMARY KEY CHECK(singleton_id = 1),
                payload_json TEXT NOT NULL,
                revision INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS collector_matching_catalog_revisions (
                revision_id TEXT PRIMARY KEY,
                revision INTEGER NOT NULL,
                saved_at TEXT NOT NULL,
                saved_by TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS collector_commercial_estimates (
                estimate_id TEXT PRIMARY KEY,
                registry_key TEXT NOT NULL,
                status TEXT NOT NULL,
                currency TEXT NOT NULL,
                known_cost TEXT NOT NULL,
                total_cost TEXT,
                proposed_revenue TEXT,
                profit TEXT,
                margin_percent TEXT,
                calculated_at TEXT NOT NULL,
                input_fingerprint TEXT NOT NULL,
                draft_json TEXT NOT NULL,
                result_json TEXT NOT NULL,
                UNIQUE(registry_key, input_fingerprint),
                FOREIGN KEY(registry_key)
                    REFERENCES tender_records(registry_key)
                    ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_commercial_estimates_registry
                ON collector_commercial_estimates(
                    registry_key,
                    calculated_at DESC
                );
            CREATE TABLE IF NOT EXISTS collector_commercial_cost_lines (
                estimate_id TEXT NOT NULL,
                line_id TEXT NOT NULL,
                registry_key TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                quantity TEXT NOT NULL,
                unit_cost TEXT,
                total TEXT,
                evidence_json TEXT,
                PRIMARY KEY(estimate_id, line_id),
                FOREIGN KEY(estimate_id)
                    REFERENCES collector_commercial_estimates(estimate_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS collector_vertical_source_verifications (
                verification_id TEXT PRIMARY KEY,
                provider_id TEXT NOT NULL,
                connection_mode TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                live INTEGER NOT NULL DEFAULT 0,
                error_message TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_vertical_verification_provider
                ON collector_vertical_source_verifications(
                    provider_id,
                    completed_at DESC
                );

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
            CREATE TABLE IF NOT EXISTS collector_aggregator_verification_attempts (
                attempt_id TEXT PRIMARY KEY,
                discovery_id TEXT NOT NULL,
                attempted_at TEXT NOT NULL,
                outcome TEXT NOT NULL,
                official_registry_key TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT '',
                evidence_json TEXT NOT NULL DEFAULT '[]',
                FOREIGN KEY(discovery_id)
                    REFERENCES collector_aggregator_discoveries(discovery_id)
                    ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_aggregator_attempts_discovery
                ON collector_aggregator_verification_attempts(
                    discovery_id,
                    attempted_at DESC
                );
            CREATE INDEX IF NOT EXISTS idx_collector_scores_run
                ON collector_tender_scores(run_id);
            CREATE INDEX IF NOT EXISTS idx_collector_scores_total
                ON collector_tender_scores(total_score DESC);

            CREATE TABLE IF NOT EXISTS collector_verification_runs (
                verification_run_id TEXT PRIMARY KEY,
                collector_run_id TEXT NOT NULL DEFAULT '',
                started_at TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                status TEXT NOT NULL,
                item_count INTEGER NOT NULL DEFAULT 0,
                verified_field_count INTEGER NOT NULL DEFAULT 0,
                conflict_count INTEGER NOT NULL DEFAULT 0,
                unresolved_conflict_count INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (collector_run_id)
                    REFERENCES collector_runs(run_id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_verification_runs_collector
                ON collector_verification_runs(
                    collector_run_id,
                    completed_at DESC
                );

            CREATE TABLE IF NOT EXISTS collector_tender_field_values (
                candidate_id TEXT PRIMARY KEY,
                verification_run_id TEXT NOT NULL,
                registry_key TEXT NOT NULL,
                field_name TEXT NOT NULL,
                value_json TEXT NOT NULL,
                normalized_value TEXT NOT NULL,
                value_hash TEXT NOT NULL,
                selected INTEGER NOT NULL DEFAULT 0,
                historical INTEGER NOT NULL DEFAULT 0,
                trust_level INTEGER NOT NULL,
                confidence REAL NOT NULL,
                official INTEGER NOT NULL DEFAULT 0,
                verified INTEGER NOT NULL DEFAULT 0,
                source_id TEXT NOT NULL,
                source_url TEXT NOT NULL DEFAULT '',
                retrieved_at TEXT NOT NULL,
                FOREIGN KEY (verification_run_id)
                    REFERENCES collector_verification_runs(
                        verification_run_id
                    )
                    ON DELETE CASCADE,
                FOREIGN KEY (registry_key)
                    REFERENCES tender_records(registry_key)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_field_values_registry
                ON collector_tender_field_values(
                    registry_key,
                    field_name,
                    selected,
                    retrieved_at DESC
                );
            CREATE INDEX IF NOT EXISTS idx_field_values_verification
                ON collector_tender_field_values(
                    verification_run_id,
                    registry_key
                );

            CREATE TABLE IF NOT EXISTS collector_tender_field_provenance (
                provenance_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL UNIQUE,
                verification_run_id TEXT NOT NULL,
                registry_key TEXT NOT NULL,
                field_name TEXT NOT NULL,
                value_hash TEXT NOT NULL,
                source_id TEXT NOT NULL,
                source_url TEXT NOT NULL DEFAULT '',
                retrieved_at TEXT NOT NULL,
                verified INTEGER NOT NULL DEFAULT 0,
                official INTEGER NOT NULL DEFAULT 0,
                confidence REAL NOT NULL,
                trust_level INTEGER NOT NULL,
                FOREIGN KEY (candidate_id)
                    REFERENCES collector_tender_field_values(candidate_id)
                    ON DELETE CASCADE,
                FOREIGN KEY (verification_run_id)
                    REFERENCES collector_verification_runs(
                        verification_run_id
                    )
                    ON DELETE CASCADE,
                FOREIGN KEY (registry_key)
                    REFERENCES tender_records(registry_key)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_provenance_registry
                ON collector_tender_field_provenance(
                    registry_key,
                    field_name,
                    retrieved_at DESC
                );

            CREATE TABLE IF NOT EXISTS collector_tender_field_conflicts (
                conflict_id TEXT PRIMARY KEY,
                verification_run_id TEXT NOT NULL,
                registry_key TEXT NOT NULL,
                field_name TEXT NOT NULL,
                conflict_type TEXT NOT NULL,
                candidate_ids_json TEXT NOT NULL,
                selected_candidate_id TEXT NOT NULL,
                detected_at TEXT NOT NULL,
                critical INTEGER NOT NULL DEFAULT 1,
                unresolved INTEGER NOT NULL DEFAULT 0,
                message TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (verification_run_id)
                    REFERENCES collector_verification_runs(
                        verification_run_id
                    )
                    ON DELETE CASCADE,
                FOREIGN KEY (registry_key)
                    REFERENCES tender_records(registry_key)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_field_conflicts_registry
                ON collector_tender_field_conflicts(
                    registry_key,
                    unresolved,
                    detected_at DESC
                );

            CREATE TABLE IF NOT EXISTS collector_tender_field_manual_selections (
                registry_key TEXT NOT NULL,
                field_name TEXT NOT NULL,
                candidate_id TEXT NOT NULL,
                selected_at TEXT NOT NULL,
                selected_by TEXT NOT NULL DEFAULT 'user',
                note TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (registry_key, field_name),
                FOREIGN KEY (registry_key)
                    REFERENCES tender_records(registry_key)
                    ON DELETE CASCADE,
                FOREIGN KEY (candidate_id)
                    REFERENCES collector_tender_field_values(candidate_id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_manual_field_candidate
                ON collector_tender_field_manual_selections(candidate_id);

            CREATE TABLE IF NOT EXISTS collector_tender_field_resolution_history (
                resolution_id TEXT PRIMARY KEY,
                registry_key TEXT NOT NULL,
                field_name TEXT NOT NULL,
                action TEXT NOT NULL,
                conflict_id TEXT NOT NULL DEFAULT '',
                previous_candidate_id TEXT NOT NULL DEFAULT '',
                selected_candidate_id TEXT NOT NULL DEFAULT '',
                selected_value_json TEXT NOT NULL DEFAULT 'null',
                selected_source_id TEXT NOT NULL DEFAULT '',
                resolved_at TEXT NOT NULL,
                resolved_by TEXT NOT NULL DEFAULT 'user',
                note TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (registry_key)
                    REFERENCES tender_records(registry_key)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_resolution_history_registry
                ON collector_tender_field_resolution_history(
                    registry_key,
                    resolved_at DESC
                );

            CREATE INDEX IF NOT EXISTS idx_resolution_history_field
                ON collector_tender_field_resolution_history(
                    registry_key,
                    field_name,
                    resolved_at DESC
                );

            CREATE TABLE IF NOT EXISTS collector_tender_verification_state (
                registry_key TEXT PRIMARY KEY,
                verification_run_id TEXT NOT NULL,
                status TEXT NOT NULL,
                last_verified_at TEXT NOT NULL,
                critical_field_count INTEGER NOT NULL DEFAULT 0,
                verified_field_count INTEGER NOT NULL DEFAULT 0,
                official_field_count INTEGER NOT NULL DEFAULT 0,
                missing_fields_json TEXT NOT NULL DEFAULT '[]',
                conflict_count INTEGER NOT NULL DEFAULT 0,
                unresolved_conflict_count INTEGER NOT NULL DEFAULT 0,
                minimum_confidence REAL NOT NULL DEFAULT 0,
                FOREIGN KEY (registry_key)
                    REFERENCES tender_records(registry_key)
                    ON DELETE CASCADE,
                FOREIGN KEY (verification_run_id)
                    REFERENCES collector_verification_runs(
                        verification_run_id
                    )
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_verification_state_status
                ON collector_tender_verification_state(
                    status,
                    last_verified_at DESC
                );


            CREATE TABLE IF NOT EXISTS collector_tender_freshness_state (
                registry_key TEXT PRIMARY KEY,
                verification_run_id TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                last_verified_at TEXT NOT NULL DEFAULT '',
                verification_due_at TEXT NOT NULL DEFAULT '',
                is_stale INTEGER NOT NULL DEFAULT 0,
                stale_reason TEXT NOT NULL DEFAULT '',
                deadline_original TEXT NOT NULL DEFAULT '',
                source_timezone TEXT NOT NULL DEFAULT '',
                timezone_status TEXT NOT NULL DEFAULT 'missing',
                deadline_utc TEXT NOT NULL DEFAULT '',
                user_timezone TEXT NOT NULL DEFAULT '',
                deadline_user_local TEXT NOT NULL DEFAULT '',
                seconds_remaining INTEGER,
                recheck_interval_minutes INTEGER NOT NULL DEFAULT 0,
                deadline_expired INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (registry_key)
                    REFERENCES tender_records(registry_key)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_freshness_state_status
                ON collector_tender_freshness_state(
                    status,
                    is_stale,
                    verification_due_at
                );

            CREATE INDEX IF NOT EXISTS idx_freshness_state_due
                ON collector_tender_freshness_state(
                    is_stale,
                    deadline_expired,
                    verification_due_at
                );

            CREATE TABLE IF NOT EXISTS collector_exchange_rate_quotes (
                quote_id TEXT PRIMARY KEY,
                base_currency TEXT NOT NULL,
                quote_currency TEXT NOT NULL,
                rate TEXT NOT NULL,
                effective_date TEXT NOT NULL,
                source TEXT NOT NULL,
                retrieved_at TEXT NOT NULL,
                source_url TEXT NOT NULL DEFAULT '',
                imported_at TEXT NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_exchange_rate_identity
                ON collector_exchange_rate_quotes(
                    base_currency,
                    quote_currency,
                    effective_date,
                    source,
                    rate
                );

            CREATE INDEX IF NOT EXISTS idx_exchange_rate_lookup
                ON collector_exchange_rate_quotes(
                    base_currency,
                    quote_currency,
                    effective_date DESC
                );

            CREATE TABLE IF NOT EXISTS collector_checkpoints (
                provider_id TEXT NOT NULL,
                scope_key TEXT NOT NULL,
                cursor TEXT NOT NULL DEFAULT '',
                watermark TEXT NOT NULL DEFAULT '',
                contract_version TEXT NOT NULL DEFAULT '',
                parser_version TEXT NOT NULL DEFAULT '',
                query_fingerprint TEXT NOT NULL DEFAULT '',
                last_accepted_page_id TEXT NOT NULL DEFAULT '',
                accepted_page_count INTEGER NOT NULL DEFAULT 0,
                accepted_item_count INTEGER NOT NULL DEFAULT 0,
                replay_generation INTEGER NOT NULL DEFAULT 0,
                committed_at TEXT NOT NULL DEFAULT '',
                state_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (provider_id, scope_key)
            );

            CREATE TABLE IF NOT EXISTS collector_run_leases (
                lease_name TEXT PRIMARY KEY,
                run_id TEXT NOT NULL UNIQUE,
                acquired_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES collector_runs(run_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS collector_artifact_contents (
                content_sha256 TEXT PRIMARY KEY,
                byte_length INTEGER NOT NULL,
                storage_path TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS collector_raw_artifact_refs (
                reference_id TEXT PRIMARY KEY,
                content_sha256 TEXT NOT NULL,
                run_id TEXT NOT NULL,
                provider_id TEXT NOT NULL,
                page_identity TEXT NOT NULL,
                media_type TEXT NOT NULL,
                encoding TEXT NOT NULL,
                request_method TEXT NOT NULL,
                request_url TEXT NOT NULL,
                status_code INTEGER,
                retrieved_at TEXT NOT NULL,
                query_fingerprint TEXT NOT NULL,
                contract_version TEXT NOT NULL,
                parser_version TEXT NOT NULL,
                parse_outcome TEXT NOT NULL,
                retention_class TEXT NOT NULL,
                FOREIGN KEY (content_sha256)
                    REFERENCES collector_artifact_contents(content_sha256),
                FOREIGN KEY (run_id) REFERENCES collector_runs(run_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_collector_artifact_page
                ON collector_raw_artifact_refs(run_id, provider_id, page_identity);

            CREATE TABLE IF NOT EXISTS collector_accepted_pages (
                run_id TEXT NOT NULL,
                provider_id TEXT NOT NULL,
                query_fingerprint TEXT NOT NULL,
                page_identity TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                contract_version TEXT NOT NULL,
                parser_version TEXT NOT NULL,
                next_cursor TEXT NOT NULL,
                terminal INTEGER NOT NULL,
                item_count INTEGER NOT NULL,
                items_json TEXT NOT NULL,
                artifact_refs_json TEXT NOT NULL,
                content_digest TEXT NOT NULL,
                accepted_at TEXT NOT NULL,
                replay_generation INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (run_id, provider_id, page_identity),
                FOREIGN KEY (run_id) REFERENCES collector_runs(run_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_collector_accepted_page_replay
                ON collector_accepted_pages(
                    provider_id,
                    query_fingerprint,
                    page_identity
                );

            CREATE TABLE IF NOT EXISTS collector_participation_decisions (
                decision_id TEXT PRIMARY KEY,
                registry_key TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                confidence REAL NOT NULL,
                summary TEXT NOT NULL,
                policy_version TEXT NOT NULL,
                decided_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                FOREIGN KEY (registry_key)
                    REFERENCES tender_records(registry_key)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS collector_tender_summaries (
                summary_id TEXT PRIMARY KEY,
                registry_key TEXT NOT NULL,
                source TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                FOREIGN KEY (registry_key) REFERENCES tender_records(registry_key)
                    ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_tender_summaries_latest
                ON collector_tender_summaries(registry_key, generated_at DESC);

            CREATE INDEX IF NOT EXISTS idx_participation_decisions_latest
                ON collector_participation_decisions(
                    registry_key,
                    decided_at DESC
                );

            CREATE TABLE IF NOT EXISTS collector_provider_identity_aliases (
                alias_id TEXT PRIMARY KEY,
                canonical_id TEXT NOT NULL,
                introduced_version INTEGER NOT NULL
            );
            """
        )
        connection.executemany(
            """
            INSERT INTO collector_provider_identity_aliases(
                alias_id, canonical_id, introduced_version
            ) VALUES(?, ?, ?)
            ON CONFLICT(alias_id) DO UPDATE SET
                canonical_id=excluded.canonical_id,
                introduced_version=excluded.introduced_version
            """,
            (
                (alias, canonical, COLLECTOR_SCHEMA_VERSION)
                for alias, canonical in sorted(provider_aliases().items())
            ),
        )
        self._ensure_checkpoint_columns(connection)
        self._ensure_run_provider_columns(connection)
        connection.execute(
            """
            INSERT INTO tender_registry_meta(key, value)
            VALUES('collector_schema_version', ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (str(COLLECTOR_SCHEMA_VERSION),),
        )
        return COLLECTOR_SCHEMA_VERSION

    def inspect(self, connection: sqlite3.Connection) -> CollectorMigrationInventory:
        """Return a read-only migration inventory before any schema mutation."""

        current_row = connection.execute(
            "SELECT value FROM tender_registry_meta WHERE key='collector_schema_version'"
        ).fetchone()
        current_version = 0
        if current_row is not None:
            try:
                current_version = int(current_row[0])
            except (TypeError, ValueError) as exc:
                raise RuntimeError("Invalid collector schema version") from exc
        if current_version < 0:
            raise RuntimeError("Invalid collector schema version")
        if current_version > COLLECTOR_SCHEMA_VERSION:
            raise RuntimeError(
                "Collector database schema is newer than this application "
                f"({current_version} > {COLLECTOR_SCHEMA_VERSION})"
            )
        database_path = self._database_path(connection)
        return CollectorMigrationInventory(
            database_path=str(database_path) if database_path is not None else "",
            current_version=current_version,
            target_version=COLLECTOR_SCHEMA_VERSION,
            requires_migration=current_version != COLLECTOR_SCHEMA_VERSION,
            requires_backup=0 < current_version < COLLECTOR_SCHEMA_VERSION,
        )

    @classmethod
    def restore_verified_backup(
        cls,
        backup_path: str | Path,
        target_path: str | Path,
    ) -> Path:
        """Explicitly restore a verified SQLite backup via same-directory atomic replace."""

        source = Path(backup_path).expanduser().resolve()
        target = Path(target_path).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        if (
            target.with_name(f"{target.name}-wal").exists()
            or target.with_name(f"{target.name}-shm").exists()
        ):
            raise RuntimeError("Collector restore target has active SQLite sidecars")
        temporary = target.with_name(f".{target.name}.{uuid4().hex}.restore")
        try:
            with closing(sqlite3.connect(source)) as backup:
                integrity = backup.execute("PRAGMA integrity_check").fetchone()
                if integrity is None or str(integrity[0]).casefold() != "ok":
                    raise RuntimeError("Collector schema backup integrity check failed")
                with closing(sqlite3.connect(temporary)) as restored:
                    backup.backup(restored)
            with closing(sqlite3.connect(temporary)) as verified:
                restored_integrity = verified.execute("PRAGMA integrity_check").fetchone()
            if restored_integrity is None or str(restored_integrity[0]).casefold() != "ok":
                raise RuntimeError("Collector restored database integrity check failed")
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return target

    @staticmethod
    def _ensure_checkpoint_columns(connection: sqlite3.Connection) -> None:
        existing = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(collector_checkpoints)").fetchall()
        }
        definitions = {
            "contract_version": "TEXT NOT NULL DEFAULT ''",
            "parser_version": "TEXT NOT NULL DEFAULT ''",
            "query_fingerprint": "TEXT NOT NULL DEFAULT ''",
            "last_accepted_page_id": "TEXT NOT NULL DEFAULT ''",
            "accepted_page_count": "INTEGER NOT NULL DEFAULT 0",
            "accepted_item_count": "INTEGER NOT NULL DEFAULT 0",
            "replay_generation": "INTEGER NOT NULL DEFAULT 0",
            "committed_at": "TEXT NOT NULL DEFAULT ''",
        }
        for name, definition in definitions.items():
            if name not in existing:
                connection.execute(
                    f"ALTER TABLE collector_checkpoints ADD COLUMN {name} {definition}"
                )

    @staticmethod
    def _ensure_run_provider_columns(connection: sqlite3.Connection) -> None:
        existing = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(collector_run_providers)").fetchall()
        }
        for name in ("page_count", "artifact_count"):
            if name not in existing:
                connection.execute(
                    f"ALTER TABLE collector_run_providers "
                    f"ADD COLUMN {name} INTEGER NOT NULL DEFAULT 0"
                )

    @staticmethod
    def _create_verified_backup(connection: sqlite3.Connection, version: int) -> Path:
        database_path = CollectorSchemaMigrator._database_path(connection)
        if database_path is None:
            raise RuntimeError("Collector schema migration requires a file-backed database")
        backup_directory = database_path.parent / "backups"
        backup_directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup_path = backup_directory / (
            f"collector-v{version}-to-v{COLLECTOR_SCHEMA_VERSION}-{stamp}-{uuid4().hex}.sqlite3"
        )
        try:
            with closing(sqlite3.connect(backup_path)) as backup:
                connection.backup(backup)
            with closing(sqlite3.connect(backup_path)) as verified:
                integrity = verified.execute("PRAGMA integrity_check").fetchone()
                stored = verified.execute(
                    "SELECT value FROM tender_registry_meta WHERE key='collector_schema_version'"
                ).fetchone()
            if integrity is None or str(integrity[0]).casefold() != "ok":
                raise RuntimeError("Collector schema backup integrity check failed")
            if stored is None or int(stored[0]) != version:
                raise RuntimeError("Collector schema backup readback failed")
        except Exception:
            backup_path.unlink(missing_ok=True)
            raise
        return backup_path

    @staticmethod
    def _database_path(connection: sqlite3.Connection) -> Path | None:
        database_rows = connection.execute("PRAGMA database_list").fetchall()
        database_name = next(
            (str(row[2]) for row in database_rows if str(row[1]) == "main"),
            "",
        )
        if not database_name or database_name == ":memory:":
            return None
        return Path(database_name).resolve()


__all__ = [
    "COLLECTOR_SCHEMA_VERSION",
    "CollectorMigrationInventory",
    "CollectorSchemaMigrator",
]
