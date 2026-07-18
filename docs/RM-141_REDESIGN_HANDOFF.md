# RM-141 redesign handoff: RM-142–RM-155

## Rules for every package

Each stage starts only after the previous stage meets the repository Definition of Done and the
canonical status documents make it the sole `IN PROGRESS` stage. Existing adapters, analyzers,
orchestrators, repositories and dependency-injection paths are reused. UI/AI presentation must
never override approved score, recommendation, or critical stop-factor priority. Expected-red
contracts below are specifications; RM-141 did not add failing tests to main.

Every actionable finding appears under exactly one primary stage:

| Stage | Primary findings |
|---|---|
| RM-142 | UI-141-001, UI-141-002 |
| RM-143 | UI-141-003 |
| RM-144 | UI-141-004, UI-141-005 |
| RM-145 | UI-141-006 |
| RM-146 | UI-141-007 |
| RM-147 | UI-141-008 |
| RM-148 | UI-141-009 |
| RM-149 | UI-141-010 |
| RM-150 | UI-141-011 |
| RM-151 | UI-141-012 |
| RM-152 | UI-141-013, UI-141-014 |
| RM-153 | UI-141-015 |
| RM-154 | UI-141-016 |
| RM-155 | UI-141-017 |

## RM-142 — Information architecture

- Prerequisites: merged RM-141 audit and accepted J01–J16 as-is map.
- Work package: define route taxonomy, hierarchy, availability, titles, back/return behavior,
  selection/filter preservation and relation between global and embedded entry points.
- Exclusions: no design-system restyle, shell extraction, charts or domain ownership moves.
- Regression guards: all mature tender/workflow/settings/AI actions stay reachable; Dashboard quick
  actions and tender-ID deep links preserve identity; placeholder status is explicit.
- Expected-red: selecting each route returns a typed availability/state contract; navigation away
  and back preserves workflow filter/selection and focus origin.
- Acceptance: one route map covers sidebar/topbar/tabs/dialogs/shortcuts with no false peer route,
  and J03/J04/J08/J10/J12 pass offline.

## RM-143 — Design tokens and reusable components

- Prerequisites: stable RM-142 route/surface list.
- Work package: semantic colors, typography, spacing, radii, icon/resource fallback and reusable
  button/input/table/state contracts with dark/light focus/disabled/error parity.
- Exclusions: no navigation redesign, chart library or legacy extraction.
- Regression guards: object names used by tests/QSS, semantic status text and stored theme key.
- Expected-red: static inventory rejects new literal colors/local one-off state styles outside an
  approved exception list; component gallery asserts focus/disabled/loading/error in both themes.
- Acceptance: current 45 local style sites are assigned migrate/keep decisions; literal status
  colors and glyph-only controls have owned replacements/fallbacks.

## RM-144 — Production shell, composition and lifecycle

- Prerequisites: RM-142 routes and RM-143 components.
- Work package: converge on one explicit production shell/page composition, staged tender-page
  extraction, single service/repository ownership and worker/timer close protocols.
- Exclusions: do not rewrite search/domain services or retire public compatibility prematurely.
- Regression guards: RM-127 public import, all tender tabs/actions/shortcuts/settings, RM-140
  CLOSED/offline/shutdown, workflow safety backup semantics.
- Expected-red: repeated shell construct/close while workflow health runs emits no late signal;
  owner graph contains one instance where one is required and no nested `QMainWindow`.
- Acceptance: J01/J04/J07/J09/J13/J16 pass with no QObject/thread/timer growth and one documented
  lifecycle owner per controller/page.

## RM-145 — Dashboard jobs and KPI contract

- Prerequisites: RM-142/143/144 stable shell contracts.
- Work package: define Dashboard jobs-to-be-done, KPI identity/formula owner, source, unit,
  freshness, partial/error state, action and deterministic drill-down.
- Exclusions: no chart abstraction or tender/financial analytics implementation.
- Regression guards: snapshot/repository owners remain authoritative; no KPI calculation in widgets.
- Expected-red: every rendered KPI has definition/provenance/freshness and opens an exact route/filter.
- Acceptance: 0/partial/stale/error/success fixtures are understood without color alone and J01/J03
  preserve tender/workflow identity.

## RM-146 — Reusable interactive chart layer

- Prerequisites: RM-143 tokens and RM-145 metric semantics.
- Work package: select/implement chart abstraction with series contract, keyboard navigation,
  accessible textual equivalent, tooltip/selection, empty/error/stale, resize and export behavior.
- Exclusions: no new business KPI, tender aggregation or financial rounding policy.
- Regression guards: deterministic ordering and source values; dependency addition needs explicit audit.
- Expected-red: one deterministic fixture renders/exports identically, exposes accessible series
  text and supports keyboard selection in dark/light.
- Acceptance: resize/DPI/theme/large-series limits and artifact strategy are measured, not inferred.

## RM-147 — Tender analytics

- Prerequisites: RM-146 chart contract and existing search/provenance contracts.
- Work package: metric definitions, time interval/timezone, filter state, partial-source semantics,
  aggregation owner, confidence/provenance and tender-ID drill-down.
- Exclusions: never recompute/override approved score, recommendation or stop-factor priority in UI.
- Regression guards: source IDs, provider outcomes, freshness/conflict flags and deterministic order.
- Expected-red: fixed offline tender fixture produces exact series and each mark drills to the same ID.
- Acceptance: missing/partial/stale/conflicted sources remain visible and export matches the chart data.

## RM-148 — Financial analytics

- Prerequisites: RM-146 chart contract and repository/schema decision record.
- Work package: Decimal/currency/unit/rounding, interval, margin semantics, missing values,
  aggregation and export parity across workflow table, Dashboard and charts.
- Exclusions: no silent schema migration or float-to-Decimal compatibility assumption.
- Regression guards: existing workflow JSON/import/export, audit history and repository transactions.
- Expected-red: exact fractional currency fixtures sort, total, format and export with agreed rounding.
- Acceptance: a single owned numeric contract produces identical table/KPI/chart/export results.

## RM-149 — Tender card and detail hierarchy

- Prerequisites: RM-142 routes, RM-143 components, RM-147 tender semantics.
- Work package: reusable identity/status/provenance/decision/action hierarchy for feed, registry,
  results and detail/analysis entry points.
- Exclusions: no duplicate scoring or analysis engine and no loss of verification evidence.
- Regression guards: tender ID, source, conflicts, freshness, critical warnings and existing actions.
- Expected-red: the same fixture exposes the same approved decision and primary action on every surface.
- Acceptance: J03/J09/J11 work by keyboard, retain context and never encode critical status by color alone.

## RM-150 — Tables

- Prerequisites: RM-143 components plus stable tender/financial record contracts.
- Work package: common identity, model update, sorting/filtering, selection, keyboard/a11y,
  empty/loading/partial/stale/error and export parity; measured 0/100/1k/10k behavior.
- Exclusions: no business filtering/aggregation inside delegates and no arbitrary timing gate.
- Regression guards: stable row IDs, selected destructive target, deterministic ordering and actions.
- Expected-red: selection survives refresh/filter when identity remains; 10k fixture has recorded p50/p95
  and bounded UI-thread work; model and export ordering agree.
- Acceptance: each of 30 legacy table sites has migrate/keep rationale and representative table
  journeys pass keyboard/screen-reader inspection.

## RM-151 — Background episodes, notifications and safe feedback

- Prerequisites: RM-143 states and RM-144 lifecycle ownership.
- Work package: unified operation episode (idle/running/partial/success/failure/cancelled/closed),
  safe summaries, escaped rich text, diagnostic correlation, retry/cancel and notification routing.
- Exclusions: no suppression of actionable diagnostic artifacts and no exposure of secrets/paths.
- Regression guards: RM-140 search states/redaction, scheduler notifications, crash/support workflow.
- Expected-red: exceptions containing a fake secret, local path, URL query and HTML never appear in
  user text while safe diagnostic retrieval remains possible.
- Acceptance: J02/J07/J08/J10/J13/J15 have consistent terminal/recovery behavior and accessible updates.

## RM-152 — Accessibility, keyboard, focus, contrast and DPI

- Prerequisites: stable RM-142–RM-151 surfaces and components.
- Work package: full Tab/Shift+Tab order, Enter/Space/Escape, labels/buddies/names/descriptions,
  dialog focus return, contrast/high-contrast, screen reader and required native scaling matrix.
- Exclusions: do not claim WCAG from static counts or offscreen screenshots alone.
- Regression guards: existing shortcuts, visible labels, route identity, minimum user workflows.
- Expected-red: automated focus traversal plus documented native Windows manual cases at 1366x768
  through 4K/200%, dark/light, Russian growth and multi-monitor scale changes.
- Acceptance: no keyboard trap/clipping/overlap, visible focus everywhere, status not color-only, and
  `NOT_EXECUTED` cells require an explicit approved exception rather than an inferred pass.

## RM-153 — Profiling and performance budgets

- Prerequisites: RM-144 ownership and RM-150 table contract.
- Work package: measure startup/window/first paint, page switch, tender workspace, Dashboard refresh,
  tables, theme, dialog cycles, progress updates, shutdown, QObject/thread/timer growth and memory.
- Exclusions: no optimization without a profile; preserve transaction/cancellation semantics.
- Regression guards: offline deterministic fixtures, warmups/samples/environment metadata; robust
  budgets separate from fragile microbenchmarks.
- Expected-red: instrumentation identifies UI-thread DB/file spans and duplicate page services; CI
  benchmark reports trends without platform-noise false failures.
- Acceptance: agreed p50/p95/memory budgets and profiles cover J01/J07/J12/J13/J16.

## RM-154 — Visual QA

- Prerequisites: stable component/screen states and RM-152 DPI evidence.
- Work package: deterministic fonts/render backend/DPI, target screen-state matrix, goldens,
  tolerance/masking, artifact retention, privacy scrub, review/update owner and anti-flake policy.
- Exclusions: no uncontrolled native pixel comparison as the sole correctness gate.
- Regression guards: semantic tests remain primary for decisions/data; fixtures contain no user data.
- Expected-red: deliberate token/layout regression yields a reviewable diff; unchanged render is stable
  across repeated CI runs.
- Acceptance: representative shell, Dashboard, tender, workflow and critical dialogs have dark/light,
  empty/loading/partial/error/success visual evidence where applicable.

## RM-155 — Cross-stage cleanup and final acceptance

- Prerequisites: RM-142–RM-154 complete with exact-SHA gates.
- Work package: consumer/history/runtime audit of compatibility exports, legacy `MainWindow`, old
  routes/actions/settings/object names and temporary adapters; retire only approved items.
- Exclusions: no opportunistic business/domain rewrite.
- Regression guards: all J01–J16, public imports still promised, offline/no-secret, build/frozen and
  deterministic decision invariants.
- Expected-red: candidate removal fails a consumer test until all owners migrate; final search finds no
  unowned duplicate entry point.
- Acceptance: one production composition, complete journeys, clean compatibility decision log, visual
  and functional gates green, rollback documented.

## Dependency sequence

```text
RM-142 -> RM-143 -> RM-144 -> RM-145 -> RM-146 -> RM-147/RM-148
                                  |                    |
                                  +-> RM-149 -> RM-150-+
RM-143/RM-144 -> RM-151 -> RM-152 -> RM-153 -> RM-154 -> RM-155
```

The diagram expresses prerequisites, not permission to run stages in parallel; canonical roadmap
ordering remains authoritative.
