# RM-148 workflow schema and migration plan

## Schema decision

Current v2 JSON numbers are replaced by v3 canonical strings. One v3 record contains existing
identity/status/timestamp fields plus:

```json
{
  "total": "1000.00",
  "profit": "125.50",
  "currency": "RUB",
  "margin_percent": "12.55",
  "margin_version": "workflow-revenue-margin-v1"
}
```

`total`/`profit` are authoritative. Margin is a verified derived cache. Writer emits only v3.
Reader rejects future schema and corrupt/non-finite/exponent values. A compatibility reader may
inspect v2 using `json.loads(..., parse_float=Decimal, parse_int=Decimal)`; ordinary reads do not
rewrite bytes.

## Controlled v2→v3 operation

1. Acquire repository `RLock` and reject concurrent update/export/backup.
2. Read exact source bytes; record SHA-256 and schema.
3. Create a byte-exact `.v2.safety-<timestamp>.json` sibling and fsync it.
4. Parse numeric lexemes directly as Decimal.
5. Resolve v2 currency to RUB from the accepted ADR.
6. Validate type, finite value, bounds, scale and derived margin; produce stable row issues.
7. Dry run stops on every fatal/ambiguous issue and changes no bytes.
8. Serialize deterministic v3 candidate to a sibling temp; flush and fsync.
9. Atomic replace; reopen and semantically validate/fingerprint.
10. On any failure, restore safety bytes atomically and report both primary/rollback outcomes.
11. Record a technical migration evidence entry, not a user `UPDATED` event.

Migration is idempotent: rerun on valid v3 is a no-op. Partial/mixed schema is rejected. Downgrade
write is forbidden. Legacy naive timestamps remain unknown for interval metrics; migration does not
guess a timezone.

## Backup/restore/health

Backup manifest keeps schema version, counts and payload SHA. Validators use the shared Decimal/
currency/margin validator, never `float()`. Restore accepts supported schema only, creates a safety
backup, validates the candidate before replace and validates readback. Failure restores original
bytes. Health reports legacy-v2 as migration-required, v3 validity precisely, future schema as
incompatible and corrupt/invalid financial fields as actionable typed issues.

## Rollback

Before feature merge: restore the migration safety file. After feature merge: revert code and
restore v2 bytes only from the verified safety artifact; never synthesize float values from v3.
No SQLAlchemy schema/database migration is in scope.

