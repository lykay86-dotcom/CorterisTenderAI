# RM-148 implementation plan

## Constraints

Keep `BusinessMetricsRepository`, RM-145 contributor semantics, RM-146 charts, RM-147 query/time/
provenance, RM-144 lifecycle and RM-107 deterministic decisions. Add no dependency, network, FX,
AI, SQL schema or RM-149 detail redesign.

## Sequence

1. Commit this audit/ADR/contract package before production code.
2. Add characterization tests for v2 float/zero, Qt precision, Dashboard whole RUB, health/backup
   float validation and XLSX XML.
3. Add expected-red exact fixtures: cents, ties, zero/missing/invalid/non-finite/overprecision,
   RUB/unknown/mixed, margin edge cases, v2/v3, XLSX metadata and shuffled determinism.
4. Implement `app.financial`: immutable contracts, Decimal codec, currency/unit/state, rounding,
   formatter, margin, metric/snapshot service and JSON/CSV export.
5. Evolve the existing repository to v3 strings and add one controlled migration adapter with
   safety bytes/hash/dry-run/readback/rollback. Preserve event order and transaction lock.
6. Update backup, restore and health to shared validation; add concurrency/failure tests.
7. Replace workflow table/detail/dialog float paths with shared projections and derived margin.
8. Feed Dashboard from the financial snapshot while preserving potential-profit contributors.
9. Add a financial section through the accepted RM-147 route/controller and translate its snapshot
   to RM-146 `ChartSpec` without float or recalculation.
10. Update JSON/CSV/XLSX import/export; numeric XLSX cells remain usable while exact hidden metadata
    is authoritative and verified on reopen/XML.
11. Run focused, neighboring and full CI-derived gates, migration rehearsal, 0/1/100/1k/10k
    performance, frozen smoke and write `RM-148_ACCEPTANCE.md`.

## Test-first checkpoints

- Characterization commit precedes expected-red.
- Expected-red commit precedes production changes.
- No skip/xfail is used to bypass a failed acceptance.
- Fixed seed shuffles must produce byte-stable JSON/CSV and stable fingerprints.
- Export uses the supplied snapshot; repository access during export is a test failure.

## Rollback and stop conditions

Code rollback is a feature-merge revert. Data rollback uses verified byte safety artifacts only.
Stop on ambiguous currency, precision-losing chart contract, unverifiable XLSX exact metadata,
non-atomic migration/restore, audit incompatibility, SQL migration need, new dependency, RM-149
scope, or any change to deterministic score/recommendation/critical stop-factor priority.

