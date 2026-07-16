# RM-128 — аудит единого поискового entry contract

## 1. Паспорт аудита

- Дата доказательного среза: `2026-07-16T15:14:42.8881580+03:00`.
- Baseline SHA: `a14b2eb5d4df4ecd41a2b1bdca441e94b4cfa5e1` (`origin/main`).
- Ветка: `feat/rm-128-unified-search-panel`; отдельный worktree
  `C:\Users\LYKA0\AppData\Local\Temp\CorterisTenderAI_rm128`.
- Среда: Windows 10 `10.0.19045.0`, `Russian Standard Time`/UTC+03:00,
  Python `3.12.7`, Qt offscreen.
- Scope audit gate: docs-only; application code, зависимости, DB/schema и сеть не изменялись.

Entry gate пройден: RM-127 имеет статус `DONE`, RM-128 — единственный `IN PROGRESS`,
RM-129–RM-200 — `PLANNED`; baseline совпадает с техническим заданием; открытых PR и local/remote
веток RM-128 до создания рабочей ветки не было. Пользовательские untracked `.agents/` и
`skills-lock.json` основного checkout не изменялись.

## 2. Проверенный контур

Полностью прочитаны canonical roadmap/DoD/history, `docs/RM-126_AUDIT.md`, решения D-01–D-10,
RM-127 audit/plan и техническое задание RM-128. Проверены bootstrap, reusable tender page, modern
shell/topbar, controller, profiles/Collector dialogs, sync runtime/profile runner, async Collector
session/provider manager, релевантные тесты и история обязательных файлов.

Исторические точки ownership:

- `a1d8fa0` — sync profile search и UI controller;
- `27562ed` — provider manager и Collector actions;
- `ba78ed6` — Collector progress/cancellation/partial contract;
- `cc1d8d7` — reusable `TenderWorkspacePage`;
- `4a037ea` — direct modern composition и workspace action binding;
- `a14b2eb` — завершение RM-127 и активация RM-128.

## 3. Baseline tests

Все команды использовали `QT_QPA_PLATFORM=offscreen`, `PYTHONUTF8=1` и проектный
`C:\CorterisTenderAI_1_5_1\.venv\Scripts\python.exe`.

| Контур | Точный результат |
|---|---|
| RM-127/search/Collector/bootstrap baseline | `25 passed in 8.30s` |
| Full pytest | `1532 passed in 64.35s (0:01:04)` |

Первый focused запуск завершился `11 passed, 14 errors` только на setup: pytest не мог создать
вложенный `.tmp/rm128-baseline-focused`, потому что отсутствовал parent `.tmp`. Application code в
14 случаях не исполнялся. После создания подтверждённого gitignored parent тот же command прошёл;
это environment/test-harness blocker, а не скрытый regression.

## 4. Текущие UI entry points

| Entry point | Фактический путь | Текущее поведение |
|---|---|---|
| Topbar Enter | `TopBar.search_requested` → `ModernMainWindow._global_search()` → `TenderWorkspacePage.apply_compatibility_search_text()` | выбирает `tenders`, записывает строку в equipment `catalog_query`; tender network не запускает |
| Profiles action | `TenderSearchUiController.open_profiles_dialog()` → `profile_run_requested` → `run_profile()` | создаёт `_TenderSearchWorker`, вызывает legacy sync `TenderSearchProfileRunner.run()` |
| Collector action | `open_collector_dialog()` → `start_requested` → `try_start_collector()` | создаёт `_CollectorRunWorker`, вызывает async `CollectorRunSession.run()` |
| Scheduler | existing scheduler controller → `try_start_collector()` | использует тот же Collector busy guard/worker path |
| Registry | controller `open_registry_dialog()` | читает canonical shared `tender_records` и переиспользует downstream actions |

`TenderWorkspacePage` — один production owner восьми top-level tabs и шести settings tabs.
`ModernMainWindow` — единственный production `QMainWindow`. Bootstrap создаёт один
`TenderSearchRuntime` и один `TenderSearchUiController`, затем idempotently устанавливает его actions
на shell/page. Встроенного unified-search panel host пока нет.

## 5. Sync и async execution paths

### Legacy sync profile path

`TenderSearchProfileRunner` загружает enabled profile из единственного
`TenderSearchProfileRepository`, строит `TenderSearchQuery` и `TenderFilterOptions`, запускает
`TenderSearchEngine`/`CorterisTenderSearchService`, затем сохраняет run в shared registry. Этот путь
остаётся compatibility/rollback до RM-138 и не используется новой панелью.

### Target async Collector path

`CollectorRunSession` создаёт свежий network runtime только внутри explicit `run()`, вызывает
existing `CollectorService`, передаёт cancellation/progress и всегда закрывает runtime в `finally`.
`TenderSearchUiController` владеет ровно одним `_collector_worker`; dialog и scheduler уже разделяют
busy guard. Collector выполняет существующие normalize/dedup/verification/freshness/ranking/
stop-factor/persistence stages и пишет в canonical registry.

Подтверждённое различие: `CollectorRunSession.run()` принимает `TenderSearchQuery` и provider IDs,
но не принимает legacy `TenderFilterOptions`. RM-128 не должен придумывать второй filter/ranking
pipeline или преждевременно решать parity RM-138. Unified path сохраняет все поля query выбранного
профиля и использует существующий Collector ranking/stop-factor pipeline без изменения decision
семантики; legacy profile-specific filter options продолжают действовать только в rollback path.

## 6. Ownership данных и состояния

| Область | Канонический owner | RM-128 правило |
|---|---|---|
| Profiles | `TenderSearchProfileRepository(search_profiles.json)`, schema v1 | только snapshot/read; ephemeral topbar query не сохранять |
| Query | `TenderSearchProfile.to_search_query()` / immutable `TenderSearchQuery` | pure resolution заменяет только `keywords` при непустом уточнении |
| Providers | `CollectorProviderManager.states()` / `enabled_provider_ids()` | UI получает snapshot; controller повторно валидирует current snapshot до запуска |
| Network/run | `CollectorRunSession` + existing Collector service | один existing session, без startup I/O |
| Busy/cancel/progress | один `_CollectorRunWorker` в `TenderSearchUiController` | panel и Collector dialog отражают один state/token |
| Persistence | existing Collector state + shared `TenderRegistryRepository`/`tender_records` | новый results store/DB запрещён |
| Results | existing registry dialog и controller signals | panel показывает summary/status и открывает тот же registry |
| Theme/actions/dialogs | existing shell/controller | profile/provider/registry dialogs и QAction instances переиспользуются |

Money уже нормализуется в finite non-negative `Decimal`; `TenderSearchQuery` сохраняет explicit
currency. Dates вычисляются существующим `profile.to_search_query()` и не получают придуманного
timezone. Unified resolution не преобразует money во float и не переинтерпретирует даты.

## 7. Подтверждённые gaps и риски

1. Topbar placeholder обещает поиск по нескольким сущностям, но route меняет equipment query.
2. Page не имеет panel host/narrow submit/focus seam.
3. Controller не создаёт unified panel и не передаёт ей snapshots/progress/result state.
4. Создание `_CollectorRunWorker`, signal wiring и cleanup находятся в `try_start_collector()`; новый
   entry нельзя реализовать копированием этого блока.
5. Текущий `try_start_collector()` молча отбрасывает unknown/disabled provider IDs. Для нового typed
   request это запрещено: stale/unknown/disabled source должен дать validation error до network.
6. Ошибки/статус Collector сейчас показываются только открытому Collector dialog.
7. Profile dialog уже эмитит `profile_saved`/`profile_deleted`; panel refresh должен переиспользовать
   эти сигналы, а не опрашивать или создавать второй editor.
8. Provider changes уже проходят через controller `refresh_provider_states()`; тот же snapshot должен
   обновлять panel без live health check.
9. Repeated workspace installation уже ожидается idempotent для actions; panel installation и signal
   binding должны иметь такую же гарантию.
10. Full sync/async filtering parity, provider catalog consolidation, lifecycle shutdown и raw-error
    redaction принадлежат RM-131/RM-138/RM-140 и не должны маскироваться как RM-128 refactor.

## 8. Выбранная архитектура

1. Добавить один pure module `app/tenders/unified_search.py` с immutable request/result и bounded
   validation error. Он получает snapshots profiles/provider states, нормализует input и не владеет
   repository/network/UI.
2. Добавить один reusable `TenderUnifiedSearchPanel(QWidget)`. Он получает только immutable snapshots,
   theme и передаёт typed request через signals; repository/session/SQLite ему недоступны.
3. `TenderWorkspacePage` получает единственный host над `TenderWorkspaceTabs` и narrow idempotent
   `install_unified_search_panel`, `submit_unified_search_text`, `focus_unified_search` seams.
4. `TenderSearchUiController` создаёт panel не более одного раза, соединяет callbacks один раз и перед
   каждым unified start заново читает current repository/provider snapshots.
5. Existing dialog `try_start_collector()` и unified request сходятся в одном внутреннем
   `_try_start_collector_query(...)`, единственном месте создания `_CollectorRunWorker`.
6. Existing `_on_collector_progress/_succeeded/_failed` и `stop_collector()` обновляют оба views, но
   state/worker/token остаются единственными.
7. Topbar выбирает page `tenders` и делегирует строку narrow page API; `catalog_query` больше не
   изменяется этим route. Equipment search и compatibility method сохраняются отдельно.

Архитектура добавляет application request boundary, но не engine/repository/Collector/provider catalog
и не меняет deterministic decision/critical stop-factor priority.

## 9. Non-scope и stop conditions

Non-scope: profile schema RM-130; business capability RM-129; provider settings/catalog/credentials/
protocols/health RM-131–136; normalization/dedup RM-137; sync retirement/parity RM-138; monitoring
RM-139; lifecycle/time/error/schema hardening RM-140; redesign RM-141+; score/recommendation/AI.

Production implementation останавливается, если потребуется DB migration, profile schema/version
change, новый store/catalog/credential mechanism/engine/Collector, legacy sync removal, broad shutdown
rewrite, normalization/provenance/decision change, startup live I/O или silent fallback на другой
profile/provider.

## 10. Audit decision

**ACCEPTED FOR DOCS-ONLY AUDIT COMMIT.** Существенных опровержений технического задания нет.
Pure request boundary нужен для честной provider validation и сохранения business logic вне QWidget.
Production changes разрешены только после отдельного commit этого аудита и
`docs/RM-128_IMPLEMENTATION_PLAN.md`.

## 11. Feature implementation evidence

Audit-first порядок соблюдён:

- docs-only audit/plan: `39605d0`;
- expected-red characterization: `19aceba` (`ModuleNotFoundError` только для ещё отсутствующих
  RM-128 boundaries);
- pure request boundary: `fc015ed`;
- reusable panel: `7c0a3f7`;
- shared controller/page seam: `777079e`;
- topbar composition: `8f7dca8`;
- refresh-state fix/guard: `60685c6`;
- shared busy/cancel/result regressions: `a3307ce`;
- topbar no-network Collector composition: `32c57f7`.

Фактически изменён application/test contour:

- `app/tenders/unified_search.py` — immutable pure profile/provider/query resolution;
- `app/ui/tender_unified_search_panel.py` — единственная reusable panel без service ownership;
- `app/ui/main_window.py` — единственный host и narrow submit/focus delegation;
- `app/ui/modern_main_window.py`, `app/ui/widgets/topbar.py` — explicit tender-search contract;
- `app/ui/tender_search_ui_controller.py` — panel ownership и sole Collector worker seam;
- три RM-128 test modules и scoped RM-127/controller regression updates.

Architecture evidence:

- `TenderWorkspacePage` содержит одну panel и один existing tabs set;
- controller/runtime/profile repository/provider manager/Collector session не создаются panel-слоем;
- `_CollectorRunWorker(` встречается в production controller ровно в одном construction site;
- topbar не содержит/не меняет `catalog_query`; equipment catalog search остаётся самостоятельным;
- unified path повторно валидирует current profile/provider snapshots и вызывает async
  `CollectorRunSession`; legacy `run_profile()` по-прежнему вызывает sync runner;
- dialog, scheduler и panel разделяют один busy guard, worker, cancellation token, progress cleanup и
  existing registry refresh;
- unknown/disabled/stale provider в unified request отклоняется до worker/network без fallback;
- completed/partial/cancelled/failure/invalid-result состояния отображаются раздельно.

Локальная acceptance Windows/Python 3.12.7:

| Check | Exact result |
|---|---|
| Focused RM-128/controller/bootstrap | `23 passed in 5.20s` |
| Neighbor RM-127/UI/Collector | `66 passed in 8.80s` |
| Full pytest | `1552 passed in 61.49s (0:01:01)` |
| Secret scan | `Repository secret scan passed.` |
| Ruff check | `All checks passed!` |
| Ruff format | `545 files already formatted` |
| mypy | `Success: no issues found in 20 source files` |
| Offline credential smoke | `2 passed in 5.38s` |
| Migration/schema smoke | `5 passed in 3.12s` |
| Import smoke | `DashboardController` |
| Bootstrap composition smoke | `1 passed in 0.27s` |
| Build/release smoke | `6 passed in 4.17s` |
| Dependency audit | `No known vulnerabilities found`; editable project skipped |
| Diff/status | `git diff --check` success; clean before evidence update |

DB/schema/migration version, `search_profiles.json` schema v1, dependencies, provider catalog,
credentials, money/time policy, normalization/provenance, score/recommendation/AI и critical
stop-factor priority не изменены. Composition tests запрещают network I/O; live provider checks не
запускаются. Feature готова к PR, но RM-128 остаётся `IN PROGRESS` до merge, successful post-merge
Windows Quality Gate Python 3.12/3.13 и отдельного docs-only closeout.
