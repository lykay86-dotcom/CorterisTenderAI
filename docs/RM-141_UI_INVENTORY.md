# RM-141 UI inventory

## Scope and evidence

This is an audit-only inventory of the PySide6 surface at baseline
`8e704cf74c64e2125ace165807d1a33d3937b739`. It changes no production code. Counts are
reproducible with:

```powershell
python -m scripts.audit_ui_inventory --format summary
python -m scripts.audit_ui_inventory --format json
```

The script parses files and imports only; it does not open user data, initialize repositories,
read credentials, or use the network. Classification is a primary role, not a deletion decision.

## Totals

| Measure | Result |
|---|---:|
| `app/ui` Python modules | 68 |
| Lines in `app/ui` | 28,910 |
| UI/PySide6 test modules | 97 |
| Runtime widgets in isolated offscreen shell | 960 |
| Runtime focusable widgets | 275 |
| Runtime widgets with accessible name / description | 66 / 23 |
| Static `setAccessibleName` / `setAccessibleDescription` calls | 30 / 13 |
| `setBuddy` calls | 0 |
| Local `setStyleSheet` calls | 45 |
| Literal colors outside theme modules | `#2e8b57`, `#b22222` |
| Fixed / minimum / maximum dimension calls | 14 / 31 / 6 |
| `QTableWidget` / `QTableView` construction sites | 30 / 2 |
| `QTimer` / `QThread` construction sites | 6 / 1 |
| Image, icon, font, or Qt resource files under `app/ui` | 0 |

The runtime counts are diagnostic coverage indicators, not WCAG conformance ratios: not every
focusable control needs a custom accessible name, and Qt may expose visible labels implicitly.

## Module and component register

| Module | Primary classification | Main symbol(s) | Direct test consumers | Lines |
|---|---|---|---:|---:|
| `app.ui.__init__` | COMPATIBILITY_ONLY | package exports | 0 | 0 |
| `app.ui.aggregator_discovery_dialog` | PRODUCTION_DIALOG | `AggregatorDiscoveryDialog` | 1 | 87 |
| `app.ui.ai_provider_settings` | PRESENTATION_COMPONENT | `AiProviderSettingsWidget` | 1 | 157 |
| `app.ui.business_workflow.__init__` | COMPATIBILITY_ONLY | package exports | 0 | 39 |
| `app.ui.business_workflow.backup_center_dialog` | PRODUCTION_DIALOG | `WorkflowBackupCenterDialog` | 2 | 522 |
| `app.ui.business_workflow.backup_settings_dialog` | PRODUCTION_DIALOG | `WorkflowBackupSettingsDialog` | 1 | 248 |
| `app.ui.business_workflow.database_recovery_dialog` | PRODUCTION_DIALOG | `WorkflowDatabaseRecoveryDialog` | 2 | 292 |
| `app.ui.business_workflow.dialogs` | PRODUCTION_DIALOG | `BusinessRecordDialog` | 1 | 345 |
| `app.ui.business_workflow.import_dialog` | PRODUCTION_DIALOG | `WorkflowImportPreviewDialog` | 1 | 253 |
| `app.ui.business_workflow.model` | UI_MODEL | `WorkflowTableModel`, proxy, delegate | 3 | 627 |
| `app.ui.business_workflow.system_health_badge` | PRESENTATION_COMPONENT | `SystemHealthBadge` | 1 | 154 |
| `app.ui.business_workflow.system_health_dialog` | PRODUCTION_DIALOG | `SystemHealthCenterDialog` | 3 | 572 |
| `app.ui.commercial_estimator_dialog` | PRODUCTION_DIALOG | `CommercialEstimatorDialog` | 1 | 273 |
| `app.ui.company_capability_dialog` | PRODUCTION_DIALOG | `CompanyCapabilityDialog` | 2 | 285 |
| `app.ui.controllers.__init__` | COMPATIBILITY_ONLY | controller exports | 0 | 19 |
| `app.ui.controllers.dashboard_controller` | CONTROLLER | `DashboardController`, refresh worker | 3 | 803 |
| `app.ui.crash_report_center_dialog` | PRODUCTION_DIALOG | `CrashReportCenterDialog` | 1 | 634 |
| `app.ui.crash_report_dialog` | PRODUCTION_DIALOG | `CrashReportDialog`, `QtCrashBridge` | 1 | 348 |
| `app.ui.dashboard.__init__` | COMPATIBILITY_ONLY | dashboard exports | 0 | 93 |
| `app.ui.dashboard.activity_feed` | PRESENTATION_COMPONENT | `ActivityFeed` | 1 | 413 |
| `app.ui.dashboard.ai_advisor` | PRESENTATION_COMPONENT | `AiAdvisor` | 1 | 592 |
| `app.ui.dashboard.data_state` | PRESENTATION_COMPONENT | `DataStatePanel` | 1 | 348 |
| `app.ui.dashboard.demo_data` | PRESENTATION_COMPONENT | `DashboardDemoSnapshot` | 1 | 332 |
| `app.ui.dashboard.keyboard_navigation` | PRESENTATION_COMPONENT | `DashboardShortcutManager` | 1 | 130 |
| `app.ui.dashboard.kpi_center` | PRESENTATION_COMPONENT | `KpiCenter` | 2 | 247 |
| `app.ui.dashboard.quick_actions` | PRESENTATION_COMPONENT | `QuickActions` | 3 | 493 |
| `app.ui.dashboard.responsive` | PRESENTATION_COMPONENT | `DashboardLayoutSpec` | 1 | 110 |
| `app.ui.dashboard.section` | PRESENTATION_COMPONENT | `DashboardSection` | 0 | 135 |
| `app.ui.dashboard.status_banner` | PRESENTATION_COMPONENT | `DashboardStatusBanner` | 1 | 249 |
| `app.ui.dashboard.tender_feed` | PRESENTATION_COMPONENT | `TenderFeed`, model, delegate | 3 | 529 |
| `app.ui.main_window` | EMBEDDED_LEGACY | `TenderWorkspacePage`, `MainWindow` | 4 | 1,266 |
| `app.ui.matching_catalog_dialog` | PRODUCTION_DIALOG | `MatchingCatalogDialog` | 1 | 258 |
| `app.ui.modern_main_window` | PRODUCTION_ROOT | `ModernMainWindow` | 4 | 283 |
| `app.ui.pages.__init__` | COMPATIBILITY_ONLY | page exports | 0 | 5 |
| `app.ui.pages.business_workflow_page` | PRODUCTION_PAGE | `BusinessWorkflowPage` | 10 | 2,227 |
| `app.ui.pages.dashboard_page` | PRODUCTION_PAGE | `DashboardPage` | 1 | 938 |
| `app.ui.pages.tender_workspace_page` | COMPATIBILITY_ONLY | re-export of legacy owner | 2 | 5 |
| `app.ui.provider_credentials_dialog` | PRODUCTION_DIALOG | `ProviderCredentialsDialog` | 1 | 163 |
| `app.ui.safe_mode_dialog` | PRODUCTION_DIALOG | `SafeModeDialog` | 1 | 347 |
| `app.ui.tender_collector_dialog` | PRODUCTION_DIALOG | `TenderCollectorDialog` | 2 | 701 |
| `app.ui.tender_collector_notifications_dialog` | PRODUCTION_DIALOG | notifications dialog | 0 | 153 |
| `app.ui.tender_collector_schedule_dialog` | PRODUCTION_DIALOG | schedule dialog | 1 | 455 |
| `app.ui.tender_collector_scheduler_controller` | CONTROLLER | scheduler UI controller | 2 | 424 |
| `app.ui.tender_documents_dialog` | PRODUCTION_DIALOG | `TenderDocumentsDialog` | 3 | 511 |
| `app.ui.tender_full_analysis_dialog` | PRODUCTION_DIALOG | full analysis dialog | 1 | 930 |
| `app.ui.tender_participation_score_dialog` | PRODUCTION_DIALOG | score dialog | 1 | 353 |
| `app.ui.tender_provider_manager_dialog` | PRODUCTION_DIALOG | provider manager and four nested dialogs | 6 | 1,375 |
| `app.ui.tender_registry_dialog` | PRODUCTION_DIALOG | `TenderRegistryDialog` | 5 | 1,029 |
| `app.ui.tender_requirement_analysis_dialog` | PRODUCTION_DIALOG | requirements dialog | 1 | 726 |
| `app.ui.tender_search_profile_editor` | PRESENTATION_COMPONENT | `TenderSearchProfileEditor` | 2 | 579 |
| `app.ui.tender_search_profiles_dialog` | PRODUCTION_DIALOG | profiles panel/dialog | 3 | 730 |
| `app.ui.tender_search_results_dialog` | PRODUCTION_DIALOG | search results dialog | 2 | 499 |
| `app.ui.tender_search_ui_controller` | CONTROLLER | `TenderSearchUiController`, worker set | 17 | 2,821 |
| `app.ui.tender_unified_search_panel` | PRESENTATION_COMPONENT | unified search panel | 2 | 398 |
| `app.ui.tender_verification_dialog` | PRODUCTION_DIALOG | verification dialog | 1 | 538 |
| `app.ui.theme.__init__` | COMPATIBILITY_ONLY | theme exports | 0 | 19 |
| `app.ui.theme.colors` | THEME_RESOURCE | palettes and semantic roles | 2 | 313 |
| `app.ui.theme.stylesheet` | THEME_RESOURCE | global stylesheet builder | 0 | 92 |
| `app.ui.theme.typography` | THEME_RESOURCE | font tokens | 0 | 59 |
| `app.ui.viewmodels.__init__` | COMPATIBILITY_ONLY | view-model exports | 0 | 29 |
| `app.ui.viewmodels.ai_advisor_viewmodel` | VIEWMODEL | `AiAdvisorViewModel` | 1 | 132 |
| `app.ui.viewmodels.dashboard_viewmodel` | VIEWMODEL | `DashboardViewModel`, DTOs | 5 | 202 |
| `app.ui.widgets.__init__` | COMPATIBILITY_ONLY | widget exports | 0 | 29 |
| `app.ui.widgets.button` | PRESENTATION_COMPONENT | Corteris button family | 0 | 333 |
| `app.ui.widgets.card` | PRESENTATION_COMPONENT | `Card`, `KpiCard` | 0 | 443 |
| `app.ui.widgets.dashboard_layout` | PRESENTATION_COMPONENT | `DashboardLayout` | 0 | 72 |
| `app.ui.widgets.sidebar` | PRESENTATION_COMPONENT | `Sidebar` | 0 | 80 |
| `app.ui.widgets.topbar` | PRESENTATION_COMPONENT | `TopBar` | 1 | 64 |

No module is classified `DEAD_CANDIDATE`: the audit found production, import, or test consumers,
or a package compatibility purpose for every module. The five widgets produced by
`ModernMainWindow._placeholder()` are runtime `PLACEHOLDER` components: `ai`, `documents`,
`clients`, `analytics`, and `settings`.

## Runtime route and action inventory

The isolated offscreen composition created one `QMainWindow`, nine sidebar routes and no socket
connection. Active sidebar pages are Dashboard, Tenders, two views of Business Workflow, plus the
five placeholders above. The top bar owns global search, theme, AI route, notifications, and
profile. Notifications and profile terminate in informational message boxes.

The embedded tender workspace exposes eight tabs: Panel, Analysis, Estimate, Equipment/brands,
Readiness, Tools 1.4, Price Monitoring 1.5, and Settings. Its settings surface has six nested tabs.
The installed controller owns nine major actions: profiles (`Ctrl+Shift+F`), registry
(`Ctrl+Shift+R`), sources (`Ctrl+Shift+S`), collector (`Ctrl+Shift+C`), company capability,
matching catalogue, discovery, schedule (`Ctrl+Shift+P`), and notifications (`Ctrl+Shift+N`).
Tender IDs can be opened from Dashboard and Business Workflow into the tender workspace.

## Theme and resource inventory

`ThemePalette` supplies dark/light semantic colors and chart color slots. `Typography` supplies
font tokens. `build_stylesheet()` covers application background, buttons, editable controls,
line-edit/text focus, table views, scrollbars, and status bar. Reusable buttons, cards, dashboard
sections, feeds, badges, and dialogs also apply local styles. There are 45 local stylesheet calls;
three usages of two literal colors occur in `app.ui.main_window` database-status markup. There is
no icon asset pipeline: sidebar/top-bar affordances use Unicode/emoji or text.

## Test inventory

The 97 modules selected by exact source use of `app.ui` or `PySide6` produced `302 passed,
2 warnings` in 81.39 s. Exact membership is reproducible with
`rg -l 'app\.ui|PySide6' tests -g '*.py'`. Coverage groups are:

- Dashboard/view-model/controller/components: 20 modules.
- Business workflow, backup, health, crash, and import: 25 modules.
- Tender search, registry, analysis, provider, collector, and documents: 34 modules.
- RM-127–RM-140 composition/compatibility contracts: 18 modules.

The inventory spans Dashboard/view-model/controller components; Business Workflow, backup,
health, crash, and import; tender search, registry, analysis, providers, collector, and documents;
and 21 explicit RM-127–RM-140 UI composition/compatibility modules (these areas overlap).
Focused keyboard, responsive, accessibility-metadata, theme-propagation, offline-composition and
shutdown tests exist. No screenshot/golden visual test, real multi-DPI matrix, screen-reader test,
10k-widget rendering benchmark, or full-shell focus traversal contract was found.

## Reproduction limitations

- Windows 10, Python 3.12.7, PySide6 6.11.1, `QT_QPA_PLATFORM=offscreen` were used.
- 100/125/150/200% Windows scaling, multi-monitor movement, high-contrast mode, screen reader,
  IME, and touch input: `NOT_EXECUTED`; see the manual matrix in `RM-141_ACCEPTANCE.md`.
- Runtime composition isolated repositories/settings under a temporary directory and disabled
  background dashboard start. It proves composition and an offline boundary, not visual fidelity.
