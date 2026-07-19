# RM-145 Dashboard audit

## Audit identity

- Roadmap stage: RM-145, the sole `IN PROGRESS` stage.
- Finding in scope: `UI-141-006` only.
- Exact closeout baseline: `78141ff2764aa3b28facb80b332588b0cfaaeb45`.
- RM-144 feature merge: PR #96, `491b13a0b5e5dd204bf00faba09fa513c5f9de3b`,
  successful run `29666054057` on Python 3.12 and 3.13.
- RM-144 closeout: PR #97, baseline SHA above, successful run `29666535498` on
  Python 3.12 and 3.13.
- Dedicated implementation branch/worktree: `feat/rm-145-modern-dashboard` at
  `.worktrees/rm145`.

The baseline is clean inside the dedicated worktree. Unrelated untracked root-worktree content is
outside this package and remains untouched.

## Evidence read before code

The audit read the canonical status, roadmap, Definition of Done, history, RM-141 through RM-144
audit/contract/acceptance artifacts, current Dashboard implementation and tests, route registry,
shell composition, tender/workflow pages, and both repository owners. Mandatory searches covered
all six KPI keys, `DashboardKpi`, refresh timestamps, KPI activation, route context, workflow
status filters, and Dashboard formatting/parsing.

Baseline validation, before any RM-145 file change:

- focused Dashboard selection: `27 passed in 4.06s`;
- full suite: `2073 passed, 2 warnings in 179.66s (0:02:59)`; the warnings are the accepted
  openpyxl warnings in `test_rm132_legacy_credentials_handoff.py`;
- offline credential isolation: `2 passed in 14.77s`;
- migration/schema smoke: `5 passed in 7.28s`;
- composition smoke: `1 passed in 0.54s`;
- release/build/frozen smoke: `6 passed in 8.29s`;
- Ruff check, Ruff format check, mypy, secret scan, and `git diff --check`: passed;
- public Dashboard import: `DashboardController`;
- `pip-audit --skip-editable`: no known vulnerabilities; the local distribution was skipped
  because it is editable.

## Current ownership map

| Concern | Existing owner | Audited condition | RM-145 disposition |
|---|---|---|---|
| Dashboard value DTO | `app.ui.viewmodels.dashboard_viewmodel.DashboardKpi` | Presentation-only strings | Evolve this immutable lineage |
| Dashboard UI state | `DashboardViewModel` | Six definitions duplicated; piecemeal mutations | One atomic immutable publication |
| Snapshot assembly | `DashboardController` / `DashboardSnapshotBuilder` | Sequential sources; global failure; naive clock | Keep owner; inject clock and source evidence |
| KPI interaction | `app.ui.dashboard.kpi_center.KpiCenter` | Emits string key | Emit typed action carried by the KPI |
| Dashboard composition | `DashboardPage` under `DashboardLayout` | Parses formatted strings for auxiliary counts | Consume typed raw values only |
| Shell/navigation | `ModernMainWindow`, route registry/router | KPI action signal is not connected | Reuse typed route request/context seam |
| Tender source | `TenderRepository` | Dashboard query capped at 100 | Add exact reusable selector without new repository |
| Workflow source | `BusinessMetricsRepository` | Counts/profit are deterministic but contributor IDs are absent | Extend existing snapshot/evidence |
| Tender drill-down | `TenderWorkspacePage` | No closed Dashboard filter seam | Apply typed filter through existing page/model |
| Workflow drill-down | `BusinessWorkflowPage` and its proxy model | Existing kind/status/search filters | Add a closed Dashboard scope using the same predicates/IDs |
| Theme/layout | `app.ui.theme`, `DashboardLayout` | RM-143/RM-144 owners accepted | Preserve; presentation-only refinement |

No audited protocol or schema difference requires another controller, repository, router, page,
layout, theme, KPI DTO family, database table, dependency, or provider call.

## Six current KPI semantics and defects

| Stable key | Current calculation | Audit result | Accepted RM-145 meaning |
|---|---|---|---|
| `potential_profit` | Workflow potential profit, with tender-analysis fallback | Fallback changes the population and prevents exact workflow drill-down | Workflow-only deterministic potential-profit contributors |
| `new_tenders` | Tenders created on `loaded_at.date()` from a query capped at 100 | A valid count can be silently incomplete; timezone is implicit | All active tenders created in the injected local calendar day |
| `recommended` | Tender `score >= 80`, displayed as “AI recommends” | The label falsely claims AI/RM-107 decision authority | Same stable key, truthful “Оценка 80+”; never a recommendation |
| `proposals_in_work` | Proposal records in DRAFT/REVIEW/READY/SENT | Deterministic and suitable | Preserve formula and expose exact records |
| `active_projects` | Project records in PLANNED/ACTIVE/INSTALLATION/COMMISSIONING | Deterministic and suitable | Preserve formula and expose exact records |
| `attention` | Tender deadline heuristic plus workflow attention count | Mixed populations cannot produce one truthful drill-down | Workflow-only blocked/due-soon records (option C) |

The `recommended` key is an identifier compatibility constraint, not permission to present a
decision. A score threshold does not consult or override RM-107 recommendation or critical
stop-factor priority. The new label and accessible description must state that limitation.

## State, time, and publication findings

- Current `DataStateKind` is page-global and lacks the required per-KPI ZERO and STALE semantics.
- `DashboardViewModel.last_updated` uses render/mutation time and is refreshed repeatedly while a
  snapshot is applied. It is not trustworthy source evidence.
- `DashboardSnapshot.loaded_at` defaults to naive `datetime.now()`.
- The controller calls six `set_kpi` mutations and then other setters, so observers can see mixed
  snapshots.
- One repository exception fails the whole refresh. The prior view is preserved globally, but the
  affected source and per-KPI state are not explained.
- Demo and zero builders duplicate KPI definitions and generate their own current timestamps.

RM-145 will use an injected aware clock, record repository observation evidence, evaluate freshness
against a documented ten-minute threshold (twice the five-minute auto-refresh interval), and
publish one immutable Dashboard view state. Render time is never source time.

## Drill-down findings

The Dashboard currently emits the KPI key as an untyped string and the production shell does not
connect that signal. The tender page can open a tender by ID but cannot restore a Dashboard filter.
The workflow page already owns kind/status/search filtering and is the correct place to extend with
a closed Dashboard scope. Route context has no Dashboard-filter field.

The accepted seam is additive: a closed `DashboardFilterId` carried by the existing typed route
request/context. The registry determines the route. Destination pages apply the shared predicate or
stable contributor IDs. No calculation belongs in the router or widget.

## Scope boundary and stop conditions

In scope: KPI registry, typed raw values/evidence/actions, exact repository selectors, source-aware
states/freshness, atomic publication, value-to-filter parity, accessible activation, and restrained
Dashboard presentation polish.

Out of scope: RM-146 charts/analytics, forecasting, new recommendation logic, changed scoring or
critical-stop priority, persistence/schema migration, live provider calls, dependency changes,
parallel navigation/data owners, and broad tender/workflow redesign.

Stop if implementation requires any out-of-scope item, cannot preserve deterministic ownership, or
cannot prove value/filter parity with the same fixtures and source records.
