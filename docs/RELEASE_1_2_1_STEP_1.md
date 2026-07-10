# Release 1.2.1 — Step 1

## Database Migration Hotfix

This step upgrades old SQLite databases without deleting user data.

### Implemented

- automatic schema inspection;
- backup before migration;
- conversion of old integer IDs to deterministic UUIDs;
- preservation of tender, document and analysis relations;
- addition of `created_at`, `updated_at`, `is_deleted`, `deleted_at`, `row_version`;
- schema version 2;
- migration idempotency;
- SQLite integrity and health checks;
- startup health validation.

### Fixed

`sqlite3.OperationalError: no such column: tenders.updated_at`

### Backup location

For a database located at:

`<data directory>/corteris_tender_ai.db`

migration backups are stored in:

`<data directory>/backups/`
