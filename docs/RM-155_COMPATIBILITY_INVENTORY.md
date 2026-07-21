# RM-155 compatibility inventory

Evidence baseline: `119409b110a826f179355c914890bb8171af3e06`. Each row is one exact
candidate. `none` means the named consumer class was searched and not found; it is not inferred
from a single empty search.

| candidate_id | kind; path/symbol | introduced_by | replacement | consumers (runtime; test/history; frozen/settings/public) | decision | rollback; owner |
|---|---|---|---|---|---|---|
| RM155-COMP-001 | module `app/ui/main_window.py` | initial owner; reduced by `58ba458` RM-144 | `app.ui.pages.tender_workspace_page` + `ModernMainWindow` | none; RM-127/131--144 tests and history; no frozen/settings promise beyond RM-155 | REMOVE after symbols migrate | restore file; UI composition |
| RM155-COMP-002 | class `app.ui.main_window.MainWindow` | `cc1d8d7` RM-127 | `ModernMainWindow` production; `TenderWorkspacePage` fixture | none; two direct test modules and accepted history; no spec/import smoke | REMOVE | restore thin wrapper; UI composition |
| RM155-COMP-003 | export `app.ui.main_window.TenderWorkspacePage` | `58ba458` RM-144 | canonical page import | none; three direct tests; explicitly retained through RM-155 only | REMOVE | restore exact-class re-export; tender page |
| RM155-COMP-004 | export `LEGACY_PLATFORM_COMPATIBILITY_NOTICE` from old module | `58ba458` | same symbol in canonical page | none; RM-131/133 tests; not frozen/persisted | REMOVE re-export, KEEP canonical symbol | restore import/export; tender page |
| RM155-COMP-005 | export `LEGACY_PLATFORM_CREDENTIAL_NOTICE` from old module | `f9365ea`/`58ba458` | same symbol in canonical page | none; RM-132/133 tests; not frozen/persisted | REMOVE re-export, KEEP canonical symbol | restore import/export; tender page |
| RM155-COMP-006 | export `LEGACY_PLATFORM_PROVIDER_ACTION_TEXT` from old module | `58ba458` | same symbol in canonical page | none; RM-131/133 tests; not frozen/persisted | REMOVE re-export, KEEP canonical symbol | restore import/export; tender page |
| RM155-COMP-007 | attribute `ModernMainWindow.quotes_page` | `9b998a0` RM-144 | `workflow_page` | bootstrap fallback; RM-142/144 tests/history; no persistence/frozen promise | MIGRATE then REMOVE | re-add same-object alias; shell |
| RM155-COMP-008 | attribute `ModernMainWindow.estimates_page` | `9b998a0` RM-144 | `workflow_page` | bootstrap fallback; RM-142/144 tests/history; no persistence/frozen promise | MIGRATE then REMOVE | re-add same-object alias; shell |
| RM155-COMP-009 | fallback `_find_support_bundle_provider(...quotes_page)` | pre-RM-144, retained by `9b998a0` | `workflow_page` | production bootstrap only; direct fallback test; no persistence | REMOVE after parity test | restore lookup item; bootstrap |
| RM155-COMP-010 | fallback `_find_support_bundle_provider(...estimates_page)` | pre-RM-144, retained by `9b998a0` | `workflow_page` | production bootstrap only; fixture attribute; no persistence | REMOVE after parity test | restore lookup item; bootstrap |
| RM155-COMP-011 | method `TenderWorkspacePage.apply_compatibility_search_text` | moved by `58ba458`; original RM-127 seam | `submit_unified_search_text` for global search; direct field in focused page tests | no runtime caller; one RM-127 test/history; no frozen/settings | REMOVE | restore three-line method; tender page |
| RM155-COMP-012 | route alias `dashboard` | `27d98f6` RM-142 | canonical `workspace.dashboard` | sidebar/page keys and tests; object name/visual automation; no persisted route store | KEEP | revert registry change; navigation |
| RM155-COMP-013 | route alias `tenders` | `27d98f6` | canonical `workspace.tenders` | sidebar/page keys, tests, deep links; object name/visual | KEEP | revert registry change; navigation |
| RM155-COMP-014 | route alias `quotes` | `27d98f6` | `workspace.workflow.proposals` | retained route tests/history; exact proposal meaning | KEEP | revert registry change; navigation |
| RM155-COMP-015 | route alias `estimates` | `27d98f6` | `workspace.workflow.estimates` | retained route tests/history; exact estimate meaning | KEEP | revert registry change; navigation |
| RM155-COMP-016 | route alias `ai` | `27d98f6` | `workspace.tenders.ai` | compatibility navigation tests; embedded settings admission | KEEP | revert registry change; navigation |
| RM155-COMP-017 | route alias `settings` | `27d98f6` | `workspace.tenders.settings` | route contract/history; embedded settings admission | KEEP | revert registry change; navigation |
| RM155-COMP-018 | route alias `documents` | `27d98f6` | `workspace.tenders.documents` | route contract; context-required safe admission | KEEP | revert registry change; navigation |
| RM155-COMP-019 | route alias `analytics` | `27d98f6`, activated `40b8339` | canonical `future.analytics` | sidebar, visual fixtures, RM-147/153 tests | KEEP | revert registry change; analytics/navigation |
| RM155-COMP-020 | route alias `clients` | `27d98f6` | planned `future.clients` | safe planned-route tests and RM-156 handoff; no product page | KEEP until RM-156 decision | revert registry change; navigation/RM-156 |
| RM155-COMP-021 | enum `RouteId.FUTURE_ANALYTICS` | `27d98f6`, semantics accepted RM-147 | same stable enum/value | production shell, fixtures, many contract tests; accepted public navigation import | KEEP | restore enum member; navigation |
| RM155-COMP-022 | setting `ui/theme` values `dark`/`light` | pre-RM-142; retained RM-143/153 | current setting owner | production QSettings, native/visual tests and user state | KEEP | restore setting read/write; shell/theme |
| RM155-COMP-023 | action/shortcut object names in tender controller | RM-127--140 | current QAction owners | production menus/toolbars, tests, accessibility; user muscle memory | KEEP | revert exact action change; tender controller |
| RM155-COMP-024 | `TenderWorkspacePage` section/settings object names | RM-127; retained RM-152/154 | current page | QSS, tests, UIA and visual fixtures | KEEP | restore exact object names; tender page |
| RM155-COMP-025 | alias `ChartSourceEvidence` | RM-146 | RM-145 `DashboardSourceEvidence` exact type | chart public API, analytics tests/frozen smoke | KEEP; not duplicate | restore alias; charts |
| RM155-COMP-026 | `LegacyCollectorNotificationAdapter` | RM-151 | canonical notification envelope | scheduler persisted schema-v1 rows/tests | KEEP; migration boundary | restore adapter; operations |
| RM155-COMP-027 | RM-148 legacy v1/v2 financial readers/migration | RM-148 | v3 repository | persisted user JSON, backup/recovery tests | KEEP | revert only with data plan; financial repository |
| RM155-COMP-028 | RM-149 `legacy_orm` identity namespace | RM-149 | no safe registry bridge exists | Dashboard deep links and explicit fail-closed tests | KEEP | restore identity member; tender detail |
| RM155-COMP-029 | RM-150 legacy table roles/adapters | RM-150 | common table contract where migrated | retained QTableWidget consumers/tests | KEEP per migrate/keep matrix | restore adapter; table owners |
| RM155-COMP-030 | RM-152 owner exceptions/native matrix | RM-152 owner decision | none; truthful evidence | strict validator/docs; not product runtime | KEEP evidence | revert docs only by owner decision; accessibility |
| RM155-COMP-031 | RM-153 benchmark/profile hooks | RM-153 | test-only scripts | performance tests/docs; no production import | KEEP test-only | restore scripts; performance |
| RM155-COMP-032 | RM-154 baselines/candidate tooling | RM-154 | canonical visual workflow | CI/tests; spec explicitly excludes artifacts | KEEP test-only, verify not frozen | restore tooling; visual QA |

No candidate is `BLOCKED`. No deprecation warning is added: the removable contracts have no
documented external support promise beyond RM-155, while retained contracts remain fully
supported.
