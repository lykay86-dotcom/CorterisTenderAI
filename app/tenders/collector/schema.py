"""Idempotent SQLite schema migration for collector persistence."""

from __future__ import annotations

import sqlite3


COLLECTOR_SCHEMA_VERSION = 6


class CollectorSchemaMigrator:
    """Create collector tables inside the existing tender registry DB."""

    def migrate(self, connection: sqlite3.Connection) -> int:
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
                state_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (provider_id, scope_key)
            );
            """
        )
        connection.execute(
            """
            INSERT INTO tender_registry_meta(key, value)
            VALUES('collector_schema_version', ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (str(COLLECTOR_SCHEMA_VERSION),),
        )
        return COLLECTOR_SCHEMA_VERSION


__all__ = ["COLLECTOR_SCHEMA_VERSION", "CollectorSchemaMigrator"]
