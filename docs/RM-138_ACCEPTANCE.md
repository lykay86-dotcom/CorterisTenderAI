# RM-138 Acceptance Evidence

Date: 2026-07-18
Feature branch: `feat/rm-138-parallel-search`
Base SHA: `d576f862aab13fa68ea752e479df5c518ff6af42`
Feature PR: `#84`
Feature merge SHA: `593ed39c7b81efc8a67e36eef47ceadbbbaf46ca`
Exact-merge Windows gate: `29619998396` (`success`)

## Outcome

The local implementation gate is green. RM-138 extends the accepted production Collector
coordinator in place with bounded parallel execution, an overall deadline, immutable typed
lifecycle snapshots, cooperative cancellation with late-result rejection, canonical partial
results, safe public/persisted errors, ordered non-blocking progress delivery, and UI presentation
of engine-owned progress.

The synchronous `TenderSearchEngine` import, constructor, `search(...)` signature, and result
contract remain compatible. No provider registry/model, normalizer, deduplicator, repository,
database, score owner, recommendation owner, or retry loop was added.

Feature PR #84 is merged and the Quality Gate succeeded against the actual merge SHA on Python
3.12 and 3.13. This separate documentation closeout marks RM-138 `DONE` and activates RM-139 as the
only `IN PROGRESS` stage.

## Environment

- OS: Microsoft Windows NT `10.0.19045.0`;
- timezone: `Russian Standard Time` (`Europe/Moscow` project context);
- local interpreter: Python `3.12.7`;
- repository environment: `C:\CorterisTenderAI_1_5_1\.venv`;
- Qt tests: `QT_QPA_PLATFORM=offscreen`;
- UTF-8 gate: `PYTHONUTF8=1`;
- clean dedicated worktree: `C:\CorterisTenderAI_1_5_1\.worktrees\rm138`.

Pytest basetemp directories were created inside the dedicated worktree because the sandbox denied
access to the user-wide pytest temp directory. Every generated basetemp was path-validated and
removed after its run.

## Entry baseline

Before the feature branch was created, the full suite at the base SHA completed with:

```text
1879 passed, 2 warnings in 146.83s
```

The two warnings are the accepted openpyxl warnings about unsupported worksheet extension and
conditional-formatting extension handling.

## Exact local commands and results

### Repository and static gates

```powershell
C:\CorterisTenderAI_1_5_1\.venv\Scripts\python.exe scripts/check_repository_secrets.py
```

Result: `Repository secret scan passed.`

```powershell
C:\CorterisTenderAI_1_5_1\.venv\Scripts\python.exe -m ruff check .
C:\CorterisTenderAI_1_5_1\.venv\Scripts\python.exe -m ruff format . --check
```

Result: Ruff passed; `611 files already formatted` after formatting the expected-red contract test.

```powershell
C:\CorterisTenderAI_1_5_1\.venv\Scripts\python.exe -m mypy
```

Result: `Success: no issues found in 20 source files`.

### Workflow smoke selectors

```powershell
$env:QT_QPA_PLATFORM='offscreen'
C:\CorterisTenderAI_1_5_1\.venv\Scripts\python.exe -m pytest -q `
  --basetemp=.pytest-rm138-smoke `
  tests/test_collector_provider_control.py::test_manager_exposes_all_sources_without_network `
  tests/test_mos_supplier_diagnostic_script.py::test_mos_diagnostic_runs_from_scripts_path_without_app_error `
  tests/test_database_migrations_121.py `
  tests/test_collector_schema_contract.py `
  tests/test_bootstrap_tender_search_integration.py `
  tests/test_build_release_contract.py `
  tests/test_frozen_self_test.py
```

Result: `14 passed in 21.14s`.

### Focused implementation gates

- lifecycle plus legacy async/characterization gate: `15 passed in 7.25s`;
- canonical partial/service gate: `13 passed in 9.70s`;
- headless Qt UI/integration gate: `23 passed in 10.02s`;
- post-format canonical/partial confirmation: `9 passed in 8.09s`.

### Repeated race/cancellation gate

The RM-138 contract and pre-existing cancellation-progress tests were run five consecutive times:

```powershell
1..5 | ForEach-Object {
  $raceTemp='.pytest-rm138-race-' + $_
  C:\CorterisTenderAI_1_5_1\.venv\Scripts\python.exe -m pytest -q `
    "--basetemp=$raceTemp" `
    tests/test_rm138_parallel_search_contract.py `
    tests/test_collector_progress.py
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
```

Results: five successful runs, each `9 passed`; durations were `5.49s`, `6.95s`, `7.64s`,
`5.31s`, and `7.05s`.

### Full regression suite

```powershell
$env:QT_QPA_PLATFORM='offscreen'
$env:PYTHONUTF8='1'
C:\CorterisTenderAI_1_5_1\.venv\Scripts\python.exe -m pytest -q `
  --basetemp=.pytest-rm138-full
```

Result:

```text
1892 passed, 2 warnings in 125.33s (0:02:05)
```

The two warnings are the unchanged accepted openpyxl warnings recorded in the entry baseline.

### Dependency audit

The first sandboxed invocation could not open a network socket to PyPI and was not treated as audit
evidence. It was repeated with approved network access and a worktree-local cache:

```powershell
C:\CorterisTenderAI_1_5_1\.venv\Scripts\python.exe -m pip_audit `
  --skip-editable --cache-dir .pip-audit-rm138
```

Result: `No known vulnerabilities found`; the editable project distribution was the only skipped
entry. The elevated cache directory was path-validated and removed after the audit.

## Requirement-to-evidence map

| Requirement | Implementation owner | Evidence |
| --- | --- | --- |
| One production coordinator | Existing `AsyncProviderSearchEngine` | Audit ownership map; sync signature characterization; no new engine class/file. |
| Bounded parallelism | Existing semaphore plus immutable lifecycle | Characterization peak-concurrency test; lifecycle snapshot test. |
| Immutable settings/admission | Existing `CollectorRunSession` and provider settings snapshot | Existing provider-control/schema/integration suites; no bypass introduced. |
| Exact queued/running/completed state | `ParallelSearchSnapshot` and provider snapshots | Snapshot invariant and monotonic-authority contract tests. |
| Aware UTC and monotonic deadlines | Snapshot validation and asyncio deadline | Snapshot timestamp validation; overall deadline contract test. |
| Idempotent cooperative cancellation | Existing cancellation token plus terminal lifecycle boundary | Existing cancel tests; late-result suppression test; five-cycle race gate. |
| No result after terminal state | Lifecycle `accept(...)` terminal guard | Provider-that-suppresses-task-cancel contract test. |
| Partial success | Accepted executions retained before cancel/failure | Existing partial-success/cancel-retention tests and Collector service tests. |
| Canonical partial results | RM-137 `TenderNormalizer` and `TenderDeduplicator` | Schedule-independent duplicate merge test; UI canonical partial test. |
| No duplicate normalization/dedup | Engine batch carries canonical `DeduplicationResult` into service | Collector service implementation and partial/service gate. |
| Deterministic output | Immutable provider order and canonical key ordering | Reversed provider-delay schedule test. |
| One retry owner | Existing `AsyncHttpClient` only | Coordinator single-invocation characterization; existing HTTP retry suite in full gate. |
| Safe errors | Central `classify_search_error(...)` | Secret-bearing provider, persistence, and Qt-worker tests. |
| Slow subscriber isolation | Bounded ordered progress dispatcher | Slow async subscriber timing test. |
| UI remains non-blocking | Existing one `QThreadPool` worker | Headless controller/UI suite and worker composition regression. |
| UI has no progress business math | Core `progress_percent` | Dialog/panel consume supplied percent; verification/freshness tests provide core values. |
| Deterministic decision authority unchanged | Existing verification/ranker/stop-factor pipeline | Full regression suite, including ranking/stop-factor/AI contract tests. |
| Sync compatibility | Legacy `TenderSearchEngine` unchanged | Public signature characterization and legacy search/dedup/failure suites. |

## Known physical limit

Python cannot safely terminate third-party blocking code that has already entered a worker thread
through `LegacySyncProviderAdapter` or the legacy synchronous engine. RM-138 makes coordinator
cancellation prompt, prevents new dispatch, publishes one terminal state, and rejects every late
result. A private legacy thread may still finish later; it cannot change returned, persisted, or UI
state. Native production EIS and Moscow providers remain cancellable async HTTP implementations.

## Merge evidence

- Feature PR: `#84` (`https://github.com/lykay86-dotcom/CorterisTenderAI/pull/84`).
- Feature merge SHA: `593ed39c7b81efc8a67e36eef47ceadbbbaf46ca`.
- PR Quality Gate run `29619784410`: Python 3.12 —
  `1892 passed, 2 warnings in 94.36s`; Python 3.13 —
  `1892 passed, 2 warnings in 111.15s`; both jobs `success`.
- Exact-merge push run `29619998396`
  (`https://github.com/lykay86-dotcom/CorterisTenderAI/actions/runs/29619998396`) has event `push`,
  `headSha=593ed39c7b81efc8a67e36eef47ceadbbbaf46ca`, and conclusion `success`.
- Exact Python 3.12 job: `1892 passed, 2 warnings in 102.67s`; dependency audit reported no known
  vulnerabilities.
- Exact Python 3.13 job: `1892 passed, 2 warnings in 82.24s`; dependency audit reported no known
  vulnerabilities.
- Canonical closeout changes RM-138 from `IN PROGRESS` to `DONE`, makes RM-139 the only active
  stage, and leaves RM-140–RM-200 `PLANNED`.

## Closeout validation

The separate docs-only closeout branch was created from the exact feature merge SHA. After the
canonical status transition, repository secret scan, Ruff check/format, mypy, diff-check, and the
full headless suite passed again:

```text
1892 passed, 2 warnings in 161.61s (0:02:41)
```
