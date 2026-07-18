# RM-144 implementation plan

## Scope and dependency order

Implement only `UI-141-004` and `UI-141-005` from exact closeout baseline
`b790d3a981b7e056fa9f548d6686a1a95d5bf49a`. Preserve RM-140 search shutdown, RM-142 typed
navigation/history/context, RM-143 design-system ownership, workflow/tender persistence, and all
deterministic decision authority.

## Phase 1 -- audit-first gate

Commit these four documentation files alone as
`docs(rm-144): audit shell composition and lifecycle`. Confirm no `app/` or test behavior change.
The baseline pytest temp directory is audit output and is excluded from the commit.

Rollback: revert the documentation commit. Stop if canonical status, exact RM-143 closeout SHA/gate,
or dedicated-worktree evidence becomes inconsistent.

## Phase 2 -- passing characterization

Add focused baseline tests, without changing behavior, for:

- exact supported tender import consumers, class identity expectation after extraction, wrapper
  shape, eight/six sections, object names, status bar, action/shortcut and tender-ID seams;
- current one-shell/one-stack production root and the documented baseline duplicate workflow graph;
- route context capture/restore and legacy `quotes`/`estimates` dispositions;
- existing tender-search veto before Dashboard shutdown and idempotent search double shutdown;
- monitor duplicate suppression, collector success/failure, and current page scheduling sources.

Likely files: new `tests/test_rm144_shell_characterization.py` and
`tests/test_rm144_lifecycle_characterization.py`, with minimal updates to existing RM-127/RM-142
helpers if needed. Commit as `test(rm-144): characterize shell and lifecycle owners`.

Rollback: revert tests. Stop if characterization requires live network/user data or contradicts an
accepted RM-140/RM-142/RM-143 contract.

## Phase 3 -- expected-red contracts

Add `tests/test_rm144_tender_workspace_extraction.py`,
`tests/test_rm144_workflow_composition.py`, and `tests/test_rm144_workflow_lifecycle.py`. They must
fail only because canonical implementation ownership, single workflow composition, lifecycle
states/shutdown, guarded timers/generations, and safe rapid close do not yet exist. Keep the failing
commit separate: `test(rm-144): add expected-red lifecycle contracts`.

Rollback: revert only expected-red tests. Stop if any existing test fails or a red maps outside
`UI-141-004/005`.

## Phase 4 -- mechanical tender extraction

Move the `TenderWorkspacePage` implementation, its implementation imports/constants, and no other
behavior from `app/ui/main_window.py` to `app/ui/pages/tender_workspace_page.py`. Reduce
`app/ui/main_window.py` to compatibility imports plus thin `MainWindow`; update test monkeypatch
targets and `scripts/audit_ui_inventory.py` classifications. Preserve exact public class identity,
sections/settings, object names, actions/shortcuts, unified search, status bar, tender ID, and frozen
importability.

Exact production files: `app/ui/pages/tender_workspace_page.py`, `app/ui/main_window.py`, and
`scripts/audit_ui_inventory.py`. Commit separately as
`refactor(rm-144): extract canonical tender workspace page`.

Rollback: revert this mechanical commit; no data rollback. Stop for circular imports, need for a
second implementation class, changed UI hierarchy, or any domain/search/AI/DB semantic diff.

## Phase 5 -- one workflow composition

Change workflow route destinations in `app/ui/navigation/registry.py` to one physical `workflow`
destination while retaining canonical route IDs and legacy aliases. Update `ModernMainWindow` to
create/add/connect/theme one `workflow_page`; keep `quotes_page is estimates_page is workflow_page`
only as temporary compatibility aliases. Route proposal/estimate/project intents through typed
context/state, register one context provider, remove peer-refresh logic, and update bootstrap
support-bundle discovery to prefer the canonical attribute without duplicate invocation.

Exact production files: `app/ui/navigation/registry.py`, `app/ui/modern_main_window.py`, and
`app/bootstrap.py`, plus focused RM-142/RM-144 tests. Commit as
`refactor(rm-144): converge on one workflow page`.

Rollback: revert this commit; presentation state is memory-only. Stop if the change needs a new
router, stack, repository/service, persisted navigation state, schema change, or duplicate QWidget
registration.

## Phase 6 -- monitor and page lifecycle

Implement typed monitor lifecycle/generation and dedicated owned-pool semantics in
`app/core/system_health_monitor.py`. Add idempotent lifecycle guards/shutdown to
`app/ui/pages/business_workflow_page.py`, including both repeating timers and both startup
single-shots. Extend `ModernMainWindow.closeEvent()` with once-only shell state and the accepted
tender preflight -> workflow -> Dashboard order. Do not weaken RM-140 or globally wait/terminate.

Exact production files: those three modules and lifecycle tests. Commit as
`fix(rm-144): close workflow health lifecycle safely`.

Rollback: revert the lifecycle commit; no persistent rollback. Stop if bounded safe close cannot be
proved without deleting a running signal source, global-pool wait, `terminate`, sleep/busy loop,
modal close behavior, or data mutation.

## Phase 7 -- journeys, no-duplicate evidence, and acceptance

Run focused RM-144 tests and neighboring RM-127, RM-128, RM-140, RM-142, RM-143, Dashboard,
workflow health/backup/import/export/history, bootstrap, build/frozen, and offline selections.
Exercise J01/J04/J07/J09/J12/J13/J16 using temporary repositories/fake adapters only. Record:

- one production QMainWindow, layout/stack, tender page, workflow page, workflow service/monitor/
  timer set, and same-object legacy aliases;
- three registered physical destinations and preserved route/selection behavior;
- no network attempt;
- before/after repeated construct-close object/timer/worker counts;
- no Qt deleted-source/receiver/running-thread warning;
- public import identity, eight/six tender sections and nine controller actions/shortcuts;
- unchanged DB/schema/dependencies and deterministic decisions.

Then run the exact current Quality Gate derived from `pyproject.toml` and
`.github/workflows/quality-gate.yml`:

```powershell
python scripts/check_repository_secrets.py
python -m ruff check .
python -m ruff format . --check
python -m mypy
python -m pytest -q
python -m pip_audit --skip-editable
git diff --check
```

Also run the workflow offline/migration/import/composition/build selections from the workflow.
Record exact commands, environment, counts, warnings, durations, and dependency-audit disposition
in `docs/RM-144_ACCEPTANCE.md`; commit as `docs(rm-144): record production shell acceptance`.

Publication follows repository DoD: feature PR, Windows Python 3.12/3.13 Quality Gate, merge,
successful exact feature merge-SHA gate, then a separate docs-only closeout PR that marks RM-144
`DONE` and activates RM-145. Do not treat a branch or PR-head run as the exact merge-SHA gate.

## Global stop conditions

Stop for any need to start RM-145+, add a dependency/DI container/event bus/router/worker framework,
change DB/schema/business transactions/import/export/backup/search/provider behavior, retire all
legacy exports, alter RM-107 decision priority, use live credentials/network/user data, or overwrite
unrelated worktree changes. Every production phase must retain observable one-instance evidence and
must be independently revertible.
