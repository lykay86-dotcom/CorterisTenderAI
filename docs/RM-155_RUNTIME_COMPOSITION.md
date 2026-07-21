# RM-155 runtime composition

## Canonical owner graph

```text
app.main
  -> bootstrap()
     -> initialize core/database/AI/search runtime
     -> QApplication (one)
     -> ModernMainWindow (one production QMainWindow)
        -> DashboardLayout (one route/stack owner)
           -> DashboardPage + DashboardController
           -> TenderWorkspacePage + installed TenderSearchUiController
           -> BusinessWorkflowPage + BusinessMetricsRepository
           -> TenderAnalyticsPage + optional TenderAnalyticsController
     -> application.exec()
     -> idempotent controller/owner shutdown
```

`app.ui.main_window.MainWindow` is absent from this graph. PyInstaller starts `app/main.py` and
collects no hidden import for the old module. The one-file self-test imports analytics/charts and
does not import the old shell.

## Acceptance snapshot

The implementation guard must prove: one `QApplication`, one production `QMainWindow`, one
`DashboardLayout`, one `QStackedWidget`, four physical pages, one workflow repository/page/health
monitor, one route registry, no nested `QMainWindow`, and no `quotes_page`/`estimates_page`
attributes. Repeated construct, route and close must have non-positive retained growth for
`QObject`, `QThread`, `QTimer` and Python threads after bounded deferred-delete processing.

Shutdown order remains tender-search veto, workflow shutdown, Dashboard shutdown, analytics
shutdown, Qt close. The post-event-loop tender-search shutdown is a documented idempotent
secondary call and is not a second owner.
