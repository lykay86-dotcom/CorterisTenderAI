# RM-143 component and local stylesheet migration matrix

Matrix version: `rm143-style-matrix-v1`

Baseline: `67beb8787db5908c9e8dd52f7e17e385aed48814`

Inventory command: `rg -n --glob '*.py' 'setStyleSheet\s*\(' app/ui`

Coverage: **45 of 45** current local stylesheet calls. A decision does not imply that local QSS is
intrinsically defective; exact token-backed component styles remain valid.

Decision vocabulary: `MIGRATE_RM143`, `TOKEN_BACKED_KEEP`, `DEFER_RM144`–`DEFER_RM155`,
`LEGACY_COMPATIBILITY`, `REMOVE_DUPLICATE`.

| ID | File / symbol | Pattern | Current source / raw literals | Current tests | Decision / target | Replacement owner | Compatibility / acceptance | Risk |
|---|---|---|---|---|---|---|---|---|
| DS-143-001 | `business_workflow/import_dialog.py::WorkflowImportPreviewDialog.apply_theme` | dialog/table | palette + Typography; local radius/padding | `test_workflow_import_dialog.py` | TOKEN_BACKED_KEEP / RM-150 | dialog/table tokens | preserve import preview, object names; exact guard | P2 |
| DS-143-002 | `business_workflow/dialogs.py::BusinessRecordDialog.apply_theme` | form/dialog | palette + Typography; local radius/padding | workflow dialog/model tests | TOKEN_BACKED_KEEP / RM-148 | form/dialog tokens | validation, Decimal decision and signals unchanged | P2 |
| DS-143-003 | `business_workflow/system_health_badge.py::SystemHealthBadge.apply_theme` | status badge | semantic palette; local pill metrics | `test_system_health_badge.py` | MIGRATE_RM143 | status badge + radius/spacing tokens | severity remains domain-owned; both themes | P2 |
| DS-143-004 | `business_workflow/backup_settings_dialog.py::WorkflowBackupSettingsDialog.apply_theme` | form/dialog | palette + Typography; local radius/padding | backup settings tests | TOKEN_BACKED_KEEP / RM-151 | form/dialog tokens | settings/backup behavior unchanged | P2 |
| DS-143-005 | `business_workflow/database_recovery_dialog.py::WorkflowDatabaseRecoveryDialog.apply_theme` | danger dialog | palette + Typography; local radius/padding | recovery tests | TOKEN_BACKED_KEEP / RM-151 | dialog/status tokens | confirmations and safety backup unchanged | P1 |
| DS-143-006 | `business_workflow/system_health_dialog.py::SystemHealthCenterDialog._apply_snapshot_colors` | status value | semantic palette + Typography | system health dialog tests | MIGRATE_RM143 | status presentation helper | label remains visible; no domain derivation | P2 |
| DS-143-007 | `business_workflow/system_health_dialog.py::SystemHealthCenterDialog.apply_theme` | dialog/table | palette + Typography; local radius/padding | system health dialog/support tests | TOKEN_BACKED_KEEP / RM-151 | dialog/table tokens | health worker/lifecycle not changed | P2 |
| DS-143-008 | `business_workflow/backup_center_dialog.py::WorkflowBackupCenterDialog.apply_theme` | dialog/table | palette + Typography; local radius/padding | `test_workflow_backup_center_theme.py` and backup tests | TOKEN_BACKED_KEEP / RM-151 | dialog/table tokens | backup identities/actions unchanged | P2 |
| DS-143-009 | `crash_report_dialog.py::CrashReportDialog.apply_theme` | danger dialog | palette + Typography; local font/radius/padding | crash dialog tests | TOKEN_BACKED_KEEP / RM-151 | dialog/status tokens | safe diagnostic workflow unchanged | P1 |
| DS-143-010 | `crash_report_center_dialog.py::CrashReportCenterDialog.apply_theme` | dialog/table | palette + Typography; local font/radius/padding | crash center tests | TOKEN_BACKED_KEEP / RM-151 | dialog/table tokens | report identity/deletion confirmation unchanged | P1 |
| DS-143-011 | `safe_mode_dialog.py::SafeModeDialog.apply_theme` | warning dialog | palette + Typography; local radius/padding | safe-mode tests | TOKEN_BACKED_KEEP / RM-151 | dialog/status tokens | recovery/exit semantics unchanged | P1 |
| DS-143-012 | `modern_main_window.py::ModernMainWindow.apply_theme` | global QSS application | canonical `build_stylesheet`; no local literals | RM-127/RM-142 composition tests | TOKEN_BACKED_KEEP / RM-143 | sole global stylesheet owner | `ui/theme`, one shell/stack, route state preserved | P1 |
| DS-143-013 | `tender_provider_manager_dialog.py::TenderProviderManagerDialog.apply_theme` | dialog/table/status | palette; raw font/radius/padding | provider manager tests | TOKEN_BACKED_KEEP / RM-150 | dialog/table tokens | provider/credential/network boundaries unchanged | P1 |
| DS-143-014 | `tender_participation_score_dialog.py::TenderParticipationScoreDialog.apply_theme` | decision dialog | palette; raw display fonts/radius/padding | score dialog/RM-107 tests | DEFER_RM149 / RM-149 | tender detail hierarchy tokens | critical stop factor and score priority unchanged | P1 |
| DS-143-015 | `tender_full_analysis_dialog.py::TenderFullAnalysisDialog.apply_theme` | analysis dialog | palette; raw font/radius/padding | full-analysis tests | DEFER_RM149 / RM-149 | tender detail/dialog tokens | citations, decision and actions unchanged | P1 |
| DS-143-016 | `tender_documents_dialog.py::TenderDocumentsDialog.apply_theme` | document dialog/table | palette; raw font/radius/padding | documents tests | DEFER_RM149 / RM-149 | tender detail/table tokens | exact tender/document identity unchanged | P2 |
| DS-143-017 | `tender_search_results_dialog.py::TenderSearchResultsDialog.apply_theme` | results table/detail | palette; raw font/radius/padding | search results tests | DEFER_RM150 / RM-150 | table/detail tokens | selection, ordering and source URL actions unchanged | P1 |
| DS-143-018 | `tender_requirement_analysis_dialog.py::TenderRequirementAnalysisDialog.apply_theme` | analysis table/detail | palette; raw font/radius/padding | requirement analysis tests | DEFER_RM149 / RM-149 | detail/table tokens | evidence/verification semantics unchanged | P1 |
| DS-143-019 | `tender_search_profile_editor.py::TenderSearchProfileEditor.show_validation_error` | form validation | semantic danger colour | profile editor tests | MIGRATE_RM143 | form-field validation state | error text remains visible and owner-supplied | P2 |
| DS-143-020 | `tender_search_profile_editor.py::TenderSearchProfileEditor.show_validation_success` | form validation | semantic success colour | profile editor tests | MIGRATE_RM143 | form-field validation state | success text remains visible | P2 |
| DS-143-021 | `tender_search_profile_editor.py::TenderSearchProfileEditor.apply_theme` | form | palette + raw font/radius/padding | profile editor/RM-130 tests | TOKEN_BACKED_KEEP / RM-152 | form/dialog tokens | profile schema/Decimal/selection unchanged | P2 |
| DS-143-022 | `tender_registry_dialog.py::TenderRegistryDialog.apply_theme` | registry table/detail | palette; raw font/radius/padding | registry tests | DEFER_RM150 / RM-150 | table/detail tokens | stable tender IDs/selection/actions unchanged | P1 |
| DS-143-023 | `tender_search_profiles_dialog.py::TenderSearchProfilesPanel._set_status` | inline status | semantic success/danger | profile dialog tests | MIGRATE_RM143 | inline status primitive | status text and busy state unchanged | P2 |
| DS-143-024 | `tender_search_profiles_dialog.py::TenderSearchProfilesPanel.apply_theme` | panel/table | palette + Typography; local metrics | RM-128/RM-130 tests | TOKEN_BACKED_KEEP / RM-150 | form/table tokens | one controller/search seam unchanged | P1 |
| DS-143-025 | `tender_search_profiles_dialog.py::TenderSearchProfilesDialog.__init__` | dialog footer append | palette; local border | profile dialog tests | REMOVE_DUPLICATE / RM-143 | global dialog/button-box QSS | no concatenated QSS; close action/object unchanged | P2 |
| DS-143-026 | `tender_verification_dialog.py::TenderVerificationDialog.apply_theme` | verification table/detail | palette; raw font/radius/padding | verification tests | DEFER_RM149 / RM-149 | detail/table tokens | provenance and manual selection unchanged | P1 |
| DS-143-027 | `tender_unified_search_panel.py::TenderUnifiedSearchPanel.set_status` | inline status | semantic danger/text colour | RM-128/RM-140 tests | MIGRATE_RM143 | inline status primitive | accepted-run/cancel lifecycle unchanged | P1 |
| DS-143-028 | `tender_unified_search_panel.py::TenderUnifiedSearchPanel.apply_theme` | search panel | palette; local radius | RM-128 composition tests | TOKEN_BACKED_KEEP / RM-144 | surface/layout tokens | panel/controller/search ownership unchanged | P1 |
| DS-143-029 | `widgets/card.py::Card._apply_theme` | reusable card | palette + Typography; raw radius/font weight | no direct baseline owner | MIGRATE_RM143 | card + token contract | public properties/signals/object names; keyboard/effect tests | P1 |
| DS-143-030 | `widgets/card.py::KpiCard._apply_trend_theme` | status tag | semantic palette; raw radius/padding | no direct baseline owner | MIGRATE_RM143 | status tag + tokens | supplied KPI text only; both themes | P2 |
| DS-143-031 | `widgets/button.py::CorterisButton._apply_theme` | reusable button | palette + duplicated raw size/radius/padding | no direct baseline owner | MIGRATE_RM143 | button + token contract | public subclasses/properties/object name/loading | P1 |
| DS-143-032 | `widgets/dashboard_layout.py::DashboardLayout.add_placeholder_page` | compatibility demo label | raw `24px/600` | RM-142 layout tests | MIGRATE_RM143 | Typography H1 token | no production route or second map; helper compatibility | P2 |
| DS-143-033 | `tender_collector_notifications_dialog.py::TenderCollectorNotificationsDialog.apply_theme` | notification table | palette; raw font/radius/padding | notification tests | DEFER_RM151 / RM-151 | notification/table tokens | notification repository/actions unchanged | P1 |
| DS-143-034 | `tender_collector_dialog.py::TenderCollectorDialog.apply_theme` | progress/table | palette; raw font/radius/padding | collector/RM-140 lifecycle tests | DEFER_RM151 / RM-151 | operation/table tokens | admission/cancel/CLOSED unchanged | P1 |
| DS-143-035 | `tender_collector_schedule_dialog.py::TenderCollectorScheduleDialog.apply_theme` | schedule table/form | palette; raw font/radius/padding | scheduler tests | DEFER_RM151 / RM-151 | form/table/operation tokens | schedule identity/guard unchanged | P1 |
| DS-143-036 | `dashboard/data_state.py::DataStatePanel.apply_theme` | reusable data state | palette + Typography; raw radius/padding | `test_dashboard_data_states.py` | MIGRATE_RM143 | canonical data-state primitive | extend taxonomy; preserve factories/actions/object names | P1 |
| DS-143-037 | `dashboard/ai_advisor.py::AiAdvisor.apply_theme` | Dashboard decision panel | palette + Typography; local metrics | advisor tests | DEFER_RM145 / RM-145 | Dashboard jobs/KPI tokens | widget never owns approved decision | P1 |
| DS-143-038 | `dashboard/activity_feed.py::ActivityFeedItem.apply_theme` | activity item | palette + Typography; local metrics | activity feed tests | DEFER_RM145 / RM-145 | Dashboard/card tokens | keyboard/action identity preserved | P2 |
| DS-143-039 | `dashboard/activity_feed.py::ActivityFeed.apply_theme` | activity empty state | palette + Typography; local metrics | activity feed tests | DEFER_RM145 / RM-145 | Dashboard/data-state tokens | deterministic ordering/actions preserved | P2 |
| DS-143-040 | `dashboard/section.py::DashboardSection.apply_theme` | Dashboard section | palette + Typography; local metrics | Dashboard tests | DEFER_RM145 / RM-145 | Dashboard/card tokens | section object names/layout remain | P2 |
| DS-143-041 | `dashboard/quick_actions.py::QuickActionTile.apply_theme` | action card | palette + Typography; local metrics | quick-action/keyboard tests | DEFER_RM145 / RM-145 | Dashboard/card/button tokens | route signals and keyboard activation preserved | P1 |
| DS-143-042 | `dashboard/tender_feed.py::TenderFeed.apply_theme` | Dashboard table | palette + Typography; local metrics | tender-feed tests | DEFER_RM150 / RM-150 | table tokens | stable tender ID/selection/Enter unchanged | P1 |
| DS-143-043 | `dashboard/status_banner.py::DashboardStatusBanner.apply_theme` | reusable banner | semantic palette + Typography; local metrics | `test_dashboard_status_banner.py` | MIGRATE_RM143 | status banner + tokens | timer/action/object names; both themes | P1 |
| DS-143-044 | `pages/dashboard_page.py::DashboardPage._apply_page_theme` | Dashboard page | palette + Typography; local padding | Dashboard page tests | DEFER_RM145 / RM-145 | Dashboard layout tokens | responsive breakpoints and signals unchanged | P1 |
| DS-143-045 | `pages/business_workflow_page.py::BusinessWorkflowPage.apply_theme` | workflow page/table/form | palette + Typography; local metrics | workflow page/model/backup/health tests | TOKEN_BACKED_KEEP / RM-150 | surface/form/table tokens | repository, filters, selection, lifecycle unchanged | P1 |

## Non-`setStyleSheet` migration entries

| ID | Site | Decision | Acceptance |
|---|---|---|---|
| DS-143-X01 | `main_window.py::TenderWorkspacePage._update_db_status` raw `#2e8b57/#b22222` rich text | MIGRATE_RM143 | semantic palette/escaped text; no raw colour outside theme |
| DS-143-X02 | `navigation/registry.py` route emoji strings | MIGRATE_RM143 | same route IDs/order/aliases; semantic icon IDs resolve/fallback |
| DS-143-X03 | `widgets/topbar.py` and `modern_main_window.py` glyph buttons/theme glyph | MIGRATE_RM143 | semantic icons; exact object names/signals/tooltips/accessibility |
| DS-143-X04 | existing `assets/` / frozen spec | MIGRATE_RM143 | owned SVG manifest, safe fallback, build/frozen tests |

## Exception policy

Every `TOKEN_BACKED_KEEP`, `DEFER_*`, or `LEGACY_COMPATIBILITY` entry is an exact exception keyed
by file and symbol. It permits the registered local call, not raw hex colours or arbitrary new
font/style literals. Adding/moving a call requires a new stable matrix entry, owner, reason, target
RM and test. `app/ui/**` or other directory-wide exceptions are invalid.
