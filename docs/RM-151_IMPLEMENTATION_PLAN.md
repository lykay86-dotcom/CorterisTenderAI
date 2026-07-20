# RM-151 implementation plan

## Verdict and constraints

Entry gate is open on `c07773772a360d9bd6f7a3da0b18f44c6315d725`. The implementation is
audit-first/tests-first, uses branch `feat/rm-151-operation-feedback`, adds no DB/schema migration,
dependency, network, telemetry, AI call, business formula or lifecycle owner, and does not activate
RM-152.

## Lineage

1. Eight mandatory documents are committed before `app/` changes.
2. Characterization tests and pre-change performance/lifecycle artifact are committed separately.
3. Expected-red core/security/routing/lifecycle/accessibility tests are committed separately and
   fail only because accepted contracts/adapters do not exist or known legacy markers leak.
4. Production implementation follows in bounded commits.
5. Acceptance document and artifacts are added only after focused/neighbor/full gates.

## Planned modules

Audit supports one new Qt-free namespace `app.operations`:

- `contracts.py`: IDs, subjects, states, progress, capabilities, episode and feedback values;
- `transitions.py`: deterministic state acceptance, stale/duplicate/terminal guards, retry factory;
- `safe_feedback.py`: reason mapping, SafeText and allowlist-first projection;
- `diagnostics.py`: bounded correlation record/index and existing-owner references;
- `notifications.py`: envelope, dedupe/action validation and schema-v1 compatibility adapter;
- `announcements.py`: logical-clock coalescing.

Qt adapters remain thin and may live under `app.ui.operations` only when a reusable presenter is
proven necessary. No service locator, event bus, worker pool, scheduler, repository or shell is
added.

## Representative production integration

1. Adapt `TenderSearchUiController` collector and tender worker signals at the existing owner
   boundary. Preserve RM-140 lifecycle, owner cancellation tokens, per-key active maps and all
   services.
2. Adapt `DashboardController` refresh to safe reason/episode projection and strengthen sender/
   generation/closed rejection without changing repository queries or KPI computation.
3. Wrap `CollectorNotificationService/Repository` with safe envelopes and deterministic dedupe;
   keep schema v1 bytes compatible. Make the existing dialog consume safe rows/actions and retain
   the already canonical topbar/shortcut route.
4. Adapt workflow health/backup/recovery and crash/support user summaries to the common safe
   projection/correlation path while preserving RM-144 lifecycle and diagnostic artifacts.
5. Add exact notification action validation using RM-142 routes, RM-149 tender identity and RM-150
   action/selection tokens. No display-title/row-index fallback.
6. Add the bounded announcement coalescer to representative in-surface/status/notification
   projections; do not implement the RM-152 screen-reader matrix.
7. Add a static regression guard preventing new raw user-facing exception/rich-text/keyring/core-Qt
   boundaries. Existing audited legacy cases remain explicit debt unless touched by this slice.

## Characterization plan

- RM-140 manual search state/generation/revision/cancel/close behavior;
- scheduler repository byte format, cap, dedupe/read-all/clear and damaged-file behavior;
- topbar/shortcut/menu same action owner and construction count;
- Dashboard worker start/partial/failure/thread cleanup;
- tender document/analysis/score worker raw failure signals and active-map cleanup;
- RM-144 health close/no-late-signal behavior;
- crash/report/support artifact retrieval and current raw summary paths;
- backup/recovery exact target confirmations;
- QObject/QThread/QTimer/subscription construct/close counts;
- malicious marker leak in at least one isolated legacy user projection.

## Expected-red plan

- exhaustive transitions, terminal immutability, stale generation/revision and retry parentage;
- progress/aware-time/Decimal invariants;
- malicious fixture absent from every safe projection while correlation remains retrievable;
- deterministic notification dedupe/read/action/freshness and schema-v1 adapter;
- topbar/shortcut convergence on existing center;
- confirmed cancellation and close/no-late-signal;
- announcement coalescing with logical clock;
- representative J02/J07/J08/J10/J13/J15 recovery outcomes.

## Performance/lifecycle measurement

A reproducible script measures 0/1/100/1,000/10,000 events, safe projection p50/p95,
notification dedupe, peak allocation, retained registry/coalescer objects and announcement count.
It also measures 1,000 duplicates and a large malicious input. Timing is evidence only; hard gates
are deterministic output, bounded count/length/memory structure and zero retained-object growth
after terminal cleanup.

## Verification derived from project configuration

Run the active workflow sequence from `.github/workflows/quality-gate.yml` and `pyproject.toml`:

1. `python scripts/check_repository_secrets.py`
2. `python -m ruff check .`
3. `python -m ruff format . --check`
4. `python -m mypy`
5. offline credential/source smoke
6. legacy migration/schema smoke
7. public import and bootstrap composition smoke
8. build/release and frozen self-test
9. RM-151 focused and neighboring RM-140/RM-144/scheduler/crash/support/workflow contours
10. full `python -m pytest -q`
11. `python -m pip_audit --skip-editable`

Exact totals, warnings, environment and benchmark results are recorded in
`docs/RM-151_ACCEPTANCE.md`.

## Stop and rollback

Stop for any required schema/dependency, ambiguous lifecycle/diagnostic owner, non-idempotent retry,
missing exact subject identity, unactionable sanitization or RM-152+ scope expansion. Feature
rollback is code revert to this baseline; because no persistence/schema change is planned, no data
rollback should be necessary. Legacy notification bytes and diagnostic artifacts must remain
readable after rollback.

## Publication

Feature PR title is `feat(rm-151): unify operation episodes and safe feedback`. RM-151 remains
`IN PROGRESS` through PR-head and feature merge. Only an exact feature merge-SHA Windows Python
3.12/3.13 gate followed by a separate docs-only closeout may mark RM-151 `DONE` and activate
RM-152.

