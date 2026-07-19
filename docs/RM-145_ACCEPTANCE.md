# RM-145 modern Dashboard acceptance

## Package status

Local feature implementation and acceptance for `UI-141-006` are complete on dedicated branch
`feat/rm-145-modern-dashboard`. Publication, PR-head CI, merge, exact merge-SHA CI, and the separate
docs-only canonical closeout remain pending explicit authorization. RM-145 therefore remains the
sole `IN PROGRESS` stage; RM-146 has not started.

## Entry gate and traceability

- Exact baseline: RM-144 docs-only closeout merge
  `78141ff2764aa3b28facb80b332588b0cfaaeb45`, PR #97.
- RM-144 feature merge: PR #96,
  `491b13a0b5e5dd204bf00faba09fa513c5f9de3b`.
- Exact RM-144 feature/closeout Quality Gate runs `29666054057` and `29666535498` succeeded on
  Windows Python 3.12/3.13.
- Baseline full suite before RM-145 changes:
  `2073 passed, 2 warnings in 179.66s (0:02:59)`.
- Audit-first docs-only commit: `89d8346`.
- Passing characterization commit: `3e2ae9a`, `5 passed`.
- Expected-red commit: `3db1cbe`, eight failures exclusively for the absent KPI registry,
  evidence/state/action, exact contributors, and closed route filters.
- Truthful registry/evidence implementation: `b161b8b`; the new contract and characterization
  selection passed `13/13`.
- Source-aware atomic snapshot implementation: `c4b2c96`.
- Typed exact drill-down implementation: `248e946`; destination/navigation contour passed `27/27`.
- Compatibility correction found by full-suite acceptance: `f15cdda`.
- Repeated-failure freshness correction: `5754df1`; source-state contour passed `5/5`.

The root checkout's unrelated untracked `.agents/` and `skills-lock.json` were not changed. All
repository-local pytest temporary directories were removed after their runs.

## Accepted KPI registry

`DashboardKpi` remains the sole immutable Dashboard KPI value lineage. One tuple registry and one
read-only key map own exactly six stable keys in the accepted order. Raw money is `Decimal`; raw
counts are `int`; missing is `None`, never zero.

| Stable key | Truthful meaning | Source owner | Typed destination/filter |
|---|---|---|---|
| `potential_profit` | Exact workflow potential-profit contributor sum | `BusinessMetricsRepository` | workflow / `workflow_profit_contributors` |
| `new_tenders` | All active tenders created in the injected local day | `TenderRepository` selector | tenders / `tenders_created_today` |
| `recommended` | Numeric score cohort `>= 80`, titled “Оценка 80+” | `TenderRepository` selector | tenders / `tenders_score_80_plus` |
| `proposals_in_work` | Proposal statuses DRAFT/REVIEW/READY/SENT | `BusinessMetricsRepository` | workflow / `workflow_active_proposals` |
| `active_projects` | Project statuses PLANNED/ACTIVE/INSTALLATION/COMMISSIONING | `BusinessMetricsRepository` | workflow / `workflow_active_projects` |
| `attention` | Workflow records blocked or due in zero to three days | `BusinessMetricsRepository` | workflow / `workflow_attention` |

Tender-analysis profit fallback and tender-deadline contribution to the KPI `attention` were
removed. They represented different populations and could not support truthful exact drill-down.
The stable key `recommended` is retained only for compatibility. Its visible/accessibility text
explicitly says the score cohort is not a recommendation and does not cancel critical stop factors.
No score, RM-107 recommendation, or stop-factor priority logic changed.

## Accepted source, state, and time behavior

- The controller injects an aware application clock and captures source/snapshot evidence in the
  Europe/Moscow application zone. Render/setter time is not source time.
- Complete fresh zero is `ZERO`; fresh non-zero is `READY`; missing with no usable prior value is
  `ERROR` and displays an em dash.
- A failed source retains its last usable raw value and original observation time as `PARTIAL` for
  up to ten minutes, then `STALE`. Repeated failed refreshes do not reset that age.
- Tender-source failure affects only `new_tenders` and `recommended`. Workflow-source failure
  affects the other four cards. The successful source publishes its new generation normally.
- One ViewModel apply operation replaces all six KPIs, recent tenders, advisor messages, and source
  timestamp before one `state_changed` publication. Legacy narrow setters remain compatibility
  seams but production refresh/demo paths use the atomic operation.
- The Dashboard query is no longer capped at 100. Acceptance covers 101 same-day tenders and a UTC
  timestamp crossing the Moscow calendar boundary.
- Demo data is normalized to aware time, carries explicit `DEMO` evidence, uses the registry and
  truthful score label, and has no live drill-down action.

## Accepted drill-down and accessibility

- Cards emit immutable `DashboardKpiAction`, never a string key. Each action contains an existing
  `RouteId`, one closed `DashboardFilterId`, and focus token.
- `RouteContext` validates and round-trips the filter. The existing route registry rejects a tender
  filter on workflow and vice versa; the router does no domain calculation.
- The existing tender page applies the same repository selector as the value builder. The existing
  workflow page restricts its existing proxy to the exact contributor IDs emitted by
  `BusinessMetricsRepository.summary()`.
- Count parity is stable-ID set equality. Profit parity is the exact `Decimal` total for the visible
  contributor set, including one-record-per-tender and active-project priority.
- Mouse, Enter, and Space activation share the typed action. LOADING/ERROR are disabled;
  READY/ZERO/PARTIAL/STALE remain actionable. Accessible name contains title/exact value; accessible
  description includes source, state, freshness limitation, and the score-cohort disclaimer.
- State is communicated by text/semantics as well as tone. Existing RM-143 theme tokens and
  RM-144 layout/lifecycle owners remain unchanged; no chart or RM-146 analytics surface was added.

## Local test evidence

Environment: Windows, repository Python 3.12 virtual environment, offscreen Qt, temporary local
repositories/fake adapters, and isolated repository-local pytest bases.

| Contour | Exact result |
|---|---|
| RM-145 contract + characterization | `13 passed in 4.70s` |
| neighboring Dashboard/repository/navigation selection | `53 passed in 16.33s` |
| source isolation/freshness final selection | `5 passed in 1.25s` |
| typed destination/navigation selection | `27 passed in 18.23s` |
| final Dashboard/source/drill-down selection | `31 passed in 6.66s` |
| full `python -m pytest tests -q` | `2094 passed, 2 warnings in 187.89s (0:03:07)` |

The two warnings are the unchanged openpyxl unsupported-extension and conditional-formatting
warnings in `test_rm132_legacy_credentials_handoff.py`. RM-145 adds no warning. The suite increased
by 21 tests covering characterization, expected-red contracts now green, state/freshness, exact
contributors, uncapped timezone-aware tender filtering, typed routing, scope restoration, and
keyboard activation.

## Local Quality Gate and CI-equivalent evidence

| Command/step | Result |
|---|---|
| `python scripts/check_repository_secrets.py` | passed |
| `python -m ruff check .` | passed |
| `python -m ruff format . --check` | `670 files already formatted` |
| `python -m mypy` | success, 20 source files |
| offline credential + migration/schema + composition smokes | `8 passed in 19.17s` |
| public controller import | `DashboardController` |
| release/build/frozen smoke | `6 passed in 10.29s` |
| `python -m pip_audit --skip-editable` | no known vulnerabilities; editable project skipped |
| `python -m scripts.check_design_system --format summary` | `matrix=45; styles=43; violations=0` |
| `python -m scripts.audit_ui_inventory --format summary` | 78 modules, 31,612 lines, 123 UI test modules, no literal colours outside theme |
| `git diff --check` | passed |

The first full-suite command was intentionally bounded at 120 seconds and was terminated at 75%
after exposing one compatibility failure. A focused reproduction identified a legacy manually
constructed card whose explicit value remained disabled after global loading. Commit `f15cdda`
restored safe compatibility, the focused contour passed `9/9`, and the complete rerun passed all
2094 tests. This was a real acceptance finding, not omitted evidence.

## No-duplicate and change-surface evidence

- Search finds one `DASHBOARD_KPI_REGISTRY` assignment, one Dashboard controller, one Dashboard
  page, one route registry, one shell layout and the accepted theme owners.
- No `AI рекомендует` label, analysis-profit fallback, formatted-value digit parsing, unknown
  Dashboard action/filter string, second Dashboard DTO/controller/builder/repository, or live
  provider call remains in the RM-145 path.
- The diff adds no dependency, lockfile, migration, database model/table, schema version, provider,
  AI decision rule, chart, analytics page, route owner, event bus, or DI container.
- `BusinessMetricsRepository`, `TenderRepository`, `DashboardController`, `DashboardViewModel`,
  `DashboardPage`, `ModernMainWindow`, `TenderWorkspacePage`, `BusinessWorkflowPage`, their existing
  proxy/model, and RM-142 route contracts remain the only production owners.

## Business/data boundaries and rollback

The JSON workflow schema and SQL database schema are unchanged. Contributor IDs are derived
evidence from existing records and are not persisted. Route/filter state is presentation-only.
There is no settings, credential, schedule, database, or provider migration and therefore no data
downgrade procedure.

Rollback is a revert of the RM-145 feature commits to exact baseline `78141ff`; persisted user data
does not require conversion. Stop publication on any parity mismatch, duplicate owner, new warning,
secret/vulnerability, failed Python 3.12/3.13 gate, or unexplained lifecycle/navigation regression.

Local DoD verdict: the feature implementation satisfies the local RM-145 acceptance contract.
Final Definition of Done remains pending feature PR-head CI, explicit merge authorization, exact
merge-SHA CI, and the separate docs-only canonical closeout.
