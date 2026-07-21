# RM-155 settings, action and route matrix

| Kind | Exact ID/value | Owner | Consumer/risk | Decision |
|---|---|---|---|---|
| setting | `ui/theme=dark|light` | `ModernMainWindow` | persisted user preference; corrupt value safely falls back | KEEP |
| geometry/state | no redesign-specific persisted key found | Qt/shell | no migration target exists | KEEP absence; no migration |
| last route/history | in-memory `NavigationHistory`, max 32 | `DashboardLayout` | no persisted legacy route rewrite | KEEP |
| workflow state | typed search/kind/status/archive/record ID context | workflow page/navigation | exact selection or none | KEEP |
| route aliases | `dashboard,tenders,quotes,estimates,ai,settings,documents,analytics,clients` | registry | stable admission/object names/RM-156 plan | KEEP |
| canonical route IDs | all `RouteId` values | registry | typed deep links, KPI/analytics drill-down | KEEP |
| actions | nine tender controller QAction owners | `TenderSearchUiController`/scheduler | menus, toolbar, safe enabled state | KEEP |
| shortcuts | `Ctrl+Shift+F/R/S/C/P/N` and accepted neighbors | QAction owners | no conflict or hidden workflow found | KEEP |
| quick actions | `find_tenders`, `analyze_documents`, `create_proposal`, `create_estimate` | Dashboard DTO/page | typed route emission; no string bypass | KEEP |
| object names | shell/sidebar/topbar/tender tabs/settings/actions/status/table/dialog names | widget owner | QSS, tests, UIA, RM-154 fixtures | KEEP |
| provider/profile settings | accepted non-secret repositories/schema versions | existing owners | persisted data and credential separation | KEEP |

No UI/settings migration is required. Cleanup removes Python attributes/modules only. It does not
rename any route, action, shortcut, setting, object name, persisted enum, schema version or data
field. Unknown/corrupt values retain their existing fail-safe behavior; secrets remain in the
keyring boundary.
