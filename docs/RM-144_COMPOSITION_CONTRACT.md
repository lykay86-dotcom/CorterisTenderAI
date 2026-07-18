# RM-144 production composition contract

## Target owner graph

RM-144 has one production root and one physical page per mature domain:

```text
QApplication / bootstrap
└── ModernMainWindow
    ├── DashboardLayout                  # sole navigation/page-stack owner
    ├── DashboardPage
    │   └── DashboardController          # one explicit shutdown owner
    ├── TenderWorkspacePage              # one canonical production page
    │   └── existing TenderSearchUiController/runtime
    └── BusinessWorkflowPage             # one canonical workflow_page
        ├── BusinessMetricsRepository
        ├── existing workflow services
        ├── SystemHealthMonitor
        ├── auto-backup timer
        └── system-health timer
```

The separate compatibility graph remains:

```text
app.ui.main_window.MainWindow
└── canonical TenderWorkspacePage
```

Bootstrap must never construct or nest compatibility `MainWindow`.

## Canonical modules and public identity

- `app.ui.modern_main_window.ModernMainWindow` is the production shell.
- `app.ui.pages.tender_workspace_page.TenderWorkspacePage` is the sole tender implementation.
- `app.ui.main_window.TenderWorkspacePage` is a compatibility import of that exact class object.
- `app.ui.main_window.MainWindow` remains a thin wrapper until RM-155.
- `app.ui.pages.business_workflow_page.BusinessWorkflowPage` remains the workflow UI owner.
- `app.ui.navigation` and `DashboardLayout` remain the only route metadata and activation/stack
  owners; RM-144 creates no router, event bus, or service locator.

Supported tender imports must satisfy identity, not merely `isinstance` equivalence. Existing
object names, eight tender sections, six settings sections, status-bar injection, unified-search
seam, tender-ID opening, and controller action/shortcut identity remain unchanged.

## Construction and one-instance rules

Construction order is settings/theme, `DashboardLayout`, Dashboard page/controller, tender page,
one business repository, one workflow page, navigation handlers/context provider, signal wiring,
theme propagation, initial Dashboard navigation, then Dashboard start. At startup:

- exactly one top-level production `QMainWindow` and no nested `QMainWindow`;
- one `DashboardLayout` and one `QStackedWidget`;
- one Dashboard page/controller, one tender page/controller stack, and one workflow page;
- one workflow repository owner, service set, health monitor, auto-backup timer, and health timer;
- no QWidget is added to the page stack twice.

Temporary `quotes_page` and `estimates_page` attributes are retained only as same-object aliases to
`workflow_page` for existing tests/external compatibility. They must never acquire independent
state, services, signal connections, or page-stack entries and are candidates for RM-155 removal.

## Route-to-page contract

The physical destinations after RM-144 are `dashboard`, `tenders`, and `workflow`.

| Route | Physical page | Activation intent |
|---|---|---|
| Dashboard | `dashboard_page` | existing Dashboard behavior |
| Tenders and tender embedded routes | `tender_workspace_page` | exact tender/settings section or ID through existing seams |
| Workflow | `workflow_page` | typed context/default presentation state |
| Workflow proposals | `workflow_page` | `kind=proposal` unless explicit valid context overrides |
| Workflow estimates | `workflow_page` | `kind=estimate` unless explicit valid context overrides |
| Workflow projects | `workflow_page` | `kind=project` unless explicit valid context overrides |

The legacy strings `quotes` and `estimates` continue resolving to their existing canonical route
IDs, but both route specs target the same physical `workflow` destination. The sole context
provider captures the active workflow page state. Filter, status, archive mode, search text and
stable record ID flow only through `RouteContext`/`WorkflowNavigationState`; failed or missing
selection remains explicit no-selection.

## Signal and controller ownership

The workflow page's `tender_open_requested` and `workflow_changed` signals are each connected once.
A workflow mutation refreshes the same page without peer synchronization, then refreshes Dashboard.
Theme propagation calls the workflow page once. Bootstrap support-bundle discovery prefers
`workflow_page` and may retain same-object legacy lookup fallback without invoking a provider twice.

Tender search remains the single bootstrap-created controller/runtime. It is installed once on the
production shell and the one tender page. RM-144 does not recreate actions, shortcuts, services,
or repositories and does not move deterministic business decisions into the UI.

## Close coordination

`ModernMainWindow.closeEvent()` is the production coordinator:

1. If already terminal, delegate safely to Qt without repeating owner shutdown.
2. Ask the existing tender-search shutdown contract first. `False` vetoes close and leaves
   Dashboard/workflow operational because terminal shutdown has not begun.
3. Mark the shell closing so navigation and shell actions cannot schedule new work.
4. Shut down the workflow page once; it stops page scheduling before closing its monitor.
5. Shut down Dashboard once using its existing bounded contract.
6. Mark the shell closed and call `super().closeEvent(event)`.

No global pool wait, worker termination, arbitrary sleep, modal dialog, backup, recovery, import,
or repository mutation is permitted during close. Repeated close and bootstrap's repeated tender
shutdown remain safe. A workflow shutdown failure must produce a stable veto/failure outcome; it
must not silently delete a running signal source.

## Compatibility disposition and rollback

Kept through RM-155: legacy `MainWindow`, tender class/constants imports, `quotes_page` and
`estimates_page` same-object aliases, legacy route strings, action/object/shortcut names, and
QSettings keys. Removed in RM-144: the duplicate workflow QWidget and its second services,
monitor, timers, stack destination, context provider, theme call, and peer refresh loop. Deferred:
retirement of all legacy exports, broad UI restyling, accessibility/performance work, and every
RM-145+ finding.

Rollback is a revert of the RM-144 code/tests/docs commits to baseline `b790d3a`. There is no DB,
schema, data, credential, schedule, route-history, or settings migration to reverse.
