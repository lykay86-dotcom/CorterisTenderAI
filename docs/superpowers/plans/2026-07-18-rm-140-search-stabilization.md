# RM-140 — implementation plan стабилизации универсального поиска

Baseline: `f14ba84d754a4c84f1173812731e36ec274200f4`  
Branch/worktree: `feat/rm-140-search-stabilization`, `.worktrees/rm140`

## Phase A — mandatory audit gate

- Commit audit, contract and this plan as docs-only before tests/application code.
- Preserve root untracked `.agents/` and `skills-lock.json`.
- Do not implement RM-141 or change canonical roadmap status before exact merge-SHA success.

## Phase B — characterization commit

Add `tests/test_rm140_search_stabilization_characterization.py` or adjacent owner tests for:

- public legacy imports/signatures and deterministic provider selection/order;
- legacy blocking timeout behavior and current unsafe shutdown evidence without blessing it as target;
- unified/direct/scheduled shared admission versus saved-profile legacy route;
- current `collector_runs` and `tender_search_runs` rows, FKs/indexes and existing user-data reads;
- current aware async timestamps, naive legacy behavior and RM-137 unknown diagnostic;
- current RM-138 safe outcome/progress/order and offline composition;
- current RM-107 critical stop-factor/AI/Decimal/provenance invariants;
- Windows SQLite handle characterization using an explicit connection lifetime fixture.

Run old focused/neighbor tests and commit only passing characterization.

## Phase C — expected-red commit

Create focused RM-140 tests before production changes:

- `test_rm140_search_lifecycle.py`: typed transitions, one admission/terminal, manual/scheduler/profile
  conflict, late progress/result rejection;
- `test_rm140_shutdown.py`: close before/queued/running/cancelling/completed, repeated close, timer and
  provider-check cancel, bounded pool join, runtime close and Windows SQLite deletion;
- `test_rm140_timezone_contract.py`: active aware UTC, naive rejection/legacy unknown, injected
  monotonic wall rollback/forward jump;
- `test_rm140_error_redaction.py`: known/unknown/nested sentinel in class/message/URL/body/provider
  metadata absent from outcome, health, persistence, UI/log/notification/support bundle;
- `test_rm140_run_history_migration.py`: no-migration schema 14/1, one production writer, legacy
  read compatibility, old/current/future/corrupt behavior, idempotent initialization and linkage;
- `test_rm140_compatibility_retirement.py`: bootstrap/runtime no legacy graph, saved profile uses
  canonical Collector, public compatibility imports remain;
- `test_rm140_performance_contract.py`: deterministic size/count/concurrency/progress/cleanup bounds;
- `test_rm140_offline_composition.py`: socket/DNS/HTTP/keyring forbidden for import/compose/UI/close.

Expected-red is valid only when existing tests pass and failures name missing RM-140 behavior rather
than fixture/import mistakes. Record the exact failing command/output before implementation.

## Phase D — unify application lifecycle

- Add closed lifecycle enum and frozen snapshot to existing tender controller contour.
- Use a controller-owned `QThreadPool` by default; retain injected pool protocol for tests.
- Give Collector worker admission generation, started/completion signals and completion event.
- Gate every progress/result/error slot by active generation and terminal state.
- Route saved-profile and rerun actions into `_try_start_collector_query`; preserve bounded profile
  origin in existing `TenderSearchQuery.extra`.
- Extend scheduler controller with idempotent `shutdown()` that stops timer and rejects new ticks.
- Cancel provider check/Collector/full-search tokens that belong to search operations.
- Implement idempotent bounded `TenderSearchUiController.shutdown()` and wire modern shell plus
  bootstrap defense-in-depth.
- Do not use thread termination or unbounded waits.

## Phase E — retire legacy production composition

- Make `TenderSearchRuntime` analysis/document/registry composition independent of legacy engine,
  service and runner.
- Leave legacy fields optional/`None` for source compatibility where necessary.
- Remove production UI imports/worker/result creation for legacy saved-profile search.
- Keep `TenderSearchEngine`, service, runner and `app.tenders` exports for deprecated test/external
  compatibility; do not add a facade with its own orchestration.
- Update collector baseline/frozen/composition tests to assert canonical production owner.

## Phase F — time, errors and resource lifetime

- Validate active run timestamps as aware and normalize them to UTC before store writes.
- Reject new naive legacy run timestamp; expose unknown classification for old rows without rewrite.
- Keep `perf_counter`/async timeout for duration/deadline; inject clocks in focused tests.
- Make async outcome compatibility `error_type` a stable code; bound category/code/message/IDs.
- Classify before health registration; remove raw exception type/text from health/store/UI/log paths.
- Preserve timeout/cancel/not-configured fixed safe messages.
- Convert both existing repository connection factories to real context managers that always close
  SQLite handles after commit/rollback/read.

## Phase G — history retention and UI compatibility

- Keep Collector schema v14 and registry schema v1; no DDL/data-copy migration.
- Prove new production saved-profile runs exist only in `collector_runs`.
- Preserve legacy rows, run-item/tender FKs and public readers/writer for compatibility-only direct
  API use.
- Ensure registry UI does not mislabel unknown legacy timestamps; expose canonical history through
  existing owners where the current UI requires counts/occurrences, without double writing.
- Test row/link counts and hashes before/after initialization and rollback by code revert.

## Phase H — performance/offline/race acceptance

- Add stable deterministic performance test fixtures without fragile wall-time CI assertions.
- Re-run same-machine baseline script/command for 0/100/1k/10k and history/cancel metrics.
- Execute focused RM-140 plus RM-137 normalization, RM-138 parallel lifecycle, RM-139 monitoring,
  provider settings/scheduler/registry/UI/bootstrap/build and RM-107 decision contours.
- Run one five-cycle command; report each cycle, terminal count, late mutation and owned
  task/thread/timer/runtime/SQLite cleanup.
- Run workflow-derived secret scan, Ruff check/format, mypy, offline/migration/import/composition/
  build, full pytest and dependency audit.
- Record exact SHA, environment, commands, counts, durations, warnings and budget deltas in
  `docs/RM-140_ACCEPTANCE.md`.

## Phase I — publish and closeout

- Commit changes thematically; do not create empty template commits.
- Push feature branch, open PR with entry/audit/lifecycle/time/error/history/performance/offline/
  rollback/decision evidence.
- Resolve review and require Windows Quality Gate Python 3.12/3.13 plus dependency audit.
- Merge feature PR, identify exact `origin/main` merge SHA and verify a separate Actions run on it.
- Create `docs/rm-140-closeout` from exact merge SHA; update only acceptance and canonical roadmap
  documents, mark RM-140 `DONE`, RM-141 sole `IN PROGRESS`, RM-142–RM-200 `PLANNED`.
- Merge closeout and verify final canonical state; do not implement RM-141.

## Stop conditions

Stop with the specified blocker report if tests reveal an external production legacy consumer,
schema/data migration becomes necessary, timezone would need guessing, a secret reaches public
state, shutdown leaves owned work/handle alive, rollback/linkage fails, performance exceeds budget
without accepted explanation, full/Windows gates fail, or the safe fix requires a new owner or
RM-141+ scope.
