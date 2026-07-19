# RM-147 tender analytics audit

## Verdict

RM-147 can close `UI-141-008` by extending the existing local tender-registry graph. The accepted
read model is `TenderRegistryRepository` plus the related `CollectorStateRepository`, both over the
same `tender_registry.sqlite3`. The aggregation owner will be one pure `TenderAnalyticsService`.
The existing RM-146 `app.ui.charts` package remains the only chart implementation, and the existing
RM-142 registry and RM-144 shell remain the only navigation/composition owners.

No schema migration, new table, materialized cache, dependency, provider call, AI calculation,
second repository, router, chart backend, theme root, event bus, or DI container is required.
Financial analytics and all RM-148+ redesign work remain excluded.

## Entry gate and baseline

- Audit date: 2026-07-19; Windows 10, Europe/Moscow.
- Exact baseline: RM-146 docs-only closeout merge
  `570ef10b9ea0666a09aa267cbcb47bab8882f401`.
- RM-146 feature PR #100 merged as
  `e09af67931c3a63874e259bed08efc5ce3a14284`; exact merge-SHA Quality Gate run
  `29686798140` succeeded on Windows Python 3.12 and 3.13.
- RM-146 closeout PR #101 merged as the baseline above; exact closeout run `29688334074`
  succeeded on Windows Python 3.12 and 3.13. The final rerun retained the same closeout SHA.
- Canonical documents mark RM-146 `DONE`, RM-147 as the sole `IN PROGRESS` stage, and
  RM-148--RM-200 `PLANNED`.
- Dedicated branch/worktree: `feat/rm-147-tender-analytics`, `.worktrees/rm147`, created from the
  exact baseline. The root checkout's untracked `.agents/` and `skills-lock.json` are excluded.
- All canonical documents, the RM-147 specification, and RM-141--RM-146 audit, contract, plan, and
  acceptance records were read before this decision.

## Mandatory search evidence

The prescribed repository searches were run across `app`, `tests`, `scripts`, and
`pyproject.toml`. They found 82 files for registry identity/queries, 53 for collector
provenance/conflicts, 49 for source/freshness observations, 173 for time/deadline semantics, 18 for
navigation/analytics routing, 41 for chart/export contracts, 129 for score/recommendation/critical
stop factors, and 74 for the two tender repository lineages.

The only match for `QChart|QtCharts|QtGraphs|pyqtgraph|matplotlib|plotly` is the RM-146 negative
characterization test. `pyproject.toml` contains PySide6 but no second chart framework. Existing
chart code is confined to the accepted `app.ui.charts` package plus frozen diagnostics.

## Store and identity inventory

### Canonical analytics source

`TenderRegistryRepository` owns `tender_records` and exposes `TenderRegistryRecord` with stable
`registry_key`, procurement number, current source/status, first/last seen timestamps,
`seen_count`, archive flag, and canonical payload. `registry_key` is the table primary key and the
same identity used by collector aliases, source observations, versions, conflicts, verification,
freshness, documents, analysis, scoring, and current Tender Registry actions.

`CollectorStateRepository` uses the same file and already exposes:

- safe persisted `list_provider_outcomes()` records;
- exact `list_sources(registry_key)` source references;
- persisted freshness and verification state lists;
- `list_field_provenance()`, `list_field_conflicts()`, `list_field_candidates()`, and
  `list_field_resolutions()`;
- collector runs, observations, checkpoints, and safe source-monitoring inputs.

The source tables already contain the facts needed by the four mandatory metrics. Existing
read-only selectors are currently row-oriented and bounded for registry UI use, so a narrow typed
analytics read snapshot may be added to these existing repository classes. It must not create a
new physical repository or write/migrate state.

### Rejected SQLAlchemy lineage

`app.repositories.tenders.TenderRepository` owns ORM `Tender.id`, `created_at`, Dashboard score
cohorts, documents, and saved analyses in the application database. There is no audited exact
mapping from its integer/UUID-compatible ID to `TenderRegistryRecord.registry_key`. It also uses a
different creation-time definition from collector `first_seen_at`.

RM-147 therefore will not join, translate, or mix this lineage. No `TenderRepository` data enters
tender analytics and no `registry_key` is coerced into an ORM ID. A future bridge requires its own
audited identity protocol.

## Time, freshness, and conflict findings

- `tender_records.first_seen_at` is the only time owner for TA-01. `published_at` and
  `last_seen_at` are present but are forbidden fallbacks.
- Existing registry timestamps can contain legacy naive text. `legacy_timestamp_status()` already
  distinguishes explicit, unknown, and invalid time; RM-147 must leave naive values in explicit
  `unknown_time` evidence.
- `TenderFreshnessService.normalize_application_deadline()` already refuses to invent a timezone,
  preserves original/source timezone evidence, and produces UTC/user-local projections. TA-04 will
  reuse this policy rather than implement another deadline normalizer.
- Provider outcomes preserve run/provider identity, status, completion time, item count, elapsed
  time, and allowlisted error fields. `SourceMonitoringService` already classifies current/stale/
  invalid evidence and operational success/failure. Failure cannot be interpreted as a zero item
  result.
- Existing conflict APIs apply manual selection markers and expose unresolved conflicts. Analytics
  must not choose the latest candidate when a bucket-defining field remains unresolved.

## Current UI, navigation, and drill-down owners

- `RouteId.FUTURE_ANALYTICS == "future.analytics"` and alias `analytics` already exist. The route is
  currently `COMPATIBILITY`, `PLANNED`, has no destination, and is not visible in the Sidebar.
- RM-147 will reuse that stable ID and alias. In the canonical registry alone it becomes an
  `AVAILABLE` `PRIMARY` route with physical destination `analytics`, after Dashboard, Tenders, and
  Workflow. This is a deliberate fourth primary workspace because the product requirement is a
  separate persistent analytics section, not a tender modal or Dashboard duplicate.
- `DashboardLayout` remains the sole route activation/history/page-stack owner. The shell will add
  one physical `TenderAnalyticsPage`, one context provider, and one registered route handler.
- `TenderRegistryDialog` stores exact `registry_key` in table item data and preserves a selected key
  across refresh, but it has no public exact-preselection seam and otherwise selects row zero.
- `TenderSearchUiController.open_registry_dialog()` is the current dialog owner. RM-147 may add a
  narrow `open_registry_record(registry_key)` method and matching dialog selection method; it must
  not create another registry dialog/controller or open a source URL automatically.

## RM-145 and RM-146 reuse

RM-145 supplies the accepted aware-time/evidence and monotonic-generation precedent, but its
Dashboard ORM data and six KPI registry are not analytics inputs. RM-147 defines its own tender
analytics evidence while preserving source observation time and generation semantics.

RM-146 supplies immutable `ChartSpec`, `ChartSeries`, `ChartPoint`, states, selection, table,
normalizer/painter, and JSON/CSV/PNG/SVG functions. RM-147 will add only an adapter from already
aggregated analytics points. It will not query, filter, sort contributors, sample, or calculate in
the adapter. The RM-146 1,000-render/10,000-data limits and `TOO_LARGE` behavior remain authoritative.

## Approved owner graph

```text
TenderRegistryRepository + CollectorStateRepository
    -> typed read snapshot
TenderAnalyticsService
    -> immutable TenderAnalyticsSnapshot
TenderAnalyticsChartAdapter
    -> RM-146 ChartSpec / textual equivalent / visual export
TenderAnalyticsViewModel + controller
    -> generation, selection, lifecycle, atomic publication
TenderAnalyticsPage
    -> filters, state, charts, contributor list, export intents
DashboardLayout / ModernMainWindow
    -> the one route/page activation path
```

The service owns metric definitions, predicates, time buckets, state precedence, evidence, and
ordering. Repositories only read facts. The adapter only translates. The view model never computes
metrics. Widgets never query SQLite. Export consumes the displayed frozen snapshot.

## Change surface and exclusions

Expected production surface:

- new cohesive `app/tenders/analytics/` contracts/catalog/service/adapter/export modules;
- narrow read-only snapshot methods on the two existing repository classes;
- one page, view model, and controller under existing UI ownership;
- canonical route registry and production shell composition;
- narrow exact registry-record preselection seam;
- frozen diagnostic import/render extension only if required by acceptance.

Excluded: ORM tender data, DB/schema/migrations, materialized cache, financial values, currency,
rounding, score bands, recommendation logic, stop-factor changes, generic tables, notification
architecture, global performance budgets, visual goldens, cleanup/compatibility retirement, live
network/provider/credential/user data, and all RM-148+ work.

## Risks and stop conditions

Stop for an ambiguous identity bridge, required schema/dependency, second aggregation/chart/route/
theme owner, inability to retain exact contributors, unsafe/raw provider evidence, silent time-zone
fallback, source failure rendered as zero, unresolved conflict hidden, snapshot/export mismatch,
mixed generation, unexplained baseline regression, or any change to RM-107 authority.

## Audit decision

**ACCEPTED FOR DOCS-FIRST COMMIT.** Application and expected-red work may begin only after this
audit and the six companion decision/contract/plan documents are committed together as a
documentation-only commit.
