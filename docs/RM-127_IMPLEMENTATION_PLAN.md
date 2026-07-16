# RM-127 — план реализации TenderWorkspacePage

Baseline: `f34c66b7adf2c175c5a48f17db4f12e154745813`. План основан на
`docs/RM-127_AUDIT.md` и решении D-01 из `docs/RM-126_REQUIREMENTS.md`.

## 1. Изменяемые файлы

Обязательный контур:

- `app/ui/pages/tender_workspace_page.py` — public page boundary;
- `app/ui/main_window.py` — выделение QWidget-owner и thin legacy wrapper;
- `app/ui/modern_main_window.py` — direct page composition и narrow API;
- `app/ui/tender_search_ui_controller.py` — idempotent binding existing actions;
- `app/bootstrap.py` — единственный post-controller binding seam;
- `tests/test_rm127_tender_workspace_contract.py` — tabs/page API/wrapper contract;
- `tests/test_rm127_modern_main_window_composition.py` — modern composition/navigation/actions;
- `tests/test_bootstrap_tender_search_integration.py` — bootstrap seam contract;
- `docs/RM-127_AUDIT.md`, `docs/RM-127_IMPLEMENTATION_PLAN.md`, `docs/ROADMAP.md` — evidence.

Дополнительные production files допускаются только при доказанном caller/test gap. DB migrations,
provider/search/Collector/decision/AI files не изменяются.

## 2. Migration path ownership

1. Characterization tests фиксируют current labels/order, direct legacy composition и action identity.
2. Существующий `MainWindow` widget/callback owner преобразуется в
   `TenderWorkspacePage(QWidget)` без переписывания callback bodies.
3. Page получает stable section maps и `objectName`, status-bar sink и narrow compatibility API.
4. `MainWindow(QMainWindow)` становится thin wrapper: создаёт ровно одну page, делает её
   `centralWidget`, не строит tabs повторно и делегирует legacy attributes.
5. `app.ui.pages.tender_workspace_page` публикует canonical page import.
6. `ModernMainWindow` создаёт page напрямую, регистрирует её как `tenders` и удаляет все
   `_legacy_window`/`takeCentralWidget()` branches.
7. `TenderSearchUiController` idempotently передаёт page свои семь actions и две scheduler actions;
   ownership QAction остаётся у существующих controllers.
8. Bootstrap сохраняет одну runtime/controller composition и вызывает binding после
   `install_on_main_window()`.
9. Roadmap получает фактически выполненные команды/evidence; `STATUS.md` и history не переводят RM
   в `DONE` до feature merge/post-merge/closeout.

## 3. Compatibility seams

- `MainWindow` сохраняется как standalone QMainWindow wrapper; production его не импортирует.
- Page сохраняет текущие public widget attributes/callback methods для внутренних legacy paths.
- `statusBar()` на page делегирует явно переданный `QStatusBar`; новая business logic не добавляется.
- `refresh_tenders()` делегирует текущему `refresh()`.
- `open_tender(id)` повторяет current refresh/table scan/select-row contract и возвращает `bool`.
- `apply_compatibility_search_text(query)` только заполняет price/equipment `catalog_query`; не
  выбирает новый search engine и не запускает сеть.
- `select_section(key)` использует stable map; неизвестный key возвращает `False`.
- `bind_tender_actions(actions)` добавляет existing QAction instances только один раз и не меняет
  parent, slot, shortcut или enabled state.

## 4. Порядок тестов и коммитов

1. Docs-only audit/plan → `docs(rm-127): audit tender tab ownership`.
2. Red characterization tests → `test(rm-127): define tender workspace tab contract`.
3. Page + wrapper extraction → `feat(rm-127): extract reusable tender workspace page`.
4. Modern composition + action seam → `feat(rm-127): mount tender workspace in modern shell`.
5. Navigation/action/C11/close regressions → `test(rm-127): cover tender navigation and action parity`.
6. Final evidence/roadmap → `docs(rm-127): record feature acceptance evidence`.

Каждый production step сначала проходит RM-127 focused tests, затем соседний controller/dialog
contour. Full gate запускается после завершения scoped implementation.

## 5. Rollback

Rollback состоит только из revert UI/application commits. Schema DB, data/profile files,
credentials, provider state, search/Collector contracts и decision payload не мигрируют. Legacy
wrapper сохраняется до отдельного removal decision, поэтому standalone fallback остаётся доступен.
Если потребуется data migration, новый repository/service или изменение search semantics — работа
останавливается и finding добавляется в audit.

## 6. Non-scope

- universal tender search и facade RM-128;
- business/search profile schemas RM-129/130;
- provider catalog/settings/credentials/protocols RM-131–136;
- normalization/async migration/monitoring/lifecycle RM-137–140;
- visual redesign/design system RM-141+;
- новая DB/migration/dependency/network client;
- новый controller, search engine, Collector, repository или analysis workflow;
- изменения score, recommendation, AI contracts и critical stop-factor priority;
- live network в tests/composition.

## 7. Acceptance checklist

- [ ] Production создаёт один `QMainWindow` — `ModernMainWindow`.
- [ ] `TenderWorkspacePage` — `QWidget` и единственный owner текущих tabs.
- [ ] Production не импортирует/создаёт `LegacyMainWindow`, не вызывает `takeCentralWidget()`.
- [ ] Exact ordered top-level/nested keys, labels и stable `objectName` проверены.
- [ ] Dashboard/business workflow открывают найденный row; missing ID возвращает neutral result.
- [ ] Topbar использует только named compatibility API без network/search engine/Collector call.
- [ ] Existing QAction identity/objectName/shortcut/enabled state сохранены; binding idempotent.
- [ ] Existing menu/toolbar и C11 full-analysis routes сохранены.
- [ ] Legacy wrapper строит ровно одну page и не используется bootstrap.
- [ ] Close smoke не обращается к legacy wrapper.
- [ ] DB/schema/versioned artifacts/dependencies не изменены.
- [ ] Focused, full pytest и workflow-equivalent gate зелёные.
- [ ] Feature PR, post-merge gate и отдельный closeout выполнены до `DONE`.

## 8. Команды проверки

Все pytest commands выполняются с `QT_QPA_PLATFORM=offscreen`, `PYTHONUTF8=1` и при необходимости
с repository-local `--basetemp` из-за подтверждённого Windows Temp permission blocker.

Focused RM-127:

```powershell
python -m pytest -q tests/test_rm127_tender_workspace_contract.py `
  tests/test_rm127_modern_main_window_composition.py `
  tests/test_bootstrap_tender_search_integration.py
```

Соседний UI/controller contour:

```powershell
python -m pytest -q tests/test_tender_search_ui_controller.py `
  tests/test_tender_search_profiles_dialog.py `
  tests/test_tender_search_results_dialog.py `
  tests/test_tender_registry_dialog.py tests/test_tender_collector_dialog.py `
  tests/test_tender_full_analysis_dialog.py
```

Full workflow-equivalent gate:

```powershell
python scripts/check_repository_secrets.py
python -m ruff check .
python -m ruff format . --check
python -m mypy
python -m pytest -q tests/test_collector_provider_control.py::test_manager_exposes_all_sources_without_network `
  tests/test_mos_supplier_diagnostic_script.py::test_mos_diagnostic_runs_from_scripts_path_without_app_error
python -m pytest -q tests/test_database_migrations_121.py tests/test_collector_schema_contract.py
python -c "from app.ui.controllers import DashboardController; print(DashboardController.__name__)"
python -m pytest -q tests/test_bootstrap_tender_search_integration.py
python -m pytest -q tests/test_build_release_contract.py tests/test_frozen_self_test.py
python -m pytest -q
python -m pip_audit --skip-editable
git diff --check
git status --short
```

CI acceptance: Windows Python 3.12/3.13, все jobs `success`.
