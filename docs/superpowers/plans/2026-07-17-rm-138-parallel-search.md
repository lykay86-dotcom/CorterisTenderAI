# RM-138 Parallel Tender Search Implementation Plan

## Objective

Extend the existing production Collector coordinator with bounded parallel search, authoritative
immutable lifecycle snapshots, overall deadlines, safe error contracts, cooperative cancellation,
canonical partial results, and non-blocking UI delivery. Preserve synchronous compatibility and
all deterministic business decisions.

## Guardrails

- Work only on `feat/rm-138-parallel-search`, based on
  `d576f862aab13fa68ea752e479df5c518ff6af42`.
- Keep the audit/contract/plan as the first RM-138 commit.
- Add characterization and expected-red tests before production changes.
- Reuse `AsyncProviderSearchEngine`, `CollectorRunSession`, `TenderNormalizer`,
  `TenderDeduplicator`, `CollectorStateRepository`, provider settings/admission, and
  `AsyncHttpClient` retry.
- Do not add an engine, provider registry/model, normalizer, deduplicator, repository, database,
  score owner, recommendation owner, or retry loop.
- Use aware UTC for recorded time and monotonic clocks for deadline/latency arithmetic.

## Commit sequence

### 1. Audit and contract

Add:

- `docs/RM-138_PARALLEL_SEARCH_AUDIT.md`;
- `docs/RM-138_PARALLEL_SEARCH_CONTRACT.md`;
- this implementation plan.

Commit: `docs(rm-138): audit parallel tender search`

### 2. Characterization tests

Freeze current compatibility behavior before changing implementation:

- sync `TenderSearchEngine` import/signature/result compatibility;
- production provider ordering and bounded semaphore behavior;
- settings snapshot and manual-provider admission;
- canonical RM-137 dedup/provenance ownership;
- Collector partial-success persistence;
- UI worker remains outside the UI thread.

Commit: `test(rm-138): characterize parallel search boundaries`

### 3. Expected-red contract tests

Add focused failing tests for:

- immutable run/provider snapshots and monotonic revisions;
- exact queued/running/completed counters and monotonic engine-owned percent;
- overall monotonic deadline;
- idempotent cooperative cancellation and bounded cancellation latency;
- late-result rejection after terminal state;
- typed safe error redaction through outcome/persistence/UI boundaries;
- no coordinator retry over transport retry;
- normalized/deduplicated partial items and schedule-independent final output;
- slow/failing subscriber isolation and ordered terminal delivery;
- bounded shutdown without orphan asyncio tasks.

Commit: `test(rm-138): specify parallel search lifecycle`

### 4. Lifecycle and safe failures

Implement contract types as immutable value objects in the existing Collector contour. Add a
central exception classifier that converts known HTTP/provider/cancellation errors into fixed safe
categories and codes. Thread these values through outcomes, progress, persistence, and UI without
raw exception text.

Keep compatibility defaults for current `CollectorProgressEvent` consumers and existing test
doubles.

Commit: `feat(rm-138): add typed search lifecycle`

### 5. Deadlines, cancellation, and progress dispatcher

Extend `AsyncProviderSearchEngine` in place:

- capture immutable admitted provider order;
- track one revisioned state machine;
- enforce provider and overall monotonic deadlines;
- stop dispatch after cancel/deadline;
- discard late completions;
- publish exactly one terminal snapshot;
- deliver events through a bounded/coalescing dispatcher outside semaphore-held provider work;
- drain/close dispatcher with a bounded wait.

Do not add provider-level retry. Read attempts only from typed transport failures.

Commit: `feat(rm-138): enforce bounded parallel execution`

### 6. Canonical partial results

Create one per-run canonical accumulator using the RM-137 normalizer and deduplicator. Feed it only
accepted completed-provider items. Publish immutable partial canonical results after state changes,
and return the same canonical batch to `CollectorService` so final processing does not use a second
implementation.

Isolate invalid individual items with typed diagnostics while retaining valid items.

Commit: `feat(rm-138): publish deterministic partial results`

### 7. UI integration

Keep `_CollectorRunWorker` as the single background worker. Update Collector/unified views to use
engine-owned percent, provider lifecycle states, safe messages, and partial canonical tenders.
Remove phase-to-percent business calculations from widgets. Keep cancellation idempotent and the
Qt event loop responsive.

The older saved-profile worker remains compatible and is not silently redirected in this RM.

Commit: `feat(rm-138): integrate parallel search progress`

### 8. Acceptance and regression evidence

Add `docs/RM-138_ACCEPTANCE.md` with exact local commands/results, limits, and requirement-to-test
mapping. Run from the clean RM-138 worktree using the repository Python environment:

```powershell
python scripts/check_repository_secrets.py
python -m ruff check .
python -m ruff format . --check
python -m mypy
python -m pytest -q
python -m pip_audit --skip-editable
```

Also run the workflow smoke selectors from `.github/workflows/quality-gate.yml`, targeted RM-138
stress/race tests repeatedly, and UI/headless integration tests with `QT_QPA_PLATFORM=offscreen`.

Commit: `docs(rm-138): record acceptance evidence`

### 9. Feature PR and exact-merge gate

Push the branch, open a ready feature PR, wait for both Windows matrix jobs, merge only after green,
then capture the actual feature merge SHA. Run/verify the Quality Gate against that exact SHA on
Python 3.12 and 3.13. A PR-head-only run is not exact-merge evidence.

### 10. Documentation closeout

On a separate closeout branch based on the feature merge SHA:

- mark RM-138 `DONE` in `docs/STATUS.md` and `docs/ROADMAP.md`;
- activate RM-139 and no later stage;
- add accepted merge SHA, exact-gate run id/URL, Python matrix, test totals, warnings, and limitations
  to `docs/ROADMAP_HISTORY.md` and RM-138 acceptance evidence;
- run the full local gate again;
- open, validate, and merge a separate docs closeout PR.

## Rollback boundaries

Each implementation concern is kept in a separate commit. If cancellation/deadline behavior is
unstable, revert the bounded-execution commit without removing typed contracts. If partial
accumulation is unstable, revert its commit while retaining lifecycle safety. No rollback may
restore raw exception publication or introduce a second production search/dedup owner.
