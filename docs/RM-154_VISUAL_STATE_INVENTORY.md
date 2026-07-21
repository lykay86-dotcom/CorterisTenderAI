# RM-154 Visual State Inventory

Status: approved audit inventory; no baseline is implied by inclusion.

## Decision vocabulary

- `GOLDEN`: a strict offscreen pixel case is required.
- `SEMANTIC`: existing non-pixel assertions remain the primary evidence; no new PNG.
- `CANDIDATE`: characterize first and promote to `GOLDEN` only after review.
- `EXCLUDE`: unstable, native-only, private, redundant, or out of RM-154 scope.

All fixtures use synthetic Russian/English labels and fixed identifiers. Theme cases
are paired. The canonical viewport is 1540x940; the compact logical viewport is
1093x614. RM-152 remains the owner of native monitor/DPI acceptance.

## Shell and page matrix

| Case family | Surface/state | Dark | Light | Viewport | Decision | Native evidence also required | Reason |
|---|---|---:|---:|---|---|---:|---|
| `shell.dashboard.empty` | shell, dashboard selected, deterministic empty state | yes | yes | canonical | GOLDEN | no | shell geometry, navigation, typography, cards, empty state |
| `shell.tenders.empty` | shell, tenders selected, deterministic empty registry | yes | yes | canonical | GOLDEN | no | route highlight, filters, table chrome, empty state |
| `shell.workflow.empty` | shell, workflow selected, deterministic empty workflow | yes | yes | canonical | GOLDEN | no | toolbar, tabs, table, state surfaces |
| `shell.analytics.empty` | shell, analytics selected, deterministic empty snapshot | yes | yes | canonical | GOLDEN | no | filters, chart containers, empty/error affordances |
| `shell.dashboard.compact` | dashboard at RM-152 compact logical size | yes | yes | compact | CANDIDATE | yes | guards logical reflow; native scaling remains RM-152 |
| `dashboard.ready` | populated KPI, recent tenders, recommendations, activity | yes | yes | canonical | GOLDEN | no | high-value successful state with controlled data |
| `dashboard.partial` | partial-data banner and bounded content | yes | yes | canonical | SEMANTIC | no | visually close to ready; semantic tests retain owner |
| `dashboard.error` | deterministic error state | yes | yes | canonical | CANDIDATE | no | important recovery state; promote if layout is distinct |
| `tender.detail.critical-stop` | selected synthetic tender with approved critical stop | yes | yes | canonical | GOLDEN | no | critical-stop priority must be visible but remains deterministic |
| `tender.detail.ai-copy` | provider narrative or recheck prose | no | no | canonical | EXCLUDE | no | generated text is not an approved decision owner |
| `workflow.ready` | deterministic proposal/estimate/project rows | yes | yes | canonical | GOLDEN | no | principal business workflow and table density |
| `workflow.progress` | transient progress/animation | no | no | canonical | SEMANTIC | no | timing is covered semantically; animation is frozen/excluded |
| `analytics.ready` | deterministic finance and distribution snapshots | yes | yes | canonical | GOLDEN | no | chart, legend, filters, table and numeric formatting |
| `analytics.loading` | skeleton/loading affordance | yes | yes | canonical | CANDIDATE | no | characterize after timers/animation are disabled |
| `analytics.too-large` | bounded too-large chart state | no | no | canonical | SEMANTIC | no | RM-146 semantic state already owns this guard |

## Dialog and component matrix

| Case family | Surface/state | Dark | Light | Decision | Native evidence also required | Reason |
|---|---|---:|---:|---|---:|---|
| `dialog.participation.critical-stop` | fixed score, stop factor, approved decision | yes | yes | GOLDEN | yes | most critical decision dialog; native modality remains RM-152 |
| `dialog.participation.busy` | busy indicator | no | no | SEMANTIC | yes | transient animation/timing is not a stable pixel owner |
| `dialog.full-analysis.ready` | deterministic result, no provider text | yes | yes | CANDIDATE | yes | large high-value dialog; promote after size characterization |
| `dialog.full-analysis.recheck` | AI recheck text | no | no | EXCLUDE | yes | provider output must not alter or masquerade as approved decision |
| `dialog.database-recovery` | deterministic recovery choices | yes | yes | CANDIDATE | yes | critical recovery layout; OS-owned dialog chrome excluded |
| `component-gallery.core` | buttons, fields, status chips, table, feedback states | yes | yes | GOLDEN | no | compact token and reusable-component sentinel |
| `chart.ready` | representative bar/line canvas | yes | yes | SEMANTIC | no | full analytics golden plus RM-146 exports already cover pixels |
| `chart.empty/error/stale` | individual chart state variants | no | no | SEMANTIC | no | existing state-specific assertions are more diagnostic |
| `native.file-dialog` | Windows file chooser | no | no | EXCLUDE | yes | OS-owned pixels and personal path risk |
| `window.chrome` | title bar, taskbar, desktop shadows | no | no | EXCLUDE | yes | compositor-owned and outside the client-area contract |

## State construction rules

1. The fixture clock is `2026-07-21T09:00:00+03:00` and relative times are supplied
   as already deterministic domain values.
2. IDs are fixed `VISUAL-*` tokens; names and amounts are synthetic and contain no
   customer, machine, account, or repository data.
3. Repository, settings, keyring, health, network, AI, and filesystem reads are
   replaced with in-memory adapters before the widget is constructed.
4. Async refresh and timers are not started. A case may render only after bounded
   event draining and an explicit ready assertion.
5. Focus, hover, selection, scroll position, expansion, and active route are set by
   the case; defaults are never assumed.
6. The deterministic score, recommendation, and critical stop factor are injected
   through their existing approved domain/view-model owners. Visual fixtures cannot
   compute or override those decisions.
7. A `CANDIDATE` becomes `GOLDEN` only through an audit amendment and explicit
   baseline review. Dropping a candidate requires a recorded reason, not silent
   omission.

## Initial bounded catalog

The implementation begins with the eight mandatory shell route/theme cases and the
paired component-gallery sentinel. Ready-state and critical-dialog families are
added only through existing public setters after their fixture builders pass privacy
and repeatability tests. This ordering keeps the first review bundle small while
preserving the required representative coverage.

