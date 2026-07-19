# RM-150 stable accessible table contracts acceptance

## Verdict and publication status

The RM-150 feature candidate satisfies the local automated acceptance gate. It establishes one
bounded presentation contract for table identity, updates, selection, actions, states, typed
sorting/filtering and export parity, and applies that contract to the eleven approved migration
sites. Twelve small/static sites remain compatible `keep` sites and twelve sites remain explicit
`defer` decisions; no mechanical all-table rewrite was performed.

Feature PR, PR-head Windows Python 3.12/3.13 evidence, merge, exact merge-SHA gate and the separate
canonical docs-only closeout are still pending. Therefore RM-150 remains the sole `IN PROGRESS`
stage and this document does not activate RM-151.

## Entry gate and traceability

- Exact feature baseline: `c7b9c2210dbcbb5db7b9b24fc81f0809d05f8d6b`, the RM-149 docs-only
  closeout merge.
- RM-149 feature PR #106 merged as `219e7c43527ca230a61de8cdeb3f191288fc3f87`.
- RM-149 exact merge-SHA Quality Gate run `29704404132` succeeded on Windows Python 3.12 and
  Python 3.13; both jobs reported `2245 passed`.
- RM-149 docs-only closeout PR #107 merged as the feature baseline above and canonically made
  RM-150 the only `IN PROGRESS` stage.
- Dedicated worktree/branch: `.worktrees/rm150`, `feat/rm-150-table-contract`.
- Audit and nine mandatory pre-production documents were committed as `6c79157` before
  characterization (`efd9402`), expected-red (`a9ba57d`) and production implementation
  (`0e90130`). The acceptance-discovered enum regression was corrected independently as
  `3e37a7c`.
- The unrelated root-checkout `.agents/` and `skills-lock.json` were not changed.

The work closes `UI-141-011` at feature-candidate level. Canonical closure remains reserved for the
post-merge docs-only package.

## Inventory and migration decision

The pre-production audit found 35 product table constructions: 32 `QTableWidget` and three
`QTableView` sites. This traces the original RM-141 inventory of 30 widget plus two view sites and
explicitly accounts for the three later RM-146/RM-147/RM-148 tables. The implemented source now
contains 36 constructions because `TableStateHost` owns one additional reusable adapter
`QTableView`; it is infrastructure for those product sites, not an unclassified product surface.

| Decision | Count | Accepted meaning |
|---|---:|---|
| migrate | 11 | identity/action/export/performance risk warrants common roles or adapters now |
| keep | 12 | bounded/static table remains simple while satisfying the compatibility contract |
| defer | 12 | owner or broader redesign belongs to a later RM; exact rationale is recorded |

Every site, owner, journey, risk and rationale is recorded in
`RM-150_TABLE_SURFACE_AUDIT.md` and `RM-150_TABLE_MIGRATE_KEEP_MATRIX.md`. The implementation does
not introduce a universal widget, repository, router, business owner or third-party grid.

## Common contract and deterministic invariants

- `app.ui.tables.contracts` is Qt-free and defines immutable, versioned surface/row/column/revision,
  cell, row, snapshot, state, selection and action-token values. Domain identity is namespaced and
  never inferred from a visible row index or localized label.
- `Decimal` remains the exact numeric boundary; float cells are rejected. Typed sorting has an
  explicit null policy and an identity tie-break independent of input/hash order. Text filtering is
  normalized and deterministic.
- Selection reconciliation restores only the same row identity. If it is filtered, removed or
  unavailable, selection becomes empty; it never moves an action to a neighboring row.
- Action validation rechecks exact surface, snapshot fingerprint, row identity, row revision and
  current availability before mutation.
- Loading, empty, error and partial states are siblings of the data view, not selectable fake rows.
  Accessible names/descriptions and stable semantic roles expose row, column, state and action
  meaning without depending on color.
- Export consumes the exact immutable visible projection. Row order, column order, exact values and
  snapshot fingerprint are identical to the displayed model; no re-query or display-string numeric
  conversion occurs.
- `ImmutableTableModel`, `TableSelectionController` and `TableStateHost` are reusable Qt adapters,
  not business owners. Rendering performs no repository, file, AI, provider or network I/O.

RM-107 remains the sole decision/critical stop-factor owner; RM-148 remains the financial
Decimal/currency owner; RM-149 remains the tender detail/action identity owner. No score,
recommendation, critical priority, financial formula, AI/provider or network path changed.

## Representative migration evidence

- Backup/restore uses exact path identity and revalidates the selected entry after confirmation.
- Chart and provider tables expose common identities, explicit states and accessible text while
  retaining their accepted compatibility roles.
- Dashboard rows receive explicit `legacy_orm` identity rather than a guessed registry bridge.
- Workflow sorting delegates once to typed source-record sorting with identity tie-break; filtering
  and model reset restore only the exact selected identity.
- Registry selection persists as an exact registry key across refresh/filter/archive visibility,
  and RM-149 action validation remains authoritative.
- Analytics financial and textual tables share row/column/revision/state/sort/export semantics from
  one snapshot and preserve exact Decimal values and fingerprints.
- Persisted search resolves actions through the common registry row identity, not current row
  position, while preserving its legacy compatibility role.
- Estimate and catalog tables use stable transient identities across recalculation and exact
  selected-row resolution.

Characterization covers inherited signals, roles, selection behavior and non-regressed owners. The
expected-red contract initially failed with 18 missing-contract errors, then passed after the common
contract and representative adapters were implemented.

## Performance evidence

Reproducible commands:

```text
python scripts/benchmark_rm150_tables.py --sizes 0 100 1000 10000 --warmups 5 --repeats 20 --production-baseline c7b9c2210dbcbb5db7b9b24fc81f0809d05f8d6b --label pre-production --output docs/RM-150_PERFORMANCE_BASELINE.json
python scripts/benchmark_rm150_tables.py --sizes 0 100 1000 10000 --warmups 5 --repeats 20 --production-baseline c7b9c2210dbcbb5db7b9b24fc81f0809d05f8d6b --label post-implementation --output docs/RM-150_PERFORMANCE_POST.json
```

Environment: Windows 10, Python 3.12.7, PySide6 6.11.1, `QT_QPA_PLATFORM=offscreen`.
Measurements exclude fixture generation, use five warm-ups and twenty timed repetitions, and take
a separate `tracemalloc` peak sample. No arbitrary timing threshold was added.

| 10,000-row scenario | Baseline p95 ms | Post p95 ms | Delta | Baseline/post peak bytes |
|---|---:|---:|---:|---:|
| workflow model reset | 8.984 | 13.242 | +47.4% | 717,264 / 797,264 |
| workflow missing-text filter | 117.155 | 137.449 | +17.3% | 2,480 / 2,480 |
| workflow Decimal sort | 2,295.315 | 90.907 | -96.0% | 2,553 / 240,600 |
| dashboard model reset | 0.110 | 0.084 | -23.6% | 80,128 / 80,128 |

The two variable sub-150 ms workflow operations remain bounded; the post filter p95 is also below
the RM-141 historical 148.005 ms observation. Typed sort is approximately 25 times faster. Its
~235 KiB peak is the bounded materialized source-record ordering that replaces thousands of Qt
proxy-to-Python comparisons; it does not grow an owner, cache, query or hidden sample. There is no
repository N+1 path in any measured scenario. Raw artifacts record all 0/100/1,000/10,000 results
and identify baseline production commit and exact measurement HEAD `3e37a7c91046042edac17c588769ad628ec857f9`.

## Exact local verification

| Contour | Result |
|---|---|
| focused RM-150 characterization/contracts/adapters | `31 passed in 7.45s` |
| deterministic contract run, `PYTHONHASHSEED=1` | `22 passed in 7.45s` |
| deterministic contract run, `PYTHONHASHSEED=987654` | `22 passed in 6.54s` |
| registry regression and neighboring contour | `18 passed in 11.90s` |
| required offline credential isolation smoke | `2 passed in 6.70s` |
| required legacy migration/schema smoke | `5 passed in 3.18s` |
| bootstrap tender integration | `1 passed in 0.29s` |
| build/release and frozen self-test | `7 passed in 4.65s` |
| full repository suite after regression fix | `2276 passed, 2 warnings in 151.15s` |
| repository secret scan | `Repository secret scan passed.` |
| Ruff check | `All checks passed!` |
| Ruff format | `744 files already formatted` before this acceptance document |
| canonical mypy | `Success: no issues found in 20 source files` |
| public import | `DashboardController` |
| dependency audit | `No known vulnerabilities found` |

The full-suite failure that preceded the final result was preserved and reduced to
`test_registry_shows_verification_column_and_signal`: the migration compared collector status to
the analytics-style nonexistent member `CONFLICTED` instead of collector member `CONFLICT`, which
aborted table population. Commit `3e37a7c` changes that single comparison. The focused integration
test and the full suite are the regression guards.

The two warnings are unchanged openpyxl unsupported-extension and conditional-formatting warnings
from `test_rm132_legacy_credentials_handoff.py`; RM-150 adds no warning. Only local Python 3.12.7
is installed. Windows Python 3.13 evidence must come from the PR-head and exact merge-SHA Quality
Gate before publication.

## Keyboard, accessibility and residual manual evidence

Automated Qt tests pass for stable selection/current identity, filtered/removed selection,
accessible names/descriptions/text roles, explicit state regions, exact action targets and native
keyboard-focusable controls. The common model exposes row/column/state/action semantics without
fake placeholder rows.

Native Narrator/screen-reader inspection, physical keyboard walkthrough, high contrast and physical
DPI inspection were `NOT_EXECUTED` locally and are not claimed. The automated semantic contract is
accepted for RM-150; full native accessibility/DPI certification remains explicitly owned by
RM-152. A newly packaged EXE and screenshot/golden certification were also not executed and remain
within RM-154/release scope.

## Security, rollback and pending publication gate

- No DB/schema/migration, dependency, settings, provider/network/AI, credential, scoring or
  deterministic decision change exists.
- Table fixtures contain generated values only. Cell rendering and adapters perform no I/O.
- Exact action identity/revision validation and no-neighbor selection behavior reduce destructive
  mis-target risk. Export stays on the visible immutable snapshot.
- Code rollback is a revert of RM-150 feature commits to baseline `c7b9c221`; there is no data,
  schema, dependency or settings rollback.
- Stop publication on any identity/export mismatch, adjacent-row fallback, changed owner or RM-107
  result, dependency/schema addition, full-suite failure, failed Python 3.12/3.13 job, or exact
  merge-SHA mismatch.
- Next required action: publish the feature branch, obtain a green PR-head Quality Gate, merge the
  feature PR, verify the automatic gate whose `headSha` exactly equals the feature merge SHA, then
  land a separate docs-only closeout that records GitHub evidence, marks RM-150 `DONE` and only then
  activates RM-151.
