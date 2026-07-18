# RM-141 user-interface audit

## Verdict

The current UI is functionally substantial and its tender-search decisions remain correctly owned
outside presentation code, but it is not ready for a visual redesign as an unstructured styling
exercise. The audit confirms 17 actionable findings: 0 P0, 0 P1, 16 P2, and 1 P3. The main risks
are route ambiguity, embedded legacy composition, fragmented component/theme contracts,
synchronous UI-thread work, table scaling, lifecycle ownership, accessibility/DPI evidence gaps,
and the absence of chart/visual-test contracts.

RM-141 makes no production behavior, dependency, database, design, route, or theme change. Every
actionable finding has exactly one primary owner in RM-142–RM-155.

## Baseline and method

- Evidence SHA: `8e704cf74c64e2125ace165807d1a33d3937b739`.
- Branch origin: exact RM-140 closeout SHA; clean dedicated worktree.
- Sources: canonical roadmap/DoD/history, RM-126–RM-140 audit/contract/acceptance records, Git
  history, static AST inventory, import/consumer search, existing tests, isolated offscreen runtime
  composition, model microbenchmarks, and Windows Quality Gate evidence.
- Environment: Windows 10 19045, Python 3.12.7, PySide6 6.11.1, offscreen Qt.
- External interface guidance: Vercel Web Interface Guidelines fetched on 2026-07-18 and adapted
  only where technology-neutral (focus, form labelling, feedback, state, locale, performance,
  contrast). Web-only DOM/CSS rules were not treated as PySide6 requirements.
- No live provider, credential, keyring value, private user record, or production network was used.

## Hypothesis disposition

| Hypothesis | Result | Evidence summary |
|---|---|---|
| Modern shell is the sole production root | CONFIRMED | `bootstrap()` creates one `ModernMainWindow`; runtime found one `QMainWindow`. |
| Modern shell is independent of legacy UI | NOT_CONFIRMED | public tender page is a five-line re-export of `app.ui.main_window.TenderWorkspacePage`. |
| Sidebar destinations are complete workflows | NOT_CONFIRMED | five of nine routes are placeholder widgets. |
| Dashboard has the strongest component/state contracts | CONFIRMED | dedicated model, state, keyboard, responsive and controller tests. |
| Theme tokens cover all presentation styling | NOT_CONFIRMED | 45 local QSS calls and two literal colors outside theme files. |
| Search lifecycle/shutdown is closed after RM-140 | CONFIRMED for tender search | RM-140 tests and composition; separate workflow health worker is not covered by this claim. |
| UI never performs persistence/file work synchronously | NOT_CONFIRMED | `BusinessWorkflowPage` invokes repository, import/export, backup and recovery services in callbacks. |
| Tables have a uniform scalable model contract | NOT_CONFIRMED | 30 `QTableWidget` sites, two `QTableView` sites; 10k workflow filter p50 121.738 ms. |
| Accessibility/DPI evidence covers the full shell | NOT_CONFIRMED | focused Dashboard/dialog coverage only; multi-DPI and screen reader not executed. |
| Analytics is presentation-ready | NOT_CONFIRMED | Analytics route is placeholder; no chart abstraction, tender-series contract, or drill-down owner. |
| Saved credentials can be read back through UI | NOT_CONFIRMED | RM-132 tests verify disabled legacy field and no secret prefill. |
| A P0/P1 privacy or data-loss defect is present | NOT_CONFIRMED | raw-error risk exists, but no secret exposure or data loss was reproduced. |

## Cross-cutting audit results

### UI and business boundary

Presentation formatting, validation, signal routing and dialog orchestration are legitimate UI
work. Deterministic scoring, recommendation, critical stop factors, normalization, provider
protocols, credentials and search retry/cancellation remain in existing application/domain owners.
No duplicate decision algorithm was found in UI.

The exception is operational placement: `BusinessWorkflowPage.refresh()`, import/export, backup,
restore, database inspection and record mutations call services/repositories directly from UI
callbacks. The service behavior is not duplicated, but potentially blocking DB/file work remains
on the UI thread. The page also creates default repositories/services/timers, obscuring lifecycle
ownership when the shell creates two page instances.

### Theme and components

Dark/light semantic palettes, typography tokens and a global QSS builder exist, including chart
color slots. Reusable buttons/cards and Dashboard components are present. The missing contract is
system-wide: local QSS remains widespread; focus selectors cover line/text edits but not all
buttons/tool buttons/combos; global disabled-state coverage is incomplete; top-bar/sidebar icons
are Unicode glyphs without an asset/fallback policy; database status embeds literal red/green.

### Accessibility and DPI

Dashboard tables/actions have deliberate keyboard behavior and some components expose names and
descriptions. Static inventory finds 30 accessible-name calls, 13 descriptions and no label
buddies; runtime finds 275 focusable widgets, 66 named and 23 described. These counts identify a
review gap, not automatic nonconformance. Top-bar glyph controls rely on tooltips. There is no
full-shell Tab/Shift+Tab/focus-restoration test, screen-reader exercise, high-contrast exercise, or
validated contrast matrix. The shell minimum is 1180x720 and Sidebar minimum width is 250; 14
fixed, 31 minimum and 6 maximum dimension calls increase scaling/localization risk.

The mandatory 100–200% Windows scaling matrix is `NOT_EXECUTED` because the audit environment did
not expose controlled interactive displays at each scale. Offscreen responsive tests are useful
but cannot prove native DPI, font rasterization, hit targets, multi-monitor motion or clipping.

### Tables, states, and performance

Dashboard `TenderFeedModel` uses a `QTableView` and explicit empty/loading/error state panel.
Workflow uses a model/proxy/delegate but resets/sorts the full list and filters all rows. Many
tender dialogs use `QTableWidget`, with local identity/selection/state policies. There is no common
pagination/virtualization, stable selection, provenance, export parity or large-data acceptance
contract.

Read-only benchmark (`perf_counter_ns`, two warmups, nine samples, fixture generation excluded):

| Scenario | Rows | p50 ms | p95 ms |
|---|---:|---:|---:|
| Workflow reset + sort | 100 | 0.059 | 0.064 |
| Workflow reset + sort | 1,000 | 0.656 | 2.230 |
| Workflow reset + sort | 10,000 | 8.399 | 12.352 |
| Workflow proxy missing-text filter | 100 | 0.970 | 1.937 |
| Workflow proxy missing-text filter | 1,000 | 11.969 | 14.559 |
| Workflow proxy missing-text filter | 10,000 | 121.738 | 148.005 |
| Dashboard tender model reset | 10,000 | 0.055 | 0.059 |

This is a model-operation baseline, not a full render/startup/memory SLA. Full-shell first paint,
page switching, theme switching, dialog cycles, peak memory and native widget rendering are
`NOT_EXECUTED` as reliable benchmarks and belong to RM-153.

### Analytics readiness

Dashboard KPI DTOs have identity/value/tone but not a complete metric-definition, interval,
provenance, freshness and drill-down contract. `BusinessMetricsSnapshot` uses `Decimal` for
potential profit, while `BusinessWorkflowRecord` stores `total`, `profit`, and margin as `float`
and the UI model formats/sorts floats. The analytics sidebar destination is a placeholder and there
is no chart dependency or abstraction. This is correctly a contract gap, not permission to add
charts in RM-141.

### Security and privacy

Positive evidence: isolated composition made no socket connection; credential dialogs do not
prefill saved secrets; RM-140 redacts search failures; destructive backup/recovery flows include
confirmation/safety-backup behavior; no secret was found in audit artifacts.

Risk evidence: multiple dialogs pass `str(exc)` directly to user-visible messages/details;
`TenderWorkspacePage._update_db_status` interpolates an exception into rich-text markup without
escaping. This can disclose local paths/technical details or treat untrusted markup as rich text,
but no secret/path injection was reproduced. Severity therefore remains P2. Clipboard and real
support-bundle contents were not exercised with user data.

### Test maturity

The UI-focused contour is broad: 97 modules and 302 passing tests cover models, controllers,
dialogs, composition, background search, offline isolation, keyboard behavior, responsive rules,
themes, migrations and frozen build imports. Risks are concentration around known features,
offscreen-only layout assertions, limited event-loop stress across the whole shell, no controlled
DPI matrix and zero screenshot/golden tests. Visual regressions, focus-order regressions and
cross-dialog theme drift can therefore pass current CI.

## Findings register

### UI-141-001 — Sidebar exposes unavailable peer routes

- Status: CONFIRMED; Severity: P2; Category: information architecture.
- User journey: J03, J08, J10; Evidence SHA: `8e704cf74c64e2125ace165807d1a33d3937b739`.
- Files/symbols: `ModernMainWindow.__init__`, `_placeholder`; Runtime consumer: production shell.
- Observed behavior: five of nine sidebar destinations are placeholders; notifications/profile are stubs.
- Expected invariant: navigation communicates availability and leads to recoverable user jobs.
- User/business impact: false affordances and duplicated expectations for AI/settings/notifications.
- Security/data impact: none identified.
- Owner: shell route/navigation contract; Existing tests: RM-127 composition.
- Regression contract: preserve all working routes/deep links while placeholder status becomes explicit.
- Target RM: RM-142; Dependencies: RM-141 audit.
- Suggested direction, not implementation: define route taxonomy, availability and state preservation.
- Rollback/compatibility concern: sidebar keys and Dashboard quick actions are compatibility inputs.
- Confidence: high.

### UI-141-002 — Two peer routes present one workflow repository

- Status: CONFIRMED; Severity: P2; Category: information architecture/data context.
- User journey: J12; Evidence SHA: baseline above.
- Files/symbols: `ModernMainWindow.quotes_page`, `.estimates_page`; Runtime consumer: shell.
- Observed behavior: two eager `BusinessWorkflowPage` instances share one repository and differ by initial filter.
- Expected invariant: route labels, scope and retained selection clearly describe one data domain.
- User/business impact: duplicate navigation, duplicated background owners and context loss on refresh.
- Security/data impact: no corruption reproduced.
- Owner: route taxonomy; Existing tests: workflow filters and Dashboard metrics.
- Regression contract: proposal/estimate/project create/edit/history/export remain reachable with stable IDs.
- Target RM: RM-142; Dependencies: UI-141-001.
- Suggested direction, not implementation: define one coherent workflow hierarchy and preserved filters.
- Rollback/compatibility concern: Dashboard quick actions currently target both keys.
- Confidence: high.

### UI-141-003 — Theme/component contract is fragmented

- Status: CONFIRMED; Severity: P2; Category: design system.
- User journey: J06, J14; Evidence SHA: baseline above.
- Files/symbols: `app.ui.theme.*`, 45 `setStyleSheet` calls, `main_window.py:1169-1174`.
- Runtime consumer: all pages/dialogs; Observed: tokens coexist with local QSS, glyph icons and literals.
- Expected invariant: semantic tokens and reusable states cover focus/disabled/error/theme parity.
- User/business impact: inconsistent redesign, inaccessible states and high change cost.
- Security/data impact: rich-text exception aspect is separately UI-141-012.
- Owner: theme/component system; Existing tests: palette and selected component theme tests.
- Regression contract: dark/light behavior, object names and semantic status remain stable.
- Target RM: RM-143; Dependencies: RM-142 taxonomy.
- Suggested direction, not implementation: inventory-derived token/component/state contract.
- Rollback/compatibility concern: local object names/QSS selectors are test and style APIs.
- Confidence: high.

### UI-141-004 — Production tender page remains embedded legacy

- Status: CONFIRMED; Severity: P2; Category: composition/maintainability.
- User journey: J04, J07, J09; Evidence SHA: baseline and commits `cc1d8d7`, `4a037ea`.
- Files/symbols: `app.ui.main_window.TenderWorkspacePage`, public re-export module.
- Runtime consumer: `ModernMainWindow`; Observed: active page and compatibility `MainWindow` share legacy owner file.
- Expected invariant: one explicit shell/page composition with audited compatibility boundary.
- User/business impact: redesign can accidentally remove mature tender workflows or duplicate owners.
- Security/data impact: none direct.
- Owner: production composition; Existing tests: RM-127/RM-140 contracts.
- Regression contract: imports, tabs, actions, shortcuts, settings and tender-ID opening remain valid.
- Target RM: RM-144; Dependencies: RM-142/143 contracts.
- Suggested direction, not implementation: staged extraction without new domain/service layer.
- Rollback/compatibility concern: retain wrapper/re-export until consumer search and acceptance permit retirement.
- Confidence: high.

### UI-141-005 — Workflow health worker can outlive its page

- Status: CONFIRMED; Severity: P2; Category: lifecycle/threading.
- User journey: J13, J16; Evidence SHA: baseline above.
- Files/symbols: `BusinessWorkflowPage` health scheduling; `SystemHealthMonitor` runnable signals.
- Runtime consumer: both workflow pages; Observed: rapid shell close produced two deleted-signal-source errors.
- Expected invariant: every worker has a live receiver or is cancelled/drained before QObject deletion.
- User/business impact: noisy/unsafe shutdown and possible lost final feedback; no data loss reproduced.
- Security/data impact: none observed.
- Owner: shell/page composition lifecycle; Existing tests: health monitor and RM-140 search shutdown, but not this cross-owner close.
- Regression contract: close before/during/after health work has no late signal and remains offline.
- Target RM: RM-144; Dependencies: UI-141-004.
- Suggested direction, not implementation: assign worker ownership and terminal close protocol.
- Rollback/compatibility concern: do not weaken RM-140 search close guarantees.
- Confidence: high.

### UI-141-006 — Dashboard metrics lack a redesign job/drill-down contract

- Status: PARTIAL; Severity: P2; Category: Dashboard semantics.
- User journey: J01, J03; Evidence SHA: baseline above.
- Files/symbols: `DashboardSnapshot`, `DashboardKpi`, `DashboardPage`.
- Runtime consumer: Dashboard; Observed: KPI identity/value/tone exists, but definition/provenance/freshness/drill-down is incomplete.
- Expected invariant: each KPI answers a user job and has owned states and deterministic drill-down.
- User/business impact: visual redesign could amplify ambiguous numbers.
- Security/data impact: none.
- Owner: Dashboard presentation contract; Existing tests: Dashboard metrics/states/controller.
- Regression contract: values still come from repository snapshot, never ad-hoc UI calculations.
- Target RM: RM-145; Dependencies: RM-142/143.
- Suggested direction, not implementation: define jobs, owners, freshness and route targets before layout.
- Rollback/compatibility concern: retain current quick actions and empty/error behavior until migrated.
- Confidence: medium-high.

### UI-141-007 — No reusable chart interaction/accessibility layer

- Status: CONFIRMED; Severity: P2; Category: chart readiness.
- User journey: future analytics from J01/J03; Evidence SHA: baseline above.
- Files/symbols: analytics placeholder, theme chart colors; Runtime consumer: none yet.
- Observed behavior: no chart implementation/dependency/data-to-mark contract.
- Expected invariant: charts have semantic fallback, keyboard, tooltip, selection, empty/error/export contracts.
- User/business impact: independent charts would duplicate behavior and exclude keyboard/screen-reader users.
- Security/data impact: provenance must not be lost.
- Owner: chart presentation layer; Existing tests: none.
- Regression contract: expected-red contract for one deterministic accessible chart fixture.
- Target RM: RM-146; Dependencies: RM-143 and RM-145 metric contract.
- Suggested direction, not implementation: select abstraction only after interaction/QA requirements.
- Rollback/compatibility concern: no dependency may be added until RM-146 review.
- Confidence: high.

### UI-141-008 — Tender analytics series/provenance contract is absent

- Status: CONFIRMED; Severity: P2; Category: tender analytics.
- User journey: J07, J09, J11; Evidence SHA: baseline above.
- Files/symbols: search/registry records and analytics placeholder; Runtime consumer: none as analytics.
- Observed behavior: operational tender data exists but no metric identity, interval, aggregation, provenance or drill-down series contract.
- Expected invariant: analytics preserves deterministic source, filters, timezone and tender identity.
- User/business impact: misleading aggregations or non-reproducible dashboards.
- Security/data impact: provenance/partial-source status could be hidden.
- Owner: tender analytics contract; Existing tests: source/provenance/search contracts, not analytics.
- Regression contract: same fixture/filter/order yields same series and drill-down tender IDs.
- Target RM: RM-147; Dependencies: RM-146.
- Suggested direction, not implementation: define metrics and aggregation owner outside widgets.
- Rollback/compatibility concern: do not reinterpret approved scores/recommendations.
- Confidence: high.

### UI-141-009 — Financial presentation crosses Decimal into float records

- Status: CONFIRMED; Severity: P2; Category: financial analytics/data semantics.
- User journey: J12; Evidence SHA: baseline above.
- Files/symbols: `BusinessWorkflowRecord.total/profit/margin_percent`, `WorkflowTableModel._money/_sort_value`.
- Runtime consumer: workflow pages; Observed: record money is float while aggregate potential profit uses Decimal.
- Expected invariant: currency, precision, unit and rounding policy survive repository-to-chart/export.
- User/business impact: rounding/order discrepancies in financial views.
- Security/data impact: integrity risk, no incorrect persisted result reproduced by audit.
- Owner: financial analytics presentation contract; Existing tests: workflow model/repository/export.
- Regression contract: exact currency fixture agrees across table, KPI, chart and export.
- Target RM: RM-148; Dependencies: RM-146.
- Suggested direction, not implementation: agree Decimal/currency/rounding boundary before charts.
- Rollback/compatibility concern: schema/export compatibility needs explicit migration decision.
- Confidence: high.

### UI-141-010 — Tender information/action hierarchy is fragmented

- Status: CONFIRMED; Severity: P2; Category: tender detail/card UX.
- User journey: J03, J09, J11; Evidence SHA: baseline above.
- Files/symbols: Dashboard feed, registry, search results, analysis/score/verification dialogs.
- Runtime consumer: Dashboard and tender workspace; Observed: identity, provenance, status and actions are repeated across table/dialog surfaces.
- Expected invariant: one hierarchy defines primary facts/actions while keeping source/confidence and critical stop factors visible.
- User/business impact: inconsistent action discovery and decision context.
- Security/data impact: critical warnings could be visually demoted.
- Owner: tender card/detail contract; Existing tests: individual surfaces only.
- Regression contract: same tender ID and deterministic decision across feed/registry/detail.
- Target RM: RM-149; Dependencies: RM-142/143 and RM-147 definitions.
- Suggested direction, not implementation: define reusable information hierarchy, not another decision owner.
- Rollback/compatibility concern: keep context actions and deep links.
- Confidence: high.

### UI-141-011 — Table contracts do not scale uniformly

- Status: CONFIRMED; Severity: P2; Category: tables/performance/accessibility.
- User journey: J03, J07, J09, J12; Evidence SHA: baseline and benchmark above.
- Files/symbols: 30 `QTableWidget` sites; `WorkflowTableModel`, proxy; `TenderFeedModel`.
- Runtime consumer: most data workflows; Observed: mixed update/identity/state/selection contracts and 10k filter p95 148.005 ms.
- Expected invariant: stable IDs, preserved selection, explicit states, keyboard semantics and bounded large-data behavior.
- User/business impact: lag/context loss and inconsistent accessibility.
- Security/data impact: selection drift can target the wrong action; no destructive mis-target reproduced.
- Owner: table presentation contract; Existing tests: component-specific model/table tests.
- Regression contract: 0/100/1k/10k fixtures, sorting/filtering/selection/empty/error/keyboard/export parity.
- Target RM: RM-150; Dependencies: RM-143 and domain contracts.
- Suggested direction, not implementation: shared contract before replacing individual widgets.
- Rollback/compatibility concern: row IDs, action names and export ordering.
- Confidence: high.

### UI-141-012 — User-facing error/background feedback has no unified privacy policy

- Status: CONFIRMED; Severity: P2; Category: feedback/security/privacy.
- User journey: J02, J07–J10, J13, J15; Evidence SHA: baseline above.
- Files/symbols: multiple `str(exc)` message paths; `main_window.py:1174` rich text.
- Runtime consumer: tender/workflow dialogs; Observed: raw technical exceptions may be shown; progress episodes vary by controller.
- Expected invariant: stable safe summary, correlated diagnostic detail, retry/cancel/terminal state, escaped rich text.
- User/business impact: confusing recovery and possible disclosure of private paths/technical endpoints.
- Security/data impact: potential disclosure; no credential exposure reproduced.
- Owner: background operation/notification episode policy; Existing tests: RM-140 search redaction plus individual dialogs.
- Regression contract: synthetic secret/path/HTML exception never appears in user text; diagnostic artifact remains available per policy.
- Target RM: RM-151; Dependencies: RM-143 component states and RM-144 lifecycle.
- Suggested direction, not implementation: common safe feedback contract using existing service errors.
- Rollback/compatibility concern: preserve actionable error categories and support diagnostics.
- Confidence: high on raw paths, medium on real sensitive content.

### UI-141-013 — Accessibility/keyboard evidence is component-local

- Status: PARTIAL; Severity: P2; Category: accessibility.
- User journey: all, especially J03/J04/J14; Evidence SHA: baseline runtime/static counts.
- Files/symbols: TopBar/Sidebar/dialog forms/global QSS; Runtime consumer: whole shell.
- Observed behavior: useful Dashboard contracts coexist with tooltips-only glyphs, no label buddies and no full focus traversal/restoration test.
- Expected invariant: logical visible focus, labelled controls, keyboard activation/escape and color-independent status.
- User/business impact: keyboard/assistive users may not discover or recover from actions.
- Security/data impact: focus/selection ambiguity can increase action error; no destructive event reproduced.
- Owner: accessibility/DPI stage; Existing tests: Dashboard keyboard, selected metadata/dialog tests.
- Regression contract: full-shell Tab/Shift+Tab, Enter/Space/Escape, dialog return focus, dark/light focus, accessible names.
- Target RM: RM-152; Dependencies: RM-142/143/144.
- Suggested direction, not implementation: measured accessibility matrix with native Windows assistive checks.
- Rollback/compatibility concern: preserve shortcuts and visible labels while adding semantics.
- Confidence: medium; screen reader `NOT_EXECUTED`.

### UI-141-014 — Native DPI/scaling matrix is unverified

- Status: PARTIAL; Severity: P2; Category: DPI/responsive/localization.
- User journey: all visual journeys; Evidence SHA: baseline above.
- Files/symbols: shell minimum size, Sidebar minimum, fixed/min/max dimensions.
- Runtime consumer: whole shell; Observed: responsive helpers exist but required native 100–200% matrix was unavailable.
- Expected invariant: no clipping/overlap/traps across specified viewports/scales and monitor changes.
- User/business impact: unusable controls on common Windows scaling and 1366x768.
- Security/data impact: none direct.
- Owner: accessibility/DPI stage; Existing tests: Dashboard responsive/workflow detail only.
- Regression contract: screenshot/manual matrix with viewport, scale, theme, locale and focus evidence.
- Target RM: RM-152; Dependencies: RM-143/144.
- Suggested direction, not implementation: execute controlled Windows matrix before geometry fixes.
- Rollback/compatibility concern: saved geometry and minimum sizes.
- Confidence: medium; mandatory cases `NOT_EXECUTED`.

### UI-141-015 — Performance ownership and budgets are absent

- Status: CONFIRMED; Severity: P2; Category: UI performance.
- User journey: J01, J12, J13; Evidence SHA: baseline and benchmark above.
- Files/symbols: eager shell construction; synchronous `BusinessWorkflowPage` repository/file callbacks.
- Runtime consumer: startup and both workflow pages; Observed: direct IO and duplicate services/timers; no startup/render/memory budgets.
- Expected invariant: measured UI-thread spans and explicit worker/cancellation/update budgets.
- User/business impact: stalls and slow startup on large/slow storage.
- Security/data impact: user may interrupt during opaque operation; safety backups mitigate some recovery.
- Owner: profiling/performance stage; Existing tests: background dashboard/search and nonblocking startup DB test.
- Regression contract: repeatable p50/p95 startup/page/filter/theme/dialog/shutdown and memory baselines.
- Target RM: RM-153; Dependencies: RM-144 and RM-150.
- Suggested direction, not implementation: profile before moving work; reuse existing services/workers.
- Rollback/compatibility concern: preserve transaction/backup semantics and terminal signals.
- Confidence: high for synchronous calls, medium for user-visible duration.

### UI-141-016 — Visual regression workflow is absent

- Status: CONFIRMED; Severity: P2; Category: visual QA.
- User journey: all visual states; Evidence SHA: baseline test search.
- Files/symbols: UI test suite; Runtime consumer: all surfaces.
- Observed behavior: zero screenshot/golden tests; current assertions cannot detect pixel/layout drift.
- Expected invariant: deterministic fonts/DPI/theme/state fixtures, tolerance/masking, artifacts and review owner.
- User/business impact: redesign regressions can merge despite green functional CI.
- Security/data impact: artifacts must exclude private data.
- Owner: visual QA stage; Existing tests: offscreen semantic/layout tests only.
- Regression contract: representative shell/dashboard/tender/workflow/dialog states in dark/light and target DPI.
- Target RM: RM-154; Dependencies: RM-143 and stabilized screens.
- Suggested direction, not implementation: define environment and anti-flake policy before selecting tool.
- Rollback/compatibility concern: do not make native pixel noise a brittle gate.
- Confidence: high.

### UI-141-017 — Compatibility retirement lacks a final cross-stage owner

- Status: CONFIRMED; Severity: P3; Category: cleanup/acceptance.
- User journey: all migrated routes; Evidence SHA: baseline module/history inventory.
- Files/symbols: compatibility package exports, tender re-export, legacy `MainWindow`, old action/settings/object names.
- Runtime consumer: production/tests/imports; Observed: compatibility is necessary today but can become orphaned after RM-142–154.
- Expected invariant: retire only after runtime/import/history search and replacement acceptance.
- User/business impact: premature deletion breaks workflows; permanent retention increases ambiguity.
- Security/data impact: stale entry points can bypass future UX policy if left indefinitely.
- Owner: final redesign cleanup; Existing tests: RM-127/RM-140 compatibility tests.
- Regression contract: explicit consumer map, deprecation decision, clean full gate and route/journey parity.
- Target RM: RM-155; Dependencies: RM-142–154 complete.
- Suggested direction, not implementation: final audited retirement list and end-to-end acceptance.
- Rollback/compatibility concern: all compatibility is retained through prior stages.
- Confidence: high.

## Risk summary and stop-condition result

| Severity | Count | Disposition |
|---|---:|---|
| P0 | 0 | none evidenced |
| P1 | 0 | none evidenced |
| P2 | 16 | assigned once across RM-142–RM-154 |
| P3 | 1 | assigned to RM-155 |

No stop-condition security/data decision was triggered. `PARTIAL` findings explicitly identify
unexecuted native evidence; they are not presented as passes. RM-142+ was not implemented.
