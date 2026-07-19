# RM-144 production shell and lifecycle acceptance

## Package status

Feature implementation, publication, PR-head gate, merge and exact merge-SHA gate for
`UI-141-004` and `UI-141-005` are complete. This separate docs-only package records canonical
closeout and activates RM-145.

## Entry gate and traceability

- Exact baseline: RM-143 docs-only closeout merge
  `b790d3a981b7e056fa9f548d6686a1a95d5bf49a`, PR #95, 2026-07-19.
- RM-143 feature PR #94 merge: `c8d111f3db615dd3c21c231bf265bb00093c65bd`.
- Exact feature merge-SHA gate `29663124774` and exact closeout merge-SHA gate `29663578969`
  succeeded on Windows Python 3.12/3.13; the final jobs completed in `3m39s`/`4m30s`.
- Canonical status at branch creation: RM-143 `DONE`, RM-144 sole `IN PROGRESS`, RM-145--RM-200
  `PLANNED`.
- Dedicated branch/worktree: `feat/rm-144-production-shell`, `.worktrees/rm144`.
- Baseline full suite before application changes:
  `2059 passed, 2 warnings in 230.49s (0:03:50)`.
- Audit/contract/plan docs-only commit: `70d06f3`.
- Passing characterization commit: `a7e7b93`; focused `4 passed`, neighboring `20 passed`.
- Expected-red commit: `fab3eae`; nine failures exclusively for absent canonical ownership,
  single workflow composition, and lifecycle/shutdown contracts.
- Canonical tender extraction: `58ba458`.
- Single workflow composition: `9b998a0`; RM-142/RM-144 contour `45 passed`.
- Bounded lifecycle implementation: `705355c`; lifecycle/search/navigation contour `29 passed`.

The root checkout's unrelated untracked `.agents/` and `skills-lock.json` were not changed. All
repository-local pytest and dependency-audit temporary directories were removed after validation.

## Accepted composition

- `app.ui.pages.tender_workspace_page.TenderWorkspacePage` now owns the sole implementation.
  `app.ui.main_window.TenderWorkspacePage` is the exact same class object and `MainWindow` remains a
  thin separately constructible compatibility wrapper.
- The mechanical move preserves project data paths, safe JSON rendering, eight tender sections,
  six settings sections, object names, status-bar injection, unified search, tender-ID opening, and
  the nine existing controller action/shortcut identities.
- Production bootstrap still creates only `ModernMainWindow`; no compatibility `MainWindow` is
  nested or created.
- `DashboardLayout` remains the only navigation/page-stack owner. Physical destinations are now
  exactly `dashboard`, `tenders`, and `workflow`.
- All Workflow, Proposals, Estimates and Projects routes target the one physical `workflow` page.
  Typed child route intent applies exact proposal/estimate/project filters while preserving
  `RouteContext`/`WorkflowNavigationState` search, status, archive and stable-record behavior.
- `workflow_page` is the sole `BusinessWorkflowPage`. Temporary `quotes_page` and `estimates_page`
  compatibility attributes are same-object aliases; there is no second QWidget, repository/service
  set, monitor, timer pair, signal wiring, context provider, theme call, or stack registration.
- Bootstrap support-bundle discovery prefers `workflow_page` and deduplicates same-object aliases.

## Accepted lifecycle

- `SystemHealthLifecycleState` has `OPEN`, `RUNNING`, `CLOSING`, and terminal `CLOSED` states.
  Refresh is accepted only from idle `OPEN`; duplicates and post-close requests return `False`.
- Each default monitor owns a dedicated child `QThreadPool`, not the global pool. Shutdown tracks
  the exact worker/event, may remove a queued worker, and only bounded-waits the owned pool after the
  specific worker completes. It never waits for or terminates foreign work.
- The worker and its signals source are retained through `run()` completion. Snapshot/failure/
  finished delivery is current-sender and lifecycle guarded; late results while closing do not
  reach page widgets and `busy_changed(False)` is suppressed after delivery closes.
- Monitor and page shutdown are idempotent. Negative budgets fail before lifecycle mutation; a
  timed-out close remains `CLOSING`, retains the worker safely, rejects work, and reaches `CLOSED`
  when the owned job completes.
- `BusinessWorkflowPage.shutdown()` marks closing first, stops both repeating timers, disconnects
  scheduling signals, guards both pending startup single-shots, and closes its monitor. It performs
  no backup, recovery, import, modal UI, or repository mutation during close.
- `ModernMainWindow.closeEvent()` preserves RM-140 tender-search preflight/veto. After acceptance it
  disables shell actions, closes workflow once, closes Dashboard once, and delegates to Qt only
  after terminal owner results. Repeated close remains safe.

No `terminate()`, busy loop, arbitrary `sleep()`, global pool wait, new worker framework, router,
event bus, DI container, repository, dependency, migration, or schema change was introduced.

## Runtime reproduction before and after

The same isolated Windows offscreen construction used RM-127 dependency isolation, a socket
tripwire, real workflow health collection, event processing, immediate shell close/delete, and no
live provider/user data.

| Measure | Baseline | RM-144 result |
|---|---:|---:|
| `QApplication` | 1 | 1 |
| top-level / nested `QMainWindow` | 1 / 0 | 1 / 0 |
| `DashboardLayout` / shell page stack | 1 / 1 | 1 / 1 |
| registered physical pages | 4 | 3 |
| `TenderWorkspacePage` | 1 | 1 |
| `BusinessWorkflowPage` | 2 | 1 |
| `SystemHealthMonitor` | 2 | 1 |
| owned auto-backup/health timers before close | 4 | 2 |
| active health jobs at rapid close | 2 | 1 |
| socket connect attempts | 0 | 0 |
| monitor/page state after accepted close | undefined | `CLOSED` / `CLOSED` |
| owned timers after close | unsafe/unowned close | 0 |
| deleted signal-source errors | 2 reproduced | 0 |

The RM-144 run returned `close_accepted=true` and emitted no `Signal source has been deleted`,
deleted QObject/receiver, `QThread: Destroyed while thread is still running`, crash, or hang.

## Local test evidence

Environment: Windows, repository Python 3.12 virtual environment, `QT_QPA_PLATFORM=offscreen`,
temporary repositories/fake adapters, and repository-local isolated pytest base directories.

| Contour | Exact result |
|---|---|
| RM-144 contract (`test_rm144_tender_workspace_extraction`, composition, lifecycle) | `9 passed in 12.00s` |
| extraction/legacy/search/import consumers | `34 passed, 2 warnings in 32.89s` |
| single-workflow RM-142/RM-143/bootstrap contour | `45 passed in 27.23s` |
| lifecycle/RM-140/RM-127/RM-142 contour | `29 passed in 26.79s` |
| workflow/health/backup/database neighboring selection | `79 passed, 1994 deselected in 22.22s` |
| full `python -m pytest -q` | `2073 passed, 2 warnings in 206.16s (0:03:26)` |

The two full-suite warnings are the unchanged openpyxl unsupported-extension and
conditional-formatting warnings from `test_rm132_legacy_credentials_handoff.py`. RM-144 adds no
warning. The full-suite count increased by 14 tests: four characterization tests, nine expected-red
contracts now green, and one canonical bootstrap support-provider test.

## Local Quality Gate and CI-equivalent evidence

| Command/step | Result |
|---|---|
| `python scripts/check_repository_secrets.py` | passed |
| `python -m ruff check .` | passed |
| `python -m ruff format . --check` | `666 files already formatted` |
| `python -m mypy` | success, 20 source files |
| offline credential isolation smoke | `2 passed in 19.15s` |
| legacy migration/schema smoke | `5 passed in 11.87s` |
| public controller import | `DashboardController` |
| headless bootstrap composition smoke | `1 passed in 0.63s` |
| release/build/frozen smoke | `6 passed in 9.84s` |
| `python -m pip_audit --skip-editable` | no known vulnerabilities; editable project skipped |
| `python -m scripts.check_design_system --format summary` | `matrix=45; styles=43; violations=0` |
| `python -m scripts.audit_ui_inventory --format summary` | 78 modules, 31,147 lines, 119 UI test modules, no literal colours outside theme |
| `git diff --check` | passed before acceptance document |

The first parallel build-smoke attempt used pytest's inaccessible system `%TEMP%` and reported
`PermissionError` before one fixture setup; it was not a product/test failure. The exact build
selection was rerun with an isolated repository-local `--basetemp` and passed `6/6`. The first
sandboxed dependency audit was blocked from PyPI and the user cache; the approved retry used a
task-local cache, reached PyPI, and found no known vulnerabilities. Both temporary locations were
removed.

## Business/data boundaries and rollback

- `BusinessMetricsRepository`, tender repositories, import/export/history, backup/recovery,
  collector/search/provider ownership, database schema and migrations are unchanged.
- RM-142 route IDs, aliases, availability, allowlisted context, bounded history, focus/back/return,
  exact tender ID and stable workflow record identity remain intact; only the duplicated physical
  destination converged.
- RM-143 remains the sole design-system owner; its exact matrix/guard is green.
- RM-107 approved score, recommendation and absolute critical stop-factor priority are unchanged;
  AI output still cannot override them.
- No settings/data/credential/schedule migration exists. Rollback is a revert of RM-144 feature
  commits to `b790d3a`; no persistent downgrade is required.

## GitHub acceptance and closeout

- Feature PR #96 head: `15f49972b0e8caf539cfc65a2fe73f017160e047`.
- PR-head Quality Gate run `29665840955`: `success`; Python 3.12 — `3m35s`, Python 3.13 —
  `3m31s`. Full suite, dependency audit and every required step succeeded.
- Feature merge SHA: `491b13a0b5e5dd204bf00faba09fa513c5f9de3b`.
- Exact merge-SHA push run `29666054057`: `success`; Python 3.12 — `4m24s`, Python 3.13 —
  `4m51s`. Full suite, dependency audit and every required step succeeded.
- The only annotation is the existing non-blocking official-actions Node.js 20/24 migration notice.
- This docs-only closeout changes only `ROADMAP.md`, `STATUS.md`, `ROADMAP_HISTORY.md` and this
  acceptance file. It marks RM-144 `DONE` and activates RM-145 as the sole `IN PROGRESS` stage.

Final DoD verdict: RM-144 satisfies the Definition of Done. Feature and exact merge-SHA gates are
green; `UI-141-004` and `UI-141-005` are closed; DB/data/settings downgrade is unnecessary.
