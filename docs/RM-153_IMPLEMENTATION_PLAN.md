# RM-153 implementation plan

Baseline: `1c227c323c0e9912f9a8f44dc859703e2d3fcd36`  
Branch: `feat/rm-153-ui-performance`

## Ordered delivery

1. Commit the prepared design TZ, owner audit, measured baseline, performance/resource contract,
   benchmark and this plan before production changes.
2. Add characterization tests for baseline schema, deterministic fixtures, memory-only settings,
   one canonical shell/page stack, close ordering and current theme propagation.
3. Add expected-red tests for idempotent application, active-page-only local propagation, theme
   epochs and synchronous stale-page activation; record exact intentional failures.
4. Implement the smallest shell-owned theme-epoch change. Do not alter page construction,
   controller ownership, business services, persistence, navigation contracts or shutdown owners.
5. Run focused and neighboring regression contours, then reproduce the full post benchmark on the
   same host. Keep the change only if both profiled p95 targets and every guard/resource budget pass.
6. Run the full local Quality Gate, frozen/build contour and manual Windows shell sweep; record exact
   commands, versions, counts, results, limitations and SHAs in `RM-153_ACCEPTANCE.md`.
7. Merge the feature PR, verify the exact merge-SHA Windows Python 3.12/3.13 gate, then use a
   separate docs-only closeout to update canonical status before RM-154 starts.

## Validation derived from repository truth

`pyproject.toml` and `.github/workflows/quality-gate.yml` require:

```text
python scripts/check_repository_secrets.py
python -m ruff check .
python -m ruff format . --check
python -m mypy
python -m pytest -q <focused RM-153 contour>
python -m pytest -q <neighboring RM-141/RM-142/RM-144/RM-146/RM-150/RM-152 contour>
python -m pytest -q
python -m pytest -q tests/test_collector_provider_control.py::test_manager_exposes_all_sources_without_network tests/test_mos_supplier_diagnostic_script.py::test_mos_diagnostic_runs_from_scripts_path_without_app_error
python -m pytest -q tests/test_database_migrations_121.py tests/test_collector_schema_contract.py
python -c "from app.ui.controllers import DashboardController; print(DashboardController.__name__)"
python -m pytest -q tests/test_bootstrap_tender_search_integration.py
python -m pytest -q tests/test_build_release_contract.py tests/test_frozen_self_test.py
python -m pip_audit --skip-editable
```

The deterministic baseline/post benchmark and resource-cycle check are additional RM-153 gates.
Native Windows first-paint/theme/focus/close behavior is recorded separately from headless evidence.

## Migration, privacy and rollback decisions

There is no database or settings-schema migration. Existing `ui/theme` values stay compatible.
The benchmark uses synthetic labels, temporary data and memory-only settings; no secret, personal
data, absolute production path, network response or telemetry is collected. The only migration is
internal page-theme bookkeeping inside the existing shell. Rollback is a revert with no persisted
data action.
