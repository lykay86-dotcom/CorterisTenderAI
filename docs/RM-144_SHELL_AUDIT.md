# RM-144 production shell and lifecycle audit

## Scope and entry gate

This audit is read-only evidence for findings `UI-141-004` and `UI-141-005`. It does not authorize
RM-145+ work, a new router, worker framework, repository, dependency, schema change, or any change
to deterministic scoring, recommendation, or critical stop-factor priority.

The RM-144 branch `feat/rm-144-production-shell` was created in the dedicated worktree
`.worktrees/rm144` from exact RM-143 docs-only closeout merge
`b790d3a981b7e056fa9f548d6686a1a95d5bf49a` (2026-07-19, PR #95). The closeout follows RM-143
feature PR #94, feature merge `c8d111f3db615dd3c21c231bf265bb00093c65bd`, successful exact
feature merge-SHA Quality Gate run `29663124774`, and successful exact closeout merge-SHA Quality
Gate run `29663578969`. The final run completed every required step on Python 3.12 (`3m39s`) and
Python 3.13 (`4m30s`), including full pytest and dependency audit. Canonical documents mark RM-143
`DONE`, RM-144 as the sole `IN PROGRESS` stage, and RM-145--RM-200 `PLANNED`.

The dedicated worktree was clean before validation. The exact baseline full suite, run with
`QT_QPA_PLATFORM=offscreen` and a repository-local isolated base temp, passed:

```text
2059 passed, 2 warnings in 230.49s (0:03:50)
```

Both warnings are the existing openpyxl unsupported-extension and conditional-formatting warnings
from `test_rm132_legacy_credentials_handoff.py`. The run created only the audit-owned untracked
`.pytest-tmp-rm144-baseline/`; unrelated files in the root checkout remain untouched.

## Production bootstrap and window consumers

The production path is `app/main.py -> app.bootstrap.bootstrap() -> QApplication ->
ModernMainWindow`. Bootstrap creates one `ModernMainWindow`, installs one
`TenderSearchUiController` on that window and its tender page, then enters `QApplication.exec()`.
It does not import or construct compatibility `MainWindow`.

There are two application `QMainWindow` subclasses:

| Class | Runtime consumer | Disposition |
|---|---|---|
| `app.ui.modern_main_window.ModernMainWindow` | `app.bootstrap.bootstrap()` | Sole production root. |
| `app.ui.main_window.MainWindow` | RM-127 compatibility test and external compatibility imports | Keep as a thin, separately constructible wrapper through RM-155; never nest in production. |

Other test-local `QMainWindow()` objects are controller fixtures, not application shells. The
build spec reaches the shell through `app.main`/`app.bootstrap`; it has no explicit hidden import
for either tender module. Build/frozen contracts therefore depend on normal import discovery and
must smoke-import the canonical page after extraction.

## Baseline page stack and owner graph

`ModernMainWindow` constructs one `DashboardLayout`, the sole `QStackedWidget`/navigation owner,
and eagerly registers four physical destinations:

| Legacy page key | Canonical route use | Physical owner at baseline |
|---|---|---|
| `dashboard` | `RouteId.DASHBOARD` | one `DashboardPage` |
| `tenders` | Tenders and embedded tender routes | one `TenderWorkspacePage` |
| `quotes` | Workflow, proposals, projects | first `BusinessWorkflowPage` |
| `estimates` | Estimates | second `BusinessWorkflowPage` |

The typed RM-142 registry remains the metadata owner, but its workflow specs currently expose two
destinations (`quotes`, `estimates`). `ModernMainWindow` also registers two context providers and
chooses between the two pages in `_activate_workflow()`. This is the exact duplication RM-144 must
remove; it is not permission to add another stack or router.

The baseline logical object graph is:

```text
QApplication
└── ModernMainWindow
    ├── DashboardLayout / one QStackedWidget
    ├── DashboardPage -> DashboardController
    ├── TenderWorkspacePage -> installed TenderSearchUiController
    ├── BusinessWorkflowPage (quotes)
    │   └── services + SystemHealthMonitor + auto-backup/health timers
    └── BusinessWorkflowPage (estimates)
        └── second services + SystemHealthMonitor + auto-backup/health timers
```

`BusinessMetricsRepository` is created once by the shell and passed to both workflow pages, but
each page creates its own exporters, importers, template/backup/catalog/database-health/crash/
system-health/auto-backup services and journal-facing monitor. Sharing the repository therefore
does not remove duplicate stateful scheduling and lifecycle ownership.

## Isolated runtime inventory and reproduction

An offscreen run used the existing RM-127 dependency isolation, disabled Dashboard startup,
replaced socket connect with a counter, constructed the production shell, processed events, and
immediately closed/deleted it. Before close it observed:

| Measure | Baseline result |
|---|---:|
| `QApplication` instances | 1 |
| top-level `QMainWindow` objects | 1 |
| nested `QMainWindow` objects | 0 |
| `DashboardLayout` objects | 1 |
| registered physical pages | 4 |
| `TenderWorkspacePage` objects | 1 |
| `BusinessWorkflowPage` objects | 2 |
| `SystemHealthMonitor` objects | 2 |
| page-owned auto-backup/health timers | 4 active |
| all active descendant workflow timers, including two status-banner hide timers | 6 |
| active health jobs after event processing | 2 |
| socket connect attempts | 0 |

Both health workers outlived page deletion and deterministically reproduced, twice:

```text
Error calling Python override of QRunnable::run():
RuntimeError: Signal source has been deleted
```

The first failure occurred on `snapshot_ready.emit`; the `finally` emission of `finished` then
failed for the same deleted signal source. This independently confirms RM-141 finding
`UI-141-005` on the RM-144 baseline. No network attempt, hang, thread-destroyed warning, or data
loss was observed; those absences do not make the deleted-source error safe.

## Tender workspace import and compatibility map

The implementation class is currently defined in `app/ui/main_window.py`. The nominal canonical
module `app/ui/pages/tender_workspace_page.py` is only a three-line re-export. Consumers are:

- production `ModernMainWindow` imports the public pages path and constructs exactly one instance;
- `app.ui.main_window.MainWindow` constructs the same class as its sole central widget;
- RM-127/RM-128 composition tests use the public pages path;
- RM-132 and RM-142 characterization import the legacy path;
- RM-131/RM-133 import legacy handoff constants from `app.ui.main_window`;
- RM-127/RM-132 monkeypatch dependency names in `app.ui.main_window` because implementation globals
  currently live there;
- `scripts.audit_ui_inventory` classifies the old module as embedded legacy and the page module as
  compatibility-only; those classifications must move with the implementation;
- bootstrap installs the existing search controller on `window.tender_workspace_page`; the nine
  action/shortcut instances, unified-search panel, status bar, tender-ID opening, eight section
  object names, and six settings-section object names are page/controller compatibility contracts.

No dynamic application import or string-based class lookup was found. The extraction decision is
a mechanical move of one implementation, constants, and required imports to
`app.ui.pages.tender_workspace_page`; `app.ui.main_window` will import that exact class object and
retain only the thin `MainWindow` wrapper plus public compatibility re-exports. Test monkeypatches
will target the implementation module after the move. Public class identity, not implementation
dependency globals, is the compatibility guarantee.

## Thread, timer, and shutdown inventory

`SystemHealthMonitor` defaults to `QThreadPool.globalInstance()`, starts an auto-delete
`QRunnable`, stores its worker while `_running`, and has no closing state or shutdown method. The
worker owns a separate signals `QObject`; page deletion can delete that signal source while
`run()` still emits. Duplicate refresh alone returns `False`, but refresh after owner close is not
defined.

Each `BusinessWorkflowPage` starts two repeating timers and two unowned `QTimer.singleShot`
callbacks (`0 ms` database safety and `250 ms` health refresh). It connects `workflow_changed` to
automatic backup and health scheduling. It has no `shutdown`, `close_lifecycle`, or `closeEvent`.

`DashboardController.shutdown()` stops its owned timer and bounded-waits its specific `QThread`.
`TenderSearchUiController.shutdown()` is idempotent, rejects new work, cancels tracked workers,
uses a deadline, and may veto close; it waits on its own pool only when it owns that pool.
`ModernMainWindow.closeEvent()` currently calls tender-search shutdown first, vetoes on `False`,
then shuts down Dashboard in `finally`, but never closes workflow scheduling/monitor ownership.
Bootstrap calls tender-search shutdown again after the event loop, relying on idempotency.

## Risks and accepted audit decisions

- Close must not wait for the global thread pool or affect foreign jobs. Give each health monitor a
  dedicated owned pool and retain its running worker/signal source until a bounded monitor-specific
  drain completes.
- Page-facing delivery must be lifecycle/generation guarded even when the collector completes near
  the close boundary. Stopping timers alone is insufficient.
- The two workflow physical destinations must converge on one `workflow` destination and one
  `workflow_page`; `quotes_page` and `estimates_page` may remain temporary same-object aliases only
  for audited compatibility.
- Close preflight remains tender-search-first. Once accepted, workflow and Dashboard shutdown are
  once-only terminal actions; navigation/actions are rejected after shell close begins.
- Extraction must not mix behavioral UI hierarchy changes with the move, create another tender
  controller, or change object names, actions, settings, DB, AI, search, or decision semantics.
