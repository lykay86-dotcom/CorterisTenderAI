# RM-155 public import contract

## Supported allowlist relevant to the redesign

| Import path | Symbols/purpose | Decision and parity guard |
|---|---|---|
| `app.ui.modern_main_window` | `ModernMainWindow`, production shell | KEEP; composition/frozen tests |
| `app.ui.pages.tender_workspace_page` | page and live legacy-platform notice constants | KEEP; page/action tests |
| `app.ui.controllers` | `DashboardController` and accepted controllers | KEEP; workflow import smoke |
| `app.ui.navigation` | route/context/history/registry contracts | KEEP; RM-142 tests |
| `app.ui.theme` | versioned tokens/palettes/icons | KEEP; design-system/visual tests |
| `app.ui.charts` | `corteris-chart-v1` public API | KEEP; RM-146/frozen tests |
| `app.tenders.analytics` | deterministic analytics API | KEEP; RM-147/frozen tests |
| `app.financial` | Decimal/currency/numeric API | KEEP; RM-148 tests |
| `app.tenders.detail` | typed identity/detail/action API | KEEP; RM-149 tests |
| `app.ui.tables` | immutable table presentation API | KEEP; RM-150 tests |
| `app.operations` | episode/feedback/notification API | KEEP; RM-151 tests |

## Retired boundary

`app.ui.main_window` is not a supported post-RM-155 public import. It was an application-internal
compatibility boundary retained by RM-144 explicitly through RM-155. No user/developer guide,
plugin entry point, frozen hidden import, package `__init__`, or production call imports it.
Repository tests are migrated to the allowlisted page/shell owners before deletion. No runtime
deprecation warning is emitted because importing the retired module is not part of normal startup
and a warning would preserve the duplicate import path.

A supported shim must remain type-identical, I/O-free, owner-free and explicit. No remaining shim
may construct a repository, service, controller, worker, network client or keyring reader.
