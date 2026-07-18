# RM-143 implementation plan

## Scope and ordering

Close only `UI-141-003` after the audit/contract/matrix/plan commit. Preserve RM-142 navigation,
all mature tender/workflow/search/AI owners, database schema, dependencies and deterministic
decision authority. Do not start RM-144+ application work.

## Phase 1 — docs-first gate

1. Commit the four RM-143 documents as
   `docs(rm-143): audit design system boundaries`.
2. Confirm the commit contains documentation only and the worktree is otherwise clean.
3. Do not modify application code before that commit exists.

## Phase 2 — characterization and expected-red

Create a characterization commit for existing stable inputs:

- `ThemeName`, palette field shape, `ui/theme` safe fallback and one global builder;
- current public button/card classes, object names, properties, signals and `setText` behavior;
- Dashboard `DataState`/status/banner public factories and actions;
- route IDs/order/aliases/icon compatibility field and one stack/owner;
- current asset/PyInstaller/frozen paths.

Then create the RM-143 expected-red contract tests, failing only for absent new symbols/behavior:

- design tokens/version/immutability;
- palette parity, sRGB contrast and approved pairs;
- exact stylesheet/migration guard;
- semantic icon registry/resources/fallback;
- button/card state, accessibility and lifecycle;
- status/data/form primitives;
- offline component gallery and theme propagation;
- source/frozen packaging.

## Phase 3 — token and contrast root

1. Add a versioned immutable public token root under `app.ui.theme`.
2. Extend the existing `ThemePalette` only for audited missing roles; retain one dataclass.
3. Add typed spacing, sizing, radius/border, elevation, motion and limited layout groups.
4. Formalize typography fallback/scale validation without changing global font rendering blindly.
5. Add correct sRGB luminance/contrast utilities, approved pair registry and explicit thresholds.
6. Preserve thin re-exports and prevent import cycles.

## Phase 4 — semantic icons and resources

1. Add one closed `IconId` and immutable registry/provider under `app.ui.theme`.
2. Add a bounded set of original repository-owned SVG assets under the existing `assets/` root,
   plus provenance/security manifest.
3. Resolve icons through existing path/resource ownership with safe generic fallback.
4. Adapt route icon strings, Sidebar and TopBar without changing route identity/metadata ownership.
5. Keep text fallback for missing resources; require accessible names for icon-only controls.
6. Extend build/frozen tests and reject external/script SVG content.

## Phase 5 — global/component contracts

1. Expand `build_stylesheet()` using tokens for required controls and states while preserving one
   global owner and selector precedence.
2. Migrate `CorterisButton` size/state/loading/icon-only behavior to tokens.
3. Migrate `Card/KpiCard` tones/density/focus/keyboard/disabled/shadow lifecycle.
4. Extend existing Dashboard `DataState` with disabled/unavailable and migrate its panel.
5. Extract reusable status badge/banner and form field/section presentation primitives, reusing
   existing semantic owners and leaving business validation/status calculation untouched.
6. Migrate exact `MIGRATE_RM143` sites, including database-status raw colours and rich-text escaping.
7. Keep/defer the remaining local QSS exactly as documented.

## Phase 6 — guard and gallery

1. Add a deterministic source-only guard for raw colours, foundation font metrics, unregistered
   stylesheet calls, palette parity, icon/resource completeness, exact exceptions and import cycles.
2. Parse/check all 45 baseline matrix sites by file/symbol rather than line number.
3. Add a deterministic offline gallery/harness with fixed synthetic Russian/long labels and both
   themes. It must not become a production route.
4. Cover repeated construct/theme-switch/destroy without timer/effect/widget growth.

## Phase 7 — validation

Run focused RM-143 tests, then neighboring tests:

- RM-142 route and shell navigation;
- RM-127/RM-128 composition;
- existing Dashboard/component/theme tests;
- workflow health/backup/status tests;
- build/release/frozen self-test;
- representative AI/settings/search offline tests.

Run the exact workflow-equivalent local gate:

```powershell
python scripts/check_repository_secrets.py
python -m ruff check .
python -m ruff format . --check
python -m mypy
python -m pytest -q tests/test_collector_provider_control.py::test_manager_exposes_all_sources_without_network tests/test_mos_supplier_diagnostic_script.py::test_mos_diagnostic_runs_from_scripts_path_without_app_error
python -m pytest -q tests/test_database_migrations_121.py tests/test_collector_schema_contract.py
python -c "from app.ui.controllers import DashboardController; print(DashboardController.__name__)"
python -m pytest -q tests/test_bootstrap_tender_search_integration.py
python -m pytest -q tests/test_build_release_contract.py tests/test_frozen_self_test.py
python -m pytest -q
python -m pip_audit --skip-editable
git diff --check
```

Use an isolated repository-local `--basetemp` if the host temp directory is unavailable. Record
exact commands/counts/warnings/environment in `docs/RM-143_ACCEPTANCE.md`.

## Phase 8 — publication and closeout

1. Commit reviewable docs/test/feature/refactor/test/acceptance slices.
2. Push `feat/rm-143-design-system`, open feature PR
   `feat(rm-143): implement Corteris design system`, and require Windows Python 3.12/3.13 gate.
3. Merge only after the final PR-head gate succeeds.
4. Verify the exact merge SHA Quality Gate, including full pytest and dependency audit.
5. Only then create `docs/rm-143-completion`, update ROADMAP/STATUS/HISTORY/acceptance in a
   docs-only PR, mark RM-143 `DONE`, and activate RM-144.

## Stop conditions and rollback

Stop for a second theme/icon/resource/navigation owner, persisted design version/history, required
DB migration or dependency, network asset/font, unowned asset license, broad guard exception,
RM-142 route break, mature workflow/public API break, P0/P1 security/data issue, or any need to
implement RM-144+ to satisfy RM-143.

Rollback is a revert of RM-143 commits/feature merge. It requires no DB/data/settings downgrade;
`ui/theme` keeps `dark`/`light`, public re-exports and icon fallback preserve compatibility, and
RM-142 route contracts remain intact.
