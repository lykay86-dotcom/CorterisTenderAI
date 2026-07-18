# RM-142 information architecture audit

## Verdict

RM-142 can be implemented without a second shell, router, repository, service, database change, or
domain-logic move. The current production shell has one `QMainWindow` and one `QStackedWidget`, but
route metadata and navigation behavior are duplicated across `Sidebar`, `DashboardLayout`,
`ModernMainWindow`, Dashboard signals, and controller actions. There is no canonical typed route
model, result, context, history, or focus-return owner.

The accepted target is one immutable route registry in `app.ui.navigation` and the existing
`DashboardLayout` as the sole production page-activation/navigation owner. `ModernMainWindow`
continues to compose physical pages and bind existing actions; Sidebar, TopBar, Dashboard and legacy
string calls become intent producers or thin compatibility adapters.

`DB migration: not required`. Navigation state and bounded history are in memory only. Existing
`ui/theme` persistence is unchanged and no new `QSettings`, JSON, SQLite, keyring, or file write is
introduced.

## Evidence and entry gate

- Audit date: 2026-07-18; Windows 10, Python 3.12.7, Qt offscreen.
- Baseline, branch HEAD and `origin/main` at branch creation:
  `999354c892326765792308b2c40a0c8b7236f717`.
- Branch/worktree: `feat/rm-142-information-architecture`, isolated `.worktrees/rm142`.
- RM-141 audit PR #90 merged as
  `a2e8d0528a1b9c6378a543a5c9f2c5b762483c63`; exact-SHA run `29655095879` passed on
  Python 3.12/3.13 including dependency audit.
- RM-141 closeout PR #91 merged as the baseline above; exact-SHA run `29655615482` passed on
  Python 3.12/3.13.
- Canonical documents name RM-142 as the sole `IN PROGRESS` stage; RM-143–RM-200 remain `PLANNED`.
- Clean RM-142 baseline: `1946 passed, 2 warnings in 161.36s`. The two warnings are the accepted
  openpyxl warnings in `test_rm132_legacy_credentials_handoff.py`.
- Root-checkout user files `.agents/` and `skills-lock.json`, and unrelated root stat/line-ending
  state, are outside this worktree and remain untouched.

Read evidence includes all canonical project documents and six RM-141 artifacts; RM-127/RM-128
composition/search contracts; RM-129–RM-139 compatibility, identity, UI and lifecycle guards;
RM-140 audit/contract/acceptance; production composition; relevant UI models/controllers/tests; and
Git history for route keys, actions, shortcuts, object names and deep links.

## Production composition and physical owners

```text
app.main -> bootstrap -> QApplication -> ModernMainWindow (only production QMainWindow)
  -> DashboardLayout (Sidebar + TopBar + one QStackedWidget)
     -> DashboardPage
     -> TenderWorkspacePage (public re-export; implemented by app.ui.main_window)
     -> BusinessWorkflowPage(PROPOSAL)
     -> BusinessWorkflowPage(ESTIMATE)
     -> five placeholder QWidget pages
  -> one TenderSearchUiController installed on shell and tender workspace
```

| Surface | Physical/runtime owner | Current navigation responsibility | Audit decision |
|---|---|---|---|
| production window | `ModernMainWindow` | constructs pages, wires signals and string keys | retain composition/binding role |
| page stack | `DashboardLayout.pages` | `_page_index`, activation and title | sole RM-142 navigation owner |
| primary navigation | `Sidebar` | hard-coded nine-item list and `.select(str)` | render registry; keep thin `.select` adapter |
| page title/global controls | `TopBar` | title sink plus search/AI/notification intents | metadata sink/intent producer only |
| Dashboard actions | `DashboardPage`/`QuickActions` | four string actions become four signals | preserve signals; resolve through route API |
| tender page | `TenderWorkspacePage` in `app.ui.main_window` | tabs, exact tender open, unified-search seam | retain real owner and stable page API |
| workflow data | one `BusinessMetricsRepository` | shared by two eager workflow pages | retain owner; taxonomy becomes one area |
| workflow views | `quotes_page`, `estimates_page` | initial kind, filters, selected record | retain physical pages through RM-144 |
| tender dialogs/actions | `TenderSearchUiController` and scheduler controller | mature modal destinations/shortcuts | reuse same QAction/controller instances |

`DashboardLayout._page_index` currently duplicates title metadata and silently ignores unknown keys.
It may remain only as a generated compatibility view of registered page bindings; it must not remain
an independent route map beside the canonical registry.

## Current string-route register and disposition

| Legacy key | Current physical result | Actual maturity | RM-142 disposition |
|---|---|---|---|
| `dashboard` | `DashboardPage` | available | alias of canonical Dashboard primary route |
| `tenders` | `TenderWorkspacePage` | available | alias of canonical Tenders primary route |
| `ai` | placeholder page | AI settings/recheck are mature inside tender workspace | compatibility alias to embedded AI destination; not primary |
| `quotes` | proposal-filtered workflow page | available view of shared workflow domain | alias of proposal child intent |
| `estimates` | estimate-filtered workflow page | available view of shared workflow domain | alias of estimate child intent |
| `documents` | placeholder page | tender documents are mature only with tender context | context-required tender-documents destination; not primary |
| `clients` | placeholder page | no mature client workflow | planned destination, target RM-156 |
| `analytics` | placeholder page | no chart/analytics owner | planned destination, target RM-147 |
| `settings` | placeholder page | six mature settings tabs are embedded in tender workspace | compatibility alias to embedded settings destination; not primary |

The five placeholders are `ai`, `documents`, `clients`, `analytics`, and `settings`. Navigation to
them is currently treated as successful page activation even though no user job is completed. The
first, second and fifth have mature embedded/contextual destinations; clients and analytics are
future work. None should remain a false primary peer.

## Entry-point and consumer map

### Sidebar, page stack and title

- `create_default_sidebar()` hard-codes nine keys/titles/icons and selects `dashboard` before page
  registration.
- `DashboardLayout.add_page(key, title, widget)` stores `(index, title)` in `_page_index`.
- `Sidebar.select(key)` silently returns for unknown/non-visible keys, checks a button and emits the
  raw string.
- `DashboardLayout._activate(key)` silently returns for unknown keys, changes stack index and copies
  the duplicated title into TopBar.
- No request result, unavailable state, context validation, history, back, return or focus restore
  exists.

### TopBar

- Enter in search emits one string; `ModernMainWindow._global_search()` selects `tenders` and
  delegates to `TenderWorkspacePage.submit_unified_search_text()`. RM-128 guarantees this does not
  alter equipment `catalog_query`; RM-140 owns accepted-run lifecycle.
- AI selects the false `ai` placeholder even though real AI settings are
  `TenderWorkspaceSection_settings` / `TenderWorkspaceSettingsSection_ai` and recheck is controller
  owned.
- Notifications show a shell message-box stub while the mature notification dialog is the existing
  scheduler-controller action.
- Profile is an informational modal; theme uses existing `ui/theme` and is not a route-state store.

### Dashboard and deep links

- Stable quick-action keys are `find_tenders`, `analyze_documents`, `create_proposal`, and
  `create_estimate`; their existing public signals are compatibility inputs.
- Quick actions currently select `tenders`, `ai`, `quotes`, or `estimates` directly.
- Tender feed/activity/advisor emit the exact string tender identity. The shell first selects
  `tenders`, then calls `TenderWorkspacePage.open_tender(tender_id)`. Missing IDs leave the existing
  tender selection intact but still change the outer route.
- RM-142 must validate the exact ID before committing route/history, never derive an ID from title,
  URL, score or row index, and must not calculate a recommendation.

### Tender tabs, dialogs, shortcuts and notifications

- Tender top-level stable keys: `overview`, `analysis`, `estimate`, `catalog`, `readiness`, `tools`,
  `price_monitor`, `settings`.
- Nested settings keys: `platforms`, `ai`, `company`, `economics`, `templates`, `database`.
- Existing controller QAction identities remain the action owners:
  `actionTenderSearchProfiles` (`Ctrl+Shift+F`), `actionTenderRegistry` (`Ctrl+Shift+R`),
  `actionTenderProviders` (`Ctrl+Shift+S`), `actionTenderCollector` (`Ctrl+Shift+C`),
  `actionCompanyCapabilityProfile`, `actionMatchingCatalog`, `actionAggregatorDiscoveryQueue`,
  `actionTenderCollectorSchedule` (`Ctrl+Shift+P`), and
  `actionTenderCollectorNotifications` (`Ctrl+Shift+N`).
- Navigation may invoke/reveal these existing actions but cannot recreate them, reparent them, read
  credentials, open network connections, or bypass RM-140 admission/shutdown.

### Business workflow state

- Both physical pages share one repository and stable `BusinessWorkflowRecord.id` values.
- `initial_kind` differs, while kind/status/archive/search filters and selection are page-local.
- `refresh()` restores the initial filter and selects the first visible row unless a preferred stable
  ID is supplied. Filter changes also select the first visible row.
- There is no public immutable capture/restore navigation state. A new narrow page seam is required
  so route changes preserve filters and stable selection and represent missing/out-of-scope selection
  as explicit none, never as the adjacent row.
- Repository, JSON schema, import/export/history/archive/restore and monetary types are outside
  RM-142 and remain unchanged.

## As-is selection, history and focus behavior

- Outer page selection and title are synchronous and string based.
- Consecutive selections have no typed `NO_CHANGE`; unknown selection is an unobservable no-op.
- Planned/placeholder selection changes route/title as if successful.
- There is no browser-like history, back/return operation or bounded snapshot store.
- Inner tender tabs, workflow filters and selection are not part of outer navigation state.
- Sidebar selection checks the clicked button, but quick actions/global search do not preserve a
  focus-origin token. Deep links do not provide a return-focus contract.
- No navigation object currently retains QWidget references; RM-142 must preserve that safety by
  using allowlisted string tokens and page-level fallbacks.

## Git and compatibility evidence

- `d6a4b12`, `3be4d17`, `d108e6d`, `a537165`: hard-coded Sidebar/TopBar/Layout/modern shell were
  introduced as separate layers.
- `1a65250` and `999813c`: Dashboard quick actions and tender deep-link shell wiring.
- `cc1d8d7` and `4a037ea`: reusable tender page and direct modern-shell composition; public import,
  stable tabs, action identity and one `QMainWindow` must remain.
- `777079e` and `8f7dca8`: one unified-search controller seam and topbar delegation.
- `d59887e`: one RM-140 admission/lifecycle owner and tender-before-dashboard close order.

Existing regression guards include RM-127 page/composition, RM-128 unified-search composition,
RM-140 offline/shutdown/compatibility, Dashboard feed/quick-actions/controller, workflow
model/filter/history/export, AI settings no-readback, scheduler and notification tests.

## Security, authority and persistence decision

- Route context will be a closed immutable type, not an arbitrary mapping.
- Allowed values are bounded presentation identities/state only: tender ID, workflow kind/filters,
  workflow record ID, safe search draft, embedded section IDs and focus token.
- QWidget/QObject, domain records, repositories/services/controllers, secrets, paths, raw exceptions,
  URLs and AI output are prohibited.
- Unknown routes/context fields return typed safe failures and do not alter route/history/selection.
- Registry resolution performs no repository, file, database, keyring or network I/O.
- RM-107 score/recommendation, hard exclusions and critical stop-factor priority remain unchanged;
  AI remains advisory.
- No persisted route state exists or is needed. Database/schema/migration versions and existing
  `ui/theme` behavior remain byte/semantically unchanged.

## Audit decision

**ACCEPTED FOR DOCS-ONLY COMMIT.** The implementation may proceed only after this audit, the
contract and implementation plan are committed together. The approved architecture has one
canonical route registry and one production navigation owner (`DashboardLayout`), retains one page
stack and all mature owners, removes false peer behavior, and makes every legacy key an explicit
tested alias/disposition.
