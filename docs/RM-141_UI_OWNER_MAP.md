# RM-141 UI production composition and owner map

## Confirmed production chain

```text
app/main.py
  -> app.bootstrap.bootstrap()
  -> core/database/AI/search runtime initialization
  -> QApplication
  -> ModernMainWindow
     -> DashboardLayout -> Sidebar + TopBar + QStackedWidget
     -> DashboardPage <-> DashboardController -> repositories
     -> TenderWorkspacePage (implemented in app.ui.main_window)
     -> BusinessWorkflowPage x2 -> one BusinessMetricsRepository
     -> five placeholder QWidget instances
  -> TenderSearchUiController
     -> installed on ModernMainWindow and TenderWorkspacePage
     -> TenderSearchRuntime/services/repositories/workers/dialogs
```

This chain is confirmed by `app/main.py`, `app/bootstrap.py`, runtime offscreen composition and Git
history. Commits `a537165` and `a1d8fa0` introduced the shell and tender integration; `cc1d8d7` and
`4a037ea` extracted/mounted the public tender page while retaining implementation in
`app.ui.main_window`. RM-128–RM-140 then consolidated the search runtime and lifecycle around that
composition.

## Ownership register

| Surface/object | Created by | Data/service owner | Thread boundary | Shutdown/lifetime owner | Ambiguity/risk |
|---|---|---|---|---|---|
| `QApplication` | `bootstrap()` | application context | UI thread | `bootstrap()` after `exec()` | none |
| `ModernMainWindow` | `bootstrap()` | shell `QSettings`, status bar | UI thread | Qt close + bootstrap | close event explicitly covers search and dashboard only |
| `DashboardLayout`, Sidebar, TopBar | shell | route dictionary, UI state | UI thread | shell QObject tree | string routes; no route-state model |
| `DashboardPage` | shell | `DashboardViewModel` presentation state | UI thread | shell | state contracts strongest UI area |
| `DashboardController` | shell | tender/business repositories and snapshot builder | `QThreadPool` refresh worker | shell `closeEvent()` calls `shutdown()` | covered by focused shutdown tests |
| `TenderWorkspacePage` | shell | legacy page widgets and injected status bar | UI thread plus controller workers | shell QObject tree | public module re-exports implementation from legacy file |
| `TenderSearchUiController` | bootstrap | `TenderSearchRuntime`, dialogs, worker signals | `QThreadPool`; RM-140 terminal states | controller; shell and bootstrap both call `shutdown()` | deliberate idempotent double shutdown path |
| `BusinessMetricsRepository` | shell | JSON workflow records/audit | synchronous caller | shell | one repository shared by two eagerly created pages |
| `BusinessWorkflowPage` quotes | shell | shared repository, exporters/importers/backups/health services created in page by default | UI thread plus system-health pool runnable, two timers | QObject tree only | direct IO/service construction; late worker signals reproduced on rapid close |
| `BusinessWorkflowPage` estimates | shell | same as quotes | same as quotes | same as quotes | duplicate service/timer/monitor instances over one repository |
| Five placeholders | shell | none | UI thread | shell | routes look available but have no workflow |
| Search/provider/profile/registry dialogs | `TenderSearchUiController` or tender page action | injected adapters/services/repositories | UI plus controller worker boundaries | dialog/controller | many valid compatibility entry points; not dead |
| Workflow/backup/import/health dialogs | `BusinessWorkflowPage` | page-owned services/repository | mostly synchronous UI thread | dialog/page | persistence and presentation ownership mixed |
| Crash bridge/dialogs | `bootstrap()` | `GlobalCrashHandler`, report service | exception callback -> Qt bridge | bootstrap/application | raw diagnostic data needs policy review in RM-151 |
| Theme | shell, then page/component propagation | `ThemePalette`, `Typography`, QSS, QSettings | UI thread | shell | propagation is explicit and incomplete for embedded/local styles |

## Eager/lazy composition

The shell eagerly constructs Dashboard, tender workspace, two Business Workflow pages and five
placeholders before it is shown. Dashboard refresh starts immediately. Both workflow pages start
automatic-backup and system-health timers and schedule health work during construction. Dialogs
are created on demand by page/controller actions. The tender controller is created after the
window and installed into both shell and embedded page.

## Signals, navigation, and mutable state

- Sidebar selection changes the stacked page and top-bar title through `DashboardLayout`.
- Dashboard quick actions select tender/quotes/estimates/AI routes; tender selection calls
  `TenderWorkspacePage.open_tender(tender_id)`.
- Workflow changes refresh the sibling workflow page and Dashboard.
- Top-bar global search routes to tenders and delegates to
  `TenderWorkspacePage.submit_unified_search_text()`.
- Theme selection is stored under `ui/theme`, applied globally, then explicitly propagated to
  Dashboard and both workflow pages.
- Search lifecycle state belongs to `TenderSearchUiController`; deterministic score,
  recommendation, and stop-factor decisions remain in domain/application owners and are only
  rendered by UI.

## Lifecycle characterization

An isolated shell open/close run did not use the network and created only one `QMainWindow`. Rapid
close reproduced twice:

```text
Error calling Python override of QRunnable::run():
RuntimeError: Signal source has been deleted
```

The source was `app/core/system_health_monitor.py` worker signal emission after a page-owned signal
receiver had been deleted. This is finding `UI-141-004`, not a production fix in RM-141. Existing
RM-140 shutdown guarantees remain valid for tender search; the separate workflow-health owner is
the uncovered boundary.

## Owner decisions for later RMs

- RM-142 owns route taxonomy and state preservation; it must not move business ownership.
- RM-144 owns convergence on one production shell/composition and explicit page lifecycle.
- RM-151 owns background-operation episodes and user-facing failure policy.
- RM-153 owns measured startup/render/update budgets and removal of UI-thread IO.
- Compatibility imports, action names, shortcuts, settings keys, object names, and tender-ID deep
  links remain regression guards until RM-155 explicitly retires them.

No new controller, repository, service, or dependency is proposed by this map.
