# RM-145 implementation plan

## Scope and dependency order

Implement only `UI-141-006` from exact RM-144 closeout baseline
`78141ff2764aa3b28facb80b332588b0cfaaeb45`. Preserve RM-140 search shutdown, RM-142 typed
navigation/history/context, RM-143 design ownership, RM-144 one-shell/one-workflow lifecycle,
repository persistence, approved score/recommendation semantics, and critical stop-factor priority.

## Phase 1 -- audit-first documentation gate

Commit these five files alone:

- `docs/RM-145_DASHBOARD_AUDIT.md`
- `docs/RM-145_DASHBOARD_JOBS.md`
- `docs/RM-145_KPI_CONTRACT.md`
- `docs/RM-145_DRILLDOWN_MATRIX.md`
- `docs/RM-145_IMPLEMENTATION_PLAN.md`

Commit intent: `docs(rm-145): audit dashboard KPI contracts`. Confirm no `app/`, test, dependency,
schema, or canonical roadmap file changes.

Rollback: revert the docs commit. Stop if the RM-144 exact gate, sole active-stage status, owner map,
or dedicated-worktree evidence becomes inconsistent.

## Phase 2 -- passing characterization

Add focused tests for current six-key ordering, present source formulas, Dashboard construction,
global refresh preservation, KPI activation seam, route context, workflow filters, RM-107 decision
non-ownership, and lifecycle behavior. Characterization describes current behavior without making
the required RM-145 behavior pass accidentally.

Commit intent: `test(rm-145): characterize dashboard KPI owners`.

Rollback: revert the test commit. Stop if characterization needs live provider/user data or reveals
that an accepted RM-142/RM-144 owner differs from the audit.

## Phase 3 -- expected-red contract

Add tests for the immutable registry, typed raw values/action/evidence, six closed states, injected
aware clock, exact local-day behavior, source-isolated failures, atomic publication, value/filter ID
parity, Decimal profit parity, typed route round-trip, honest score-cohort semantics, and keyboard/
accessible activation. The commit must fail only for the documented missing RM-145 behavior.

Commit intent: `test(rm-145): add expected-red KPI and drilldown contracts`.

Rollback: revert only the expected-red commit. Stop if a red maps to RM-146 analytics, schema,
provider, changed deterministic decision logic, or a second owner.

## Phase 4 -- registry, selectors, and source evidence

Evolve `DashboardKpi` and `DashboardViewModel` into the one immutable registry/state lineage. Add
closed KPI state/action/filter/evidence values. Extend `TenderRepository` and
`BusinessMetricsRepository` through existing APIs/selectors to return exact typed values and stable
contributor IDs. Remove the tender-analysis profit fallback and tender component of attention.

Likely production files:

- `app/ui/viewmodels/dashboard_viewmodel.py`
- `app/repositories/tenders.py`
- `app/repositories/business_metrics.py`
- existing domain/query helpers only if the audited owner requires them.

Commit intent: `feat(rm-145): define truthful KPI registry and evidence`.

Rollback: revert the commit; no data migration exists. Stop if exact selectors require schema or
dependency changes, provider calls, float money in the KPI contract, or changed RM-107 authority.

## Phase 5 -- source-aware atomic refresh

Update the existing Dashboard controller/builder, demo path, and page consumer to use the registry,
injected aware clock, ten-minute freshness policy, per-source failure isolation, prior-evidence
retention, and one atomic view-model publication. Eliminate UI parsing of formatted KPI strings.
Preserve generation/lifecycle guards and bounded shutdown.

Likely production files:

- `app/ui/controllers/dashboard_controller.py`
- `app/ui/dashboard/demo_data.py`
- `app/ui/pages/dashboard_page.py`
- `app/ui/dashboard/data_state.py` and `kpi_center.py` only for presentation/interaction integration.

Commit intent: `feat(rm-145): publish source-aware dashboard snapshots`.

Rollback: revert the commit. Stop if observers can see mixed generations, a render timestamp becomes
source evidence, one source blocks unrelated KPI cards, or ZERO can hide missing/failed data.

## Phase 6 -- typed drill-down and presentation

Add the closed Dashboard filter to the accepted route context, connect typed KPI actions in the
existing shell, and let the existing tender/workflow destinations apply exact selectors/IDs. Refine
cards with RM-143 tokens for state, freshness, focus, accessible descriptions, and supported density.
Do not add charts, analytics, a route, page, repository, controller, or theme owner.

Likely production files:

- `app/ui/navigation/contracts.py` and existing registry validation;
- `app/ui/modern_main_window.py`;
- `app/ui/pages/tender_workspace_page.py`;
- `app/ui/pages/business_workflow_page.py` and its existing model/proxy;
- `app/ui/dashboard/kpi_center.py` and token/theme files only where the accepted owner requires it.

Commit intent: `feat(rm-145): connect exact KPI drilldowns`.

Rollback: revert this commit; route/filter state is presentation-only. Stop if value/filter sets
diverge, formatted strings determine navigation, or routing begins calculating domain membership.

## Phase 7 -- acceptance and no-duplicate evidence

Run focused RM-145 tests plus neighboring RM-107, RM-127/128, RM-140, RM-142, RM-143, RM-144,
Dashboard, workflow, navigation/history, bootstrap, offline, migration/schema, build/frozen, and
release selections. Run full pytest, Ruff check/format, mypy, secret scan, `pip-audit`, public-import
and composition smokes, and `git diff --check`. Record exact results in
`docs/RM-145_ACCEPTANCE.md` and canonical roadmap documents only after all gates pass.

Mandatory no-duplicate searches must prove one six-entry registry, one Dashboard controller/page,
one route registry/layout/theme owner, no unknown filter/action strings, no `datetime.now()` in the
new KPI path, no formatted-value parsing, no `float` KPI money, and no new DB/dependency/provider
surface.

Commit intent: `test(rm-145): prove dashboard acceptance`.

Rollback: revert acceptance/doc updates if evidence is incomplete. Stop on any unexplained existing
failure, parity mismatch, lifecycle regression, duplicate owner, secret, vulnerability, or diff
hygiene failure.

## Phase 8 -- feature PR, exact merge gate, and closeout

After local gates pass, present exact evidence and request authorization before push/PR. Feature PR
CI must pass on the exact feature SHA. Merge only with explicit authorization. Then fast-forward a
fresh closeout branch/worktree from the verified `origin/main` merge SHA, update STATUS/ROADMAP/
HISTORY and acceptance evidence in a docs-only closeout commit, and run the full exact-SHA gate
again. Do not start RM-146 before the RM-145 Definition of Done and canonical closeout are complete.

No push, PR, merge, release, or external message is implicit in this plan.
