# RM-150 implementation plan

Baseline: `c7b9c2210dbcbb5db7b9b24fc81f0809d05f8d6b`  
Branch: `feat/rm-150-table-contract`

## Ordered delivery

1. Commit the nine-document audit/contract package before production changes.
2. Add characterization tests for all existing representative identities, selection fallbacks,
   sort/filter/update behavior, states, actions, export inputs and RM-141-style performance baseline.
3. Commit characterization and generated baseline evidence.
4. Add expected-red tests for immutable contracts, typed roles, identity selection, destructive
   revalidation, state regions, accessibility, parity and representative migrations; record exact
   intentional failures before implementation.
5. Implement the Qt-free contract and shared model/selection/filter/export adapters.
6. Migrate wave A foundation sites, then waves B–F in the matrix. Preserve every existing owner and
   run the focused/neighboring contour after each wave.
7. Run deterministic shuffled fixtures, 0/100/1,000/10,000 performance comparison, keyboard/manual
   checks and write `RM-150_ACCEPTANCE.md` with honest screen-reader status.
8. Run local and GitHub gates, merge the feature PR, verify the exact merge-SHA Quality Gate, then
   create and merge a separate docs-only closeout before RM-151 can start.

## Proposed modules

```text
app/ui/tables/
  __init__.py
  contracts.py       # frozen Qt-free values; no PySide6 import
  model.py           # QAbstractTableModel projection and stable roles
  filtering.py       # typed deterministic sort/filter projection
  selection.py       # exact-ID selection/focus restoration
  actions.py         # immutable action tokens; no mutation owner
  states.py          # sibling state-region binding
  export.py          # visible immutable snapshot
```

Existing `WorkflowTableModel`, `TenderFeedModel` and `ChartTableModel` are adapted or narrowed toward
the common boundary; they are not replaced with a competing repository/viewmodel stack. Site-specific
adapters remain next to their current owners where that avoids circular dependencies.

## Test sequence and gates

Characterization precedes expected-red; expected-red must demonstrate missing symbols/behavior before
implementation. Focused tests cover contracts, roles, selection, sort/filter/update, state,
accessibility, actions, export and benchmark. Neighboring tests cover RM-107, RM-142–RM-149,
workflow, dashboard, charts, analytics, registry/search, provider, workspace and backup.

Validation is derived from `pyproject.toml` and `.github/workflows/quality-gate.yml`:

```text
python -m pytest -q <focused RM-150 contour>
python -m pytest -q <neighboring contour>
python -m pytest -q
python scripts/check_repository_secrets.py
python -m ruff check .
python -m ruff format . --check
python -m mypy
python -m pip_audit --skip-editable
```

Also run the workflow's offline/migration/public-import/composition/build/frozen smoke commands
exactly, plus the deterministic benchmark and source-text/action-token security cases. Record exact
commands, versions, counts, warnings, durations and results in acceptance/canonical documents.

## Scope, rollback and stops

There is no DB/schema/migration, dependency, network-on-table, AI/scoring/decision/FX owner, generic
repository, second router or page stack. RM-107 critical priority and approved recommendation are
immutable. RM-147/RM-148/RM-149 typed snapshots and identities are reused.

Rollback is a feature-merge revert; no persisted-data downgrade is required. Stop on ambiguous
identity, stale or retargeted action, fake state rows, Decimal coercion, decision/critical drift,
export mismatch, unbounded UI work, lifecycle leak, required scope expansion or a red full/frozen/CI
gate.
