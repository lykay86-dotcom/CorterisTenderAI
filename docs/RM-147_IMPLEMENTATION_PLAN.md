# RM-147 implementation plan

## Scope and baseline

Close only `UI-141-008` from exact RM-146 closeout baseline
`570ef10b9ea0666a09aa267cbcb47bab8882f401`. Preserve RM-140 search lifecycle, RM-142 typed
navigation/history/context, RM-143 design ownership, RM-144 shell/lifecycle, RM-145 Dashboard
semantics, RM-146 chart contracts/limits, all repository persistence, and RM-107 deterministic
score/recommendation/critical stop-factor authority.

No RM-148 financial metric or RM-149+ redesign work is authorized.

## Phase 1 — docs-first gate

Commit only these seven files:

- `docs/RM-147_TENDER_ANALYTICS_AUDIT.md`
- `docs/RM-147_SOURCE_OF_TRUTH_DECISION.md`
- `docs/RM-147_METRIC_CATALOG.md`
- `docs/RM-147_TIME_FILTER_CONTRACT.md`
- `docs/RM-147_PROVENANCE_PARTIAL_CONTRACT.md`
- `docs/RM-147_DRILLDOWN_EXPORT_MATRIX.md`
- `docs/RM-147_IMPLEMENTATION_PLAN.md`

Intent: `docs(rm-147): audit tender analytics contracts`.

Confirm the commit contains documentation only and the worktree is clean afterward. Do not modify
application code or add expected-red tests before this commit exists.

## Phase 2 — passing characterization

Add a separate passing commit covering the exact baseline:

- registry record identity, search/count ordering/limits, payload restore, first/last seen behavior;
- collector source references, provider outcomes, provenance, candidates, resolutions, conflicts,
  verification and freshness queries;
- existing deadline normalization and naive/aware timestamp behavior;
- `TenderRegistryDialog` selection/actions and controller-owned `open_registry_dialog`;
- planned `RouteId.FUTURE_ANALYTICS`, alias, one route registry/stack/shell;
- RM-145 source evidence, monotonic/atomic Dashboard precedent without reusing ORM data;
- RM-146 public chart model, selection, text, data/visual exports, limits;
- production/frozen composition and absence of another chart/dependency.

Suggested files: `tests/test_rm147_characterization.py` and focused existing-test extensions only
where the owner is already established.

Intent: `test(rm-147): characterize tender analytics owners`.

## Phase 3 — expected-red contracts

Add the required failing contracts in a separate commit. Red must be exclusively the absent RM-147
public symbols/behavior:

1. exact metric catalog IDs/versions/order;
2. half-open aware day/week/month buckets and exact boundaries;
3. TA-01 `first_seen_at` only;
4. TA-02 current normalized status including unknown;
5. UTC instant in the correct local day;
6. naive legacy time remains unknown;
7. failed source is partial, not zero;
8. stale retained snapshot preserves original observation time;
9. unresolved conflict remains visible;
10. shuffled input yields identical points/order/export;
11. selection contains exact contributors;
12. drill-down preselects exact `registry_key`;
13. export uses displayed fingerprint and never re-queries;
14. chart adapter performs translation only;
15. canonical route registry/shell owns activation;
16. score/recommendation/critical stop-factor behavior is unchanged.

Suggested focused files follow the specification:

```text
tests/test_rm147_metric_catalog.py
tests/test_rm147_time_contract.py
tests/test_rm147_aggregation.py
tests/test_rm147_provenance_partial.py
tests/test_rm147_conflict_semantics.py
tests/test_rm147_determinism.py
tests/test_rm147_chart_adapter.py
tests/test_rm147_navigation_drilldown.py
tests/test_rm147_keyboard_accessibility.py
tests/test_rm147_export_parity.py
tests/test_rm147_lifecycle.py
tests/test_rm147_performance_contract.py
tests/test_rm147_frozen_smoke.py
```

Intent: `test(rm-147): add expected-red analytics contracts`.

Stop if any red maps to a migration, new dependency, financial metric, another owner, live I/O, or
an inherited regression.

## Phase 4 — pure contracts, catalog, and repository reads

Create a cohesive `app/tenders/analytics/` package containing Qt-free frozen contracts, metric
catalog, interval/query normalization/fingerprinting, source read DTOs, service, chart adapter, and
exporter. Exact module split may be smaller where cohesion improves.

Extend `TenderRegistryRepository` and `CollectorStateRepository` only with narrow read-only typed
snapshot selectors needed to avoid UI/service SQL and 1,000-row UI pagination. Reads must preserve
deterministic ordering, passive missing-database behavior, safe error classification, and existing
schema. Reuse canonical payload restoration and existing freshness/conflict owners.

Intent examples:

- `feat(rm-147): define immutable analytics contracts`
- `feat(rm-147): expose registry analytics read snapshots`

Stop for schema/cache/write needs, direct SQL outside repositories, ORM ID bridge, or duplicated
freshness/source policy.

## Phase 5 — deterministic service and exports

Implement `TenderAnalyticsService` as the only metric owner:

- validate/canonicalize the query and capture injected aware `as_of`;
- filter existing typed facts without fallback timestamps;
- build TA-01--TA-04 with exact contributors/evidence/state/order;
- generate stable point IDs and semantic snapshot fingerprint;
- reject unsupported filters/metrics and explicit size limits safely;
- retain last-known snapshots only in the controller/view-model, not a persistent cache.

Implement deterministic JSON/CSV from a supplied frozen snapshot only, including formula/bidi/
control protection and safe filenames. Add atomic file writing at the UI/application boundary.

Intent: `feat(rm-147): aggregate and export tender analytics`.

## Phase 6 — RM-146 adapter, view model, controller, and page

Implement a translation-only adapter to RM-146 and one UI lineage:

- `TenderAnalyticsViewModel` owns the displayed snapshot, chart specs, selection, and atomic state;
- `TenderAnalyticsController` owns injected repositories/service, monotonic generations, one owned
  worker boundary if measurements require background work, late-result rejection, safe errors, and
  idempotent shutdown following RM-144;
- `TenderAnalyticsPage` owns draft/applied filters, source banner, four chart/text equivalents,
  selection summary, exact contributor list, and export intents;
- charts use `ChartWidget`; no painter/widget/backend is copied;
- theme uses RM-143 tokens and existing chart palette; no unregistered literal/local style.

Initial refresh and every manual refresh read local persisted state only. No Collector/provider/
network execution occurs. Export is disabled during initial loading; if a previous snapshot remains
visible, the UI labels and exports that exact displayed snapshot.

Intent: `feat(rm-147): present accessible tender analytics`.

## Phase 7 — route and exact registry drill-down

In the canonical registry only, convert `FUTURE_ANALYTICS` to the available fourth primary route,
retain `future.analytics` and `analytics`, and set destination `analytics`. Add one physical page,
one handler/context provider, and once-only shutdown in `ModernMainWindow`.

Extend the existing route context with a bounded closed analytics query representation sufficient
for back/return. Do not serialize arbitrary mappings or start work during route resolution.

Add the narrow exact preselection seam to the existing `TenderRegistryDialog` and
`TenderSearchUiController`. The shell/page routes contributor activation to the installed controller;
no new registry dialog/controller or ORM translation is allowed.

Intent: `feat(rm-147): connect analytics route and drilldown`.

## Phase 8 — performance, frozen, and acceptance

Add `scripts/benchmark_rm147_analytics.py` or an equivalent deterministic runner. Measure synthetic
0/1/10/100/1,000/10,000 inputs, both ordered and shuffled, with warmups and at least ten timed
samples. Record aggregation/snapshot/adapter/render/selection p50/p95, query count, contributor
identity memory, peak traced/process memory where available, and JSON/CSV sizes. No silent sampling
or arbitrary workstation SLA; explicit limits and `TOO_LARGE` are enforced.

Extend the existing frozen self-test to import/aggregate/adapt/export one synthetic analytics
fixture offline if this is needed to prove packaging. Do not read live user data or commit binaries.

Run focused RM-147 tests and the exact neighboring contour discovered by `rg`: registry, collector
store/outcomes/freshness/verification/conflicts, RM-137/139/140 time/source lifecycle, RM-142 route/
history/security, RM-143 design guard, RM-144 shell/lifecycle, RM-145 Dashboard source/drilldown,
all RM-146 chart/export/accessibility/performance tests, bootstrap, build, and frozen tests.

Then run the workflow-equivalent local gate derived from `pyproject.toml` and
`.github/workflows/quality-gate.yml`:

```powershell
python scripts/check_repository_secrets.py
python -m ruff check .
python -m ruff format . --check
python -m mypy
python -m pytest -q tests/test_collector_provider_control.py::test_manager_exposes_all_sources_without_network tests/test_mos_supplier_diagnostic_script.py::test_mos_diagnostic_runs_from_scripts_path_without_app_error
python -m pytest -q tests/test_database_migrations_121.py tests/test_collector_schema_contract.py
python -c "from app.ui.controllers import DashboardController; print(DashboardController.__name__)"
python -m pytest -q tests/test_bootstrap_tender_search_integration.py
python -m pytest -q tests/test_build_release_contract.py tests/test_frozen_self_test.py
python -m pytest -q
python -m pip_audit --skip-editable
python -m scripts.check_design_system --format summary
python -m scripts.audit_ui_inventory --format summary
git diff --check
```

Use a repository-local isolated pytest base temp if host `%TEMP%` is unavailable. Record exact
commands, counts, warnings, durations, environment, benchmark data, no-duplicate searches, and any
honest `NOT_EXECUTED` native evidence in `docs/RM-147_ACCEPTANCE.md`.

## Phase 9 — publication and closeout

After local acceptance, present evidence and request explicit authorization before push/PR. Require
Windows Python 3.12/3.13 Quality Gate on the exact final feature head. Merge only with explicit
authorization, then verify the exact feature merge-SHA gate. Only afterward create a separate
docs-only closeout that marks RM-147 `DONE` and activates RM-148.

No push, PR, merge, release, canonical status transition, or RM-148 work is implicit.

## Global stop and rollback

Stop on any unexplained test failure, new warning/vulnerability, secret/privacy leak, duplicate
owner, unsafe export, parity mismatch, mixed generation, worker/lifecycle leak, route/history break,
frozen failure, live I/O, identity ambiguity, schema/dependency need, or changed deterministic
decision semantics.

Rollback is the ordered revert of RM-147 commits to the exact baseline. There is no database,
settings, credential, schedule, or user-data downgrade.
