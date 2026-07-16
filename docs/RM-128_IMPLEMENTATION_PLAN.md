# RM-128 — план реализации единой панели поиска

Baseline: `a14b2eb5d4df4ecd41a2b1bdca441e94b4cfa5e1`. План основан на
`docs/RM-128_AUDIT.md` и решениях D-02/D-06 из `docs/RM-126_REQUIREMENTS.md`.

## 1. Изменяемый контур

Обязательные production files:

- `app/tenders/unified_search.py` — pure immutable request resolution/validation;
- `app/ui/tender_unified_search_panel.py` — reusable presentation-only QWidget;
- `app/ui/main_window.py` — один panel host и narrow delegation API;
- `app/ui/modern_main_window.py` — topbar → tender page seam;
- `app/ui/widgets/topbar.py` — честный tender-search placeholder/tooltip;
- `app/ui/tender_search_ui_controller.py` — panel ownership, shared Collector worker seam и state fanout.

`app/bootstrap.py` изменяется только если existing `install_on_tender_workspace()` нельзя расширить
без второго composition seam; текущий аудит показывает, что изменение bootstrap не требуется.

Tests:

- `tests/test_rm128_unified_search_contract.py`;
- `tests/test_rm128_unified_search_panel.py`;
- `tests/test_rm128_unified_search_composition.py`;
- scoped additions to `tests/test_tender_search_ui_controller.py` и при доказанном gap
  `tests/test_bootstrap_tender_search_integration.py`.

Docs: этот audit/plan и feature evidence в `docs/ROADMAP.md`; `STATUS.md` и history изменяются только
после feature merge и successful exact-SHA post-merge gate.

## 2. Implementation order

1. Docs-only audit/plan commit.
2. Red characterization tests: one panel host, idempotent install, topbar no longer mutates
   `catalog_query`, unified path requests Collector, legacy `run_profile()` remains sync, composition
   performs no network.
3. Pure request boundary with deterministic profile/provider resolution and Decimal/date preservation.
4. Presentation-only panel with stable object names, snapshots, typed signals and honest states.
5. Controller integration with one panel and one `_CollectorRunWorker` construction seam.
6. Page/topbar composition through narrow API; retain independent equipment search.
7. Neighboring action/dialog/cancel/partial/failure/idempotency/no-network regressions.
8. Full local quality gate and exact evidence in roadmap/audit.
9. Feature PR; merge; exact merge-SHA Windows Python 3.12/3.13 post-merge gate; separate docs-only
   closeout; only then RM-128 `DONE` and RM-129 `IN PROGRESS`.

## 3. Pure request contract

Add frozen/slotted `UnifiedTenderSearchRequest`, `ResolvedUnifiedTenderSearch` and a bounded typed
validation exception. Resolution receives current snapshots from controller and:

- trim/casefolds profile ID;
- requires an existing enabled profile;
- normalizes query whitespace;
- calls `profile.to_search_query()` exactly once;
- for nonblank text replaces only `keywords` with one normalized item;
- preserves exclusions, regions, laws, dates, `Decimal` bounds, currency, page/page size;
- trim/casefolds/deduplicates provider IDs first-seen;
- rejects empty, unknown, disabled or stale IDs without fallback;
- never saves/mutates profile or performs I/O.

Tests use fixed `today` where date equality matters. Profile-specific legacy `TenderFilterOptions` are
not copied into a new Collector pipeline; existing Collector ranking/stop semantics remain unchanged.

## 4. Panel contract

`TenderUnifiedSearchPanel` receives profile/provider snapshots and theme only. Required stable names:
`TenderUnifiedSearchPanel`, `UnifiedTenderSearchProfileCombo`, `UnifiedTenderSearchQuery`,
`UnifiedTenderSearchProviders`, `UnifiedTenderSearchStartButton`, `UnifiedTenderSearchStopButton`,
`UnifiedTenderSearchProfilesButton`, `UnifiedTenderSearchSourcesButton`,
`UnifiedTenderSearchRegistryButton`, `UnifiedTenderSearchProgress`, `UnifiedTenderSearchStatus`.

Provider selection uses checkable items backed by provider IDs. Defaults are ordered
`profile.provider_ids ∩ enabled snapshot`; empty intersection stays empty. Disabled sources are visible
but not selectable. Refresh preserves only still-valid selection. Start emits one immutable request;
stop/profiles/sources/registry emit narrow signals. Busy/progress/result/error methods are UI-only and
must distinguish completed, partial, cancelled and failed states.

## 5. Controller and composition contract

- `install_on_tender_workspace()` retains canonical QAction binding, creates panel at most once,
  connects signals once and installs the same object idempotently.
- Controller loads fresh enabled profiles/provider states for panel refresh and again for unified
  request validation.
- Profile saved/deleted and provider state changes refresh panel snapshots without network.
- `_try_start_collector_query(profile_id, profile_name, query, provider_ids)` is the only worker
  construction/wiring/start seam.
- Legacy `try_start_collector()` resolves its saved profile then delegates; scheduler and Collector
  dialog keep behavior/identity. Unified path uses the pure resolver then delegates.
- Progress, stop, result, failure and invalid-result cleanup update panel and optional Collector dialog
  while retaining one `_collector_worker` and one cancellation token.
- Page mounts one panel before tabs and delegates submit/focus. Missing binding is neutral `False`.
- Modern topbar selects `tenders`, calls `submit_unified_search_text()` and never accesses controller,
  repository/provider/session or `catalog_query`.

## 6. Test and commit sequence

1. `docs(rm-128): audit unified search entry contracts`.
2. `test(rm-128): define unified tender search contract`.
3. `feat(rm-128): add unified search request boundary`.
4. `feat(rm-128): add unified tender search panel`.
5. `feat(rm-128): route unified search through collector facade`.
6. `feat(rm-128): connect topbar to unified tender search`.
7. `test(rm-128): cover unified search and compatibility paths`.
8. `docs(rm-128): record unified search acceptance evidence`.

Commits may combine inseparable test/implementation edits only when the red state and reason remain
recorded; docs-only audit commit is never combined with application changes.

## 7. Verification

Focused:

```powershell
python -m pytest -q tests/test_rm128_unified_search_contract.py `
  tests/test_rm128_unified_search_panel.py tests/test_rm128_unified_search_composition.py `
  tests/test_tender_search_ui_controller.py tests/test_bootstrap_tender_search_integration.py
```

Neighbor contour:

```powershell
python -m pytest -q tests/test_rm127_tender_workspace_contract.py `
  tests/test_rm127_modern_main_window_composition.py tests/test_tender_search_profiles_dialog.py `
  tests/test_tender_collector_dialog.py tests/test_collector_provider_control.py `
  tests/test_tender_search_results_dialog.py tests/test_tender_registry_dialog.py `
  tests/test_tender_full_analysis_dialog.py
```

Full workflow-equivalent gate follows `.github/workflows/quality-gate.yml`: secret scan, Ruff check,
Ruff format check, mypy, offline credential smoke, migration/schema smoke, public import smoke,
bootstrap composition smoke, build/release smoke, full pytest, pip-audit, `git diff --check` and clean
status. Pytest uses repository-local gitignored `--basetemp` if Windows Temp is unavailable.

## 8. Rollback and stop rule

Rollback is scoped revert of pure/UI/controller/topbar commits. DB/profile/provider settings schemas,
credentials and canonical record identity do not migrate. Legacy profile/Collector dialogs remain
available. Any stop condition from `docs/RM-128_AUDIT.md` halts production edits and requires an
evidence/plan update without expanding RM-128.
