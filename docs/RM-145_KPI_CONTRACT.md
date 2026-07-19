# RM-145 KPI contract

## Contract identity and ownership

Contract version: `dashboard-kpi-v1`.

`app.ui.viewmodels.dashboard_viewmodel.DashboardKpi` remains the single immutable value DTO
lineage. The same module owns the closed registry, state enum, source evidence, formatting metadata,
and typed action value. `DashboardController` remains the assembly owner; repositories remain the
calculation/query owners; widgets remain presentation consumers.

The registry contains exactly these stable keys, in this order:

1. `potential_profit`
2. `new_tenders`
3. `recommended`
4. `proposals_in_work`
5. `active_projects`
6. `attention`

Ad hoc definitions, duplicate demo/zero definitions, unknown keys, and presentation-side formulas
are contract violations.

## Value and state types

- Count raw values are `int` and non-negative.
- Money raw values are `Decimal`, never binary floating-point presentation values.
- A missing value is `None`; it is never coerced to `0` or `Decimal("0")`.
- Formatting is metadata-driven and occurs only after the raw value is fixed.
- Each KPI carries immutable source evidence, completeness, freshness, state, and typed action.
- One immutable Dashboard view state contains all six KPIs and auxiliary recent-activity data.

Closed states and precedence:

1. `LOADING`: initial/current generation has no published usable result.
2. `ERROR`: required current source failed and no usable prior value exists.
3. `STALE`: a usable prior value exists but its evidence age exceeds ten minutes.
4. `PARTIAL`: a usable value exists but the current source is incomplete, or a refresh failed while
   prior fresh evidence is retained.
5. `ZERO`: complete fresh evidence proves an exact numeric zero.
6. `READY`: complete fresh evidence proves a non-zero value.

`UNAVAILABLE` is intentionally excluded because the audited product supports every registry entry.

## Time and freshness

- The application clock is injected and returns timezone-aware datetimes.
- `observed_at` is captured by the controller around the repository snapshot operation; it is not a
  widget-render or setter time.
- The local-day calculation uses the injected application timezone (`Europe/Moscow` at acceptance)
  and explicitly normalizes stored datetimes.
- Freshness threshold is ten minutes, twice the accepted five-minute Dashboard auto-refresh period.
- Age is evaluated against the injected clock and source evidence, so tests do not sleep.
- A snapshot is published atomically. Every KPI in one publication refers to the same refresh
  generation even when individual source evidence has different completion timestamps.

## Source evidence

Each source evidence value contains at least:

- stable source ID (`tenders` or `business_workflow`);
- refresh generation;
- timezone-aware `observed_at`;
- record count inspected and stable contributor IDs;
- completeness flag;
- current failure/fallback flag and safe reason, if any.

Contributor IDs are evidence, not a second calculation owner. They are emitted by the same selector
that calculates the value and are used for exact drill-down tests and filters.

## Registry definitions

| Stable key | Display title | Raw/unit | Formula version and owner | Zero and missing | Typed action |
|---|---|---|---|---|---|
| `potential_profit` | Потенциальная прибыль | `Decimal`, RUB | `workflow-potential-profit-v1`, `BusinessMetricsRepository` | Complete empty/zero contributors = ZERO; failed/no prior = missing ERROR | workflow / `workflow_profit_contributors` |
| `new_tenders` | Новые тендеры сегодня | `int`, count | `tender-created-local-day-v1`, `TenderRepository` selector | Complete empty = ZERO; incomplete/failed follows state precedence | tenders / `tenders_created_today` |
| `recommended` | Оценка 80+ | `int`, count | `tender-score-threshold-v1`, `TenderRepository` selector | Complete empty = ZERO; missing scores are excluded | tenders / `tenders_score_80_plus` |
| `proposals_in_work` | Предложения в работе | `int`, count | `workflow-active-proposals-v1`, `BusinessMetricsRepository` | Complete empty = ZERO | workflow / `workflow_active_proposals` |
| `active_projects` | Активные проекты | `int`, count | `workflow-active-projects-v1`, `BusinessMetricsRepository` | Complete empty = ZERO | workflow / `workflow_active_projects` |
| `attention` | Workflow: требуют внимания | `int`, count | `workflow-attention-v1`, `BusinessMetricsRepository` | Complete empty = ZERO | workflow / `workflow_attention` |

### `potential_profit`

Select non-archived workflow records that are neither cancelled nor completed and have positive
potential profit. Select at most one contributor per tender; an active project is authoritative over
another record for the same tender. The KPI is the exact `Decimal` sum of selected contributor
profits. Tender-analysis fallback is removed because it creates another population and breaks exact
drill-down. Existing legacy storage conversion is contained at the repository boundary; RM-145 does
not change the schema.

### `new_tenders`

Select all active tender entities whose normalized `created_at` belongs to the injected current
local calendar day. The source must not use the current `limit=100` Dashboard projection. The raw
value is the size of the exact stable-ID set.

### `recommended`

Select active tenders with an existing numeric score greater than or equal to 80. The stable key is
retained for compatibility, but the visible and accessible label is “Оценка 80+”. This is a numeric
cohort only. It does not call AI, read or replace the approved RM-107 recommendation, suppress
critical stop factors, or assert that the operator should bid.

### `proposals_in_work`

Select non-archived proposal records in `DRAFT`, `REVIEW`, `READY`, or `SENT`.

### `active_projects`

Select non-archived project records in `PLANNED`, `ACTIVE`, `INSTALLATION`, or `COMMISSIONING`.

### `attention`

Select non-archived workflow records that are blocked or have a due date from today through three
local calendar days ahead, using the existing repository predicate. Tender deadline heuristics are
excluded. This is audited option C: one truthful workflow population with one exact drill-down.

## Formatting and presentation

- `RUB` uses the existing localized money formatter with no loss of raw `Decimal` precision.
- Counts use the existing localized integer formatter.
- Compact visual formatting may be shown only alongside an exact accessible value.
- Trend text is explanatory metadata, not a hidden calculation.
- The card accessible name contains title and exact formatted value. The description contains state,
  freshness/source summary, and the score-cohort disclaimer where applicable.
- READY/ZERO/PARTIAL/STALE cards expose the typed action. LOADING/ERROR cards do not activate.
- State must not rely on color alone; text/icon semantics and keyboard focus are required.

## Atomic publication and failure rules

The controller builds the complete immutable view state off-screen and calls one view-model apply
operation. A signal observer must never see a new KPI beside old activity or timestamp data.

Source failures are isolated:

- a tender-source failure affects only `new_tenders` and `recommended`;
- a workflow-source failure affects the other four KPIs;
- a fresh prior value is retained as PARTIAL with explicit failure evidence;
- an aged prior value is STALE;
- absence of any usable value is ERROR with `raw_value=None`;
- ZERO is emitted only from successful complete evidence.

Demo snapshots use explicit `DEMO` evidence and deterministic injected time. Demo is never presented
as a live repository observation.

## Compatibility boundary

The change is additive to accepted route context and evolutionary to `DashboardKpi`. Compatibility
helpers may remain temporarily for tests/callers, but production assembly must use the registry and
atomic path. No alternate public Dashboard controller, DTO, builder, route registry, or repository
may be introduced.
