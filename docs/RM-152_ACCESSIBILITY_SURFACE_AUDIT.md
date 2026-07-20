# RM-152 accessibility surface audit

Audit baseline: `9cb37b9a83f50ac9f8f8e34fdeb582c2ed76e257`
Audit date: `2026-07-20`
Branch/worktree: `feat/rm-152-accessibility-dpi`, `.worktrees/rm152`

## Verdict

The RM-151 closeout and canonical entry gate are accepted. The current UI does not yet satisfy
RM-152: representative keyboard traps, unstable focus identities, missing semantics, an
unsupported small-screen minimum, absent geometry recovery, and unexecuted native evidence are
reproduced below. These are presentation defects only; no score, recommendation, stop-factor,
repository, provider, schema, or lifecycle owner needs replacement.

Decisions in this audit mean:

- `keep`: accepted owner/native behavior, protected by characterization;
- `fix`: change through the existing RM-142/RM-143/RM-150/RM-151 seam;
- `adapt`: add bounded presentation metadata or layout behavior without changing ownership;
- `defer`: outside RM-152 with an explicit residual; never an inferred pass.

## Reproducible static inventory

The six commands required by the RM-152 specification were executed against `app`, `app/ui`, and
`tests`. The existing AST inventory was also executed with
`python scripts/audit_ui_inventory.py --format summary`.

| Measure | RM-141 historical | RM-152 baseline |
|---|---:|---:|
| `app/ui` modules | 68 | 91 |
| `app/ui` lines | 28,910 | 36,614 |
| UI/PySide6 test modules | 97 | 148 |
| `setAccessibleName` calls | 30 | 67 |
| `setAccessibleDescription` calls | 13 | 36 |
| explicit `setBuddy` calls | 0 | 0 |
| local `setStyleSheet` calls | 45 | 43 |
| literal colors outside theme modules | 2 | 0 |
| fixed/minimum/maximum dimension calls | 14 / 31 / 6 | 15 / 34 / 6 |
| `QTableWidget` / `QTableView` constructions | 30 / 2 | 32 / 4 |
| `QTimer` / `QThread` constructions | 6 / 1 | 6 / 1 |
| direct `QDialog` subclasses | not recorded | 30 |
| `QMessageBox` information/warning/critical/question calls | not recorded | 90 |
| `QListWidget` / `QTabWidget` constructions | not recorded | 7 / 4 |

The broad `rg` expressions produced 137 accessibility/focus matches, 26 focus-policy/tab-order
matches, 126 key/shortcut matches, 92 geometry matches, 226 style/color matches, and 607 complex
widget matches. These match counts are search diagnostics, not conformance ratios.

No new literal color exists outside `app.ui.theme`. The remaining local styles are theme-token
consumers and require high-contrast observation; they are not automatically defects.

## Isolated runtime inventory

The production `ModernMainWindow` was constructed with:

- `QT_QPA_PLATFORM=offscreen`;
- temporary QSettings and data/config/log/cache roots under the RM-152 worktree;
- isolated tender-workspace repositories;
- Dashboard startup and workflow-health execution disabled;
- `socket.getaddrinfo`, `socket.connect`, `urllib.request.urlopen`, and keyring reads rejected.

| Measure | RM-141 historical | RM-152 baseline |
|---|---:|---:|
| descendant widgets including shell | 960 | 1,008 |
| non-`NoFocus` widgets, including hidden pages/editors | 275 | 252 |
| widgets with non-empty accessible name | 66 | 76 |
| widgets with non-empty accessible description | 23 | 31 |
| `QLabel` instances / runtime buddy relations | not recorded | 194 / 25 |
| visible, enabled focusable widgets on initial Dashboard | not recorded | 18 |
| visible, enabled focusable widgets without explicit name | not recorded | 3 |

The unnamed initial controls were `TopBarTenderSearch`, `DashboardScroll`, and
`DataStateAction`. Runtime buddy relations are created by Qt `QFormLayout.addRow`; therefore zero
explicit `setBuddy` calls does not mean zero relations. Both implicit and explicit relations must
be tested at the actual surface.

## Post-implementation inventory

The same static audit after commit `5e0910d` reports 97 UI modules / 37,243 lines, 151 UI test
modules, 90 explicit accessible-name calls, 53 accessible-description calls, zero literal colors
outside theme, 15 / 35 / 6 fixed/minimum/maximum calls, 32 / 4 table widget/view constructions,
and 6 / 1 timer/thread constructions.

`python scripts/audit_rm152_runtime.py` constructs the shell with temporary QSettings, synthetic
empty repositories, disabled startup health/backup work, no keyring, and no network. It reports
1,008 widgets, 252 non-`NoFocus` widgets, 130 focusable widgets with stable object names, 84
non-empty accessible names, 35 descriptions, and 194 labels / 25 runtime buddy relations. Static
call counts are regression indicators, not a conformance percentage; native Narrator remains the
authority for role/state/relation quality.

## Current traversal and shortcut evidence

An offscreen Qt key traversal started at the first sidebar button and recorded stable properties.

- Dashboard reaches shell controls, refresh, state action, quick actions, and activity; after entry
  it loops from `DataStateAction` to the first duplicate-named `QuickActionTile` instead of leaving
  the page. This is an A2 keyboard trap/misordering.
- Tenders reaches the first `QTabBar`, its scroll tool button, then an empty unnamed
  `QTableWidget`; Tab remains in that table. This is an A2 trap and semantic gap.
- Workflow returns to the shell, but its health badge and filter edit/combos have empty accessible
  names and most lack stable object names. This is A2/A3.
- Analytics initially retains whichever control owned focus. Its date editor can consume Tab for
  native subcontrol navigation; the future harness must distinguish a bounded native composite
  from a trap.
- Sidebar buttons have names but no object names. All `CorterisButton` and `QuickActionTile`
  instances reuse one object name, so those values are not valid RM-142 focus tokens.

With the existing tender controller installed, six `QAction` shortcuts and eleven Dashboard
`QShortcut` bindings were found. There were no duplicate sequences:

| Scope | Shortcuts |
|---|---|
| tender actions | `Ctrl+Shift+F/R/S/C/P/N` |
| Dashboard | `Ctrl+F`, `Ctrl+A`, `Ctrl+K`, `Ctrl+S`, `Ctrl+R`, `Alt+1`–`Alt+5`, `Esc` |

Tender actions use `WindowShortcut`; Dashboard bindings use `WidgetWithChildrenShortcut`. The
binding ownership is kept. Tests must still prove disabled/hidden owners cannot act.

## Representative dialog evidence

`ProviderCredentialsDialog` was opened over a synthetic origin button. Qt correctly focused the
password input, `QFormLayout` related `API credential:` to it, Save was the non-destructive default,
Delete was not default, Escape rejected without a secret value, and the input remained empty.
After rejection the offscreen run had no focus widget: explicit stable return-focus behavior is
missing. This is the representative expected-red dialog defect.

The source contains 30 direct dialog subclasses and 90 message-box calls. Message boxes that name
a destructive target generally pass a safe `No`/`Cancel` default; this behavior is kept and guarded.
Dialog-specific initial focus, validation focus, return focus, and small-viewport resizing remain
inconsistent and are fixed through a bounded local helper, not a new modal framework.

## DPI, viewport, and packaging evidence

The native host discovery (no app window) reported Windows `10.0.19045`, Python `3.12.7`,
PySide6/Qt `6.11.1`, and one physical display `DELL E2218HN`, `1920x1080`, available
`1920x1040`, logical DPI `96`, device-pixel ratio `1.0`, 60 Hz.

The baseline `ModernMainWindow` had logical minimum `1180x720`. A 1366x768 physical display at 125% provides
approximately `1093x614` logical pixels before taskbar deductions, so the accepted minimum cannot
fit. RM-152 reduced the supported minimum to `960x540`; injected viewport and Russian full-text
tests now pass. Native 1366x768 at 125% is still `NOT_EXECUTED`.

No explicit Windows DPI-awareness manifest, Qt high-DPI attribute, saved-window geometry,
screen-change handler, or geometry-clamping helper exists in `app`, the PyInstaller spec, or the
installer. Qt 6 native defaults may be adequate in a dev process, but packaged and mixed-monitor
behavior is `NOT_EXECUTED`; the DPI mode must not be changed without packaged verification.

## Surface and decision register

| Surface ID / modules | Journeys | Existing owner | Current focus/semantics/layout evidence | Risk | Decision |
|---|---|---|---|---:|---|
| `workspace.shell` (`ModernMainWindow`, `DashboardLayout`) | J01,J03,J04,J14,J16 | RM-142 shell/navigation; RM-144 close | one shell; route focus fallback may target hidden/disabled/`NoFocus`; minimum too large | A2 | fix focus resolution and supported minimum; keep owners |
| `workspace.sidebar` | J01,J03,J12,J14 | RM-142 route registry/layout | named/checkable buttons, no stable control IDs | A2 | adapt stable route-derived IDs and selected semantics |
| `workspace.topbar` | J04,J08,J10,J14 | shell + existing actions | icon buttons named; search unnamed; theme name lacks current state | A2 | fix safe name/state; keep action identity |
| `workspace.status` | J01,J04,J07,J16 | shell/RM-151 feedback owners | native status text, background updates may not announce; no focus steal observed | A3 | adapt bounded semantic status projection |
| `workspace.dashboard` | J01,J03,J04 | Dashboard page/controller | explicit child tab orders form a page subcycle; dynamic state action unnamed | A2 | fix one logical chain and stable IDs; keep KPI/route owners |
| `dashboard.kpis/feed/quick/activity` | J03,J04 | RM-145/RM-150 Dashboard widgets | cards and feed semantic; duplicate object names; empty-state chain failure | A2 | adapt IDs/fallback; keep mouse/keyboard parity |
| `workspace.tenders` | J04,J09,J10 | legacy workspace + RM-142 destination | native tabs; unnamed overview table traps on empty state; fixed text editors | A2 | fix representative chain/labels; defer full visual redesign |
| `tender.search.panel` | J04,J05,J07 | `TenderSearchUiController`/RM-140 | query focus helper exists; labels/states/operation feedback fragmented | A2 | adapt labels, state text, no-focus-steal assertions |
| `tender.profiles` | J05 | profile dialog/editor/service | QForm-style content, fixed editor heights, validation local | A2 | fix relations/first-invalid/resize; keep repository |
| `tender.providers.credentials` | J06,J10 | provider controller/secret store | write-only input is safe; current dialog initial focus good; return focus missing | A2 | fix local dialog focus; preserve no-readback |
| `tender.collector` | J07 | RM-140 lifecycle/RM-151 episode adapter | typed states/text; progress table and actions need traversal/announcement evidence | A2 | adapt semantics; keep lifecycle/coalescer |
| `tender.scheduler.notifications` | J08 | scheduler controller and sole notification repository | canonical shortcuts; notification table lacks explicit name/description | A2 | fix common entry focus, row semantics, removed-row fallback |
| `tender.registry.results` | J09 | registry/search controller + RM-150 identities | accessible table names exist at registry; results table metadata sparse | A2 | adapt RM-150 roles and exact identity focus |
| `tender.detail.card` | J03,J09,J11 | RM-149 snapshot/action owners | strong names/descriptions and critical text; nested return policy incomplete | A2 | keep hierarchy; adapt stable action origins |
| `tender.documents` | J09 | existing documents controller/dialog | table/action UI, fixed initial size, no explicit semantics | A2 | fix representative metadata/focus; keep worker |
| `tender.requirements.verification` | J09,J11 | existing analysis/verification owners | text alternatives exist; 2+3 tables, strict maximum heights | A2 | adapt relations/scroll/resizing and critical order |
| `tender.full_analysis.score` | J09,J10 | existing analysis/score owners | tabs/tables; typed decision remains authoritative; native reading untested | A2 | adapt semantics/focus only; keep RM-107 priority |
| `workspace.analytics.charts` | J09,J12 | RM-146/RM-147 chart owners | chart keyboard/text table accepted offscreen; native DPI/Narrator absent | A2 | keep data/order; add native evidence and focus fallback |
| `workspace.workflow` | J12,J13 | workflow page/repository/RM-144 lifecycle | table named; health/filter controls unnamed; responsive split already exists | A2 | fix names/tab order/small viewport; keep repository |
| `workflow.record.forms` | J12 | `BusinessRecordDialog`/workflow owner | validation sets focus; field relations and return identity not universal | A2 | adapt first-invalid and stable record focus |
| `workflow.import.export` | J12,J13 | existing synchronous services | no fake cancel; import is destructive confirmation path | A1 | keep lifecycle; guard safe default/exact target/focus return |
| `workflow.backup.recovery` | J13,J15 | backup/recovery/health owners | exact identity contract from RM-150; large dialogs; focus policy inconsistent | A1 | fix safe default/initial/return/layout; never retarget |
| `workflow.health` | J13,J15 | system health service/monitor | clickable badge unnamed; status text visible | A2 | adapt button semantics; keep monitor/lifecycle |
| `crash.safe_mode.support` | J02,J15 | crash/support/launch-guard owners | fixed dialog sizes, safe summaries partly RM-151 adapted | A1 | fix focus/sizing; scan accessible strings; keep artifacts |
| `tables.common` | J03,J08,J09,J12,J13 | RM-150 model/selection/action | four views + 32 compatibility widgets; table internal Tab can trap | A2 | extend common view behavior; migrate only audited sites |
| `operations.feedback` | J07,J08,J09,J13,J16 | RM-151 episode/coalescer | safe bounded text and no focus steal are contract owners | A2 | keep owners; add consumer metadata/native observation |

## Fixed and constrained dimension decisions

- Keep/adapt the 15 fixed calls used for tokenized icon/button/progress geometry; they are logical
  Qt units and need native crop checks at 100–200%.
- Replace four fixed text-editor heights in `tender_search_profile_editor.py` with minimum/size
  policy where Russian growth or validation text requires it.
- Audit the six strict maximums: provider/search lists may remain bounded with keyboard scrolling;
  verification evidence/history must not hide required information.
- Preserve chart logical minimum `160x120` and tokenized button minimum heights.
- Reduce the shell minimum only with injected-size tests; do not mechanically remove all minima.
- Treat the 26 initial `resize()` calls as preferred starting sizes, not persisted or required
  minima; dialogs with growing tables/text remain resizable.

## Findings and stop conditions

| Finding | Evidence | Planned closure |
|---|---|---|
| `UI-141-013` keyboard/accessibility evidence incomplete | reproduced Dashboard/table traps, missing stable IDs/names, missing return focus | RM-152 contracts, expected-red, implementation, native keyboard/Narrator |
| `UI-141-014` native DPI evidence incomplete | unsupported 1366@125 minimum, no geometry guard/manifest evidence, one-monitor host | responsive/geometry tests and actual matrix; exceptions require owner approval |
| native environment gap | only one 1920x1080@100 display discovered | multi-monitor and unavailable scale cells remain `NOT_EXECUTED` until run or approved |
| packaged DPI mode incomplete | new EXE built and automated self-test passed; embedded manifest has no DPI declaration | effective native process mode and multi-monitor behavior remain `NOT_EXECUTED`; no DPI-mode change made |

This audit authorizes no domain, schema, dependency, network, provider, keyring, scoring, or
decision change. The unrelated root-checkout `.agents/` and `skills-lock.json` remain untouched.
