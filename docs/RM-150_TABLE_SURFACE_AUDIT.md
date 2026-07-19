# RM-150 table surface audit

Baseline: `c7b9c2210dbcbb5db7b9b24fc81f0809d05f8d6b`  
Finding: `UI-141-011`  
Branch: `feat/rm-150-table-contract`

## Entry gate

- RM-149 feature PR #106 merged as `219e7c43527ca230a61de8cdeb3f191288fc3f87`.
- Exact feature merge-SHA Quality Gate run `29704404132` succeeded on Python 3.12 and 3.13;
  both jobs reported `2245 passed`.
- RM-149 docs-only PR #107 merged as `c7b9c2210dbcbb5db7b9b24fc81f0809d05f8d6b`.
- Final `main` Quality Gate run `29705262213` succeeded on both supported Python versions.
- Canonical state is RM-149 `DONE`, RM-150 sole `IN PROGRESS`, RM-151–RM-200 `PLANNED`.
- The root checkout's unrelated untracked `.agents/` and `skills-lock.json` are not touched; RM-150
  uses `.worktrees/rm150`.

## Reproducible inventory

`python -m scripts.audit_ui_inventory --format summary` reports 88 UI modules, 34,900 lines,
139 UI test modules, 32 `QTableWidget` calls and 3 `QTableView` calls. The audit also reports
57 accessible-name calls and 26 accessible-description calls across the whole UI; those aggregate
counts are not evidence that any individual table has an honest accessible contract.

The RM-141 baseline contains 30 `QTableWidget` and 2 `QTableView` constructions. Every original
construction is traced: the nine legacy `main_window.py` widgets moved one-for-one to
`TenderWorkspacePage`, while the other 23 retained their logical owners. The three additions are:

| Addition | Roadmap owner | Reason |
|---|---|---|
| `app/ui/charts/widget.py:ChartWidget.table` | RM-146 | accessible chart-table projection |
| `TenderAnalyticsPage.financial_table` | RM-148 | exact Decimal financial snapshot |
| `TenderAnalyticsPage.text_table` | RM-147 | immutable text/source contributor snapshot |

No construction is omitted from the following current inventory. `WorkflowTableModel`,
`WorkflowFilterProxyModel`, `WorkflowStatusDelegate`, `TenderFeedModel` and `ChartTableModel` are
separate model/delegate owners, not additional table constructions.

## Current construction-site matrix

`MIGRATE` means a representative RM-150 conversion. `KEEP` means the current bounded/static widget
is explicitly retained. `DEFER` means a non-representative migration is prohibited in RM-150 and is
left with its current owner.

| ID | Construction site | Identity / behavior observed | Decision and reason |
|---|---|---|---|
| TBL-150-001 | `AggregatorDiscoveryDialog.table` | transient discovery row; action reads `currentRow()` | KEEP — small transient picker |
| TBL-150-002 | `CommercialEstimatorDialog.table` | fixed cost categories; editable Decimal inputs | KEEP — fixed form grid, RM-148 conversions remain owner |
| TBL-150-003 | `WorkflowBackupCenterDialog.table` | backup entry; restore/delete selected row | MIGRATE — destructive revalidation branch |
| TBL-150-004 | `CrashReportCenterDialog.table` | report path/index; delete selected row | DEFER — separate filesystem/catalog lifecycle |
| TBL-150-005 | `WorkflowImportPreviewDialog.table` | immutable bounded import preview | KEEP — preview only, no row action |
| TBL-150-006 | `SystemHealthCenterDialog.table` | diagnostic journal; separate text export | DEFER — journal owner and export format remain unchanged |
| TBL-150-007 | `ChartWidget.table` | immutable series/point IDs and `ChartSpec` | MIGRATE — analytics snapshot/export branch |
| TBL-150-008 | `TenderProviderManagerDialog.table` | provider ID in `UserRole`; row actions and health state | MIGRATE — provider partial/error branch |
| TBL-150-009 | `TenderDocumentsDialog.table` | document identity in `UserRole`; selected document action | DEFER — download/view worker lifecycle is out of scope |
| TBL-150-010 | `TenderFeed.table` | legacy tender ID model role; Enter/open action | MIGRATE — dashboard/tender branch |
| TBL-150-011 | `TenderCollectorScheduleDialog.sources` | provider ID in `UserRole`; schedule editor | KEEP — bounded settings grid |
| TBL-150-012 | `TenderParticipationScoreDialog.components_table` | fixed score component projection | KEEP — deterministic RM-107 score/decision owner |
| TBL-150-013 | `MatchingCatalogDialog.table` | entry ID in `UserRole`; editable rows | DEFER — catalog persistence protocol needs separate package |
| TBL-150-014 | `BusinessWorkflowPage.table` | typed record IDs; model/proxy/delegate; archive/export | MIGRATE — workflow, RM-148 Decimal and filter branch |
| TBL-150-015 | `TenderCollectorNotificationsDialog.table` | bounded notification history | KEEP — read-only diagnostic list |
| TBL-150-016 | `TenderCollectorDialog.provider_table` | provider ID in `UserRole`; enable selection | KEEP — settings owner; manager table is representative |
| TBL-150-017 | `TenderFullAnalysisDialog.stages` | fixed analysis-stage projection | KEEP — worker episode status, no record selection |
| TBL-150-018 | `TenderRequirementAnalysisDialog.findings_table` | finding object in `UserRole`; first-row fallback | DEFER — finding/evidence workflow remains exact owner |
| TBL-150-019 | `TenderRequirementAnalysisDialog.documents_table` | document evidence projection | DEFER — paired requirement-analysis lifecycle |
| TBL-150-020 | `TenderRegistryDialog.table` | exact registry key; archive/restore and detail actions | MIGRATE — canonical tender + destructive archive branch |
| TBL-150-021 | `TenderRegistryDialog.history_table` | occurrence history for selected registry key | DEFER — child projection follows registry owner later |
| TBL-150-022 | `TenderAnalyticsPage.financial_table` | immutable exact Decimal snapshot | MIGRATE — financial parity branch |
| TBL-150-023 | `TenderAnalyticsPage.text_table` | contributor/source identity in `UserRole`; snapshot export | MIGRATE — analytics/source/export branch |
| TBL-150-024 | `TenderSearchResultsDialog.table` | persisted registry identity but row-index selection | MIGRATE — RM-149 tender identity branch |
| TBL-150-025 | `TenderWorkspacePage.table` | legacy ORM tender ID in first column | DEFER — typed legacy compatibility surface |
| TBL-150-026 | `TenderWorkspacePage.estimate_table` | editable estimate rows; removal by row index | MIGRATE — editable identity branch |
| TBL-150-027 | `TenderWorkspacePage.catalog_table` | editable catalog rows; removal by row index | MIGRATE — editable identity branch |
| TBL-150-028 | `TenderWorkspacePage.readiness_table` | small derived readiness projection | KEEP — bounded read-only result |
| TBL-150-029 | `TenderWorkspacePage.pm_table` | price-monitor rows and row-index operations | DEFER — monitoring owner and persistence are out of scope |
| TBL-150-030 | `TenderWorkspacePage.platform_table` | platform settings; test/remove by row | DEFER — network/settings actions are out of scope |
| TBL-150-031 | `TenderWorkspacePage.template_table` | fixed `TEMPLATE_NAMES` form grid | KEEP — static bounded form |
| TBL-150-032 | `TenderWorkspacePage.db_diagnostics_table` | two-column diagnostics | KEEP — bounded read-only diagnostics |
| TBL-150-033 | `TenderVerificationDialog.fields_table` | field name in `UserRole`; first-row fallback | DEFER — verification resolution owner remains RM-149 action target |
| TBL-150-034 | `TenderVerificationDialog.candidates_table` | candidate ID in `UserRole`; first-row fallback | DEFER — paired verification transaction |
| TBL-150-035 | `TenderVerificationDialog.history_table` | resolution audit history | KEEP — read-only bounded history |

Totals: 11 `MIGRATE`, 12 `KEEP`, 12 `DEFER`; 35/35 constructions classified.

## Cross-cutting findings

- `QTableWidget.currentRow()` and row-position coupling are still common action identities.
- Several refresh paths select row zero or a neighboring row when the previous entity disappears.
- The workflow model/proxy is the strongest existing general implementation, but reset/filter behavior
  and roles do not yet meet the shared identity/update contract.
- Registry, Dashboard and analytics already carry stable domain IDs; RM-150 must preserve them rather
  than invent a generic integer identity.
- Empty, loading, error and partial conditions are inconsistently represented; fake table rows would
  collide with sorting, selection and export semantics.
- Exports are owned by several existing adapters. A table layer must project the same immutable
  snapshot and must not become a second business/export owner.
- RM-107 score, recommendation and critical stop-factor priority are read-only inputs. Sorting,
  filtering or rendering can never recompute or override them.

## Accepted boundary

RM-150 introduces a Qt-free immutable table contract and bounded Qt adapters, then migrates only the
11 representative sites. Existing repositories, controllers, workers, exporters, route owners,
Decimal conversions and tender-detail identities remain authoritative. There is no DB/schema change,
dependency, network path, AI path, scoring policy or second router/repository stack.
